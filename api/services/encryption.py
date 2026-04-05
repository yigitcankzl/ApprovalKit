"""
Field-level encryption for workspace credentials
=================================================
Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).
The encryption key is derived from CREDENTIALS_KEY in .env.

Key rotation
------------
Set CREDENTIALS_KEY_PREVIOUS to the old key while rotating. Decryption
will try the current key first and fall back to the previous key, so
already-stored ciphertext keeps working. Re-encrypt on next write and
drop CREDENTIALS_KEY_PREVIOUS once migrated.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from loguru import logger

from api.config import get_settings

settings = get_settings()


def _derive_fernet(key: str) -> Fernet:
    """Derive a valid Fernet key (32 bytes, base64-encoded) from any string."""
    derived = hashlib.sha256(key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(derived)
    return Fernet(fernet_key)


def _get_fernet() -> MultiFernet | None:
    """Return a MultiFernet that encrypts with the current key and can
    decrypt with either the current or previous key."""
    current = settings.CREDENTIALS_KEY or settings.HMAC_SECRET
    if not current:
        return None
    ferns = [_derive_fernet(current)]
    previous = settings.CREDENTIALS_KEY_PREVIOUS
    if previous and previous != current:
        ferns.append(_derive_fernet(previous))
    return MultiFernet(ferns)


def encrypt_secret(value: str | None) -> str | None:
    """Encrypt a secret value. Returns base64-encoded ciphertext."""
    if not value:
        return value
    f = _get_fernet()
    if not f:
        if settings.ENVIRONMENT == "production":
            raise RuntimeError(
                "CREDENTIALS_KEY or HMAC_SECRET must be set in production — refusing to store secrets in plaintext"
            )
        logger.warning("CREDENTIALS_KEY not set — storing secret in plaintext (dev mode only)")
        return value
    return f.encrypt(value.encode()).decode()


def decrypt_secret(value: str | None) -> str | None:
    """
    Decrypt a secret value.

    - If encryption is not configured, return the value unchanged.
    - Try current key, then previous key (rotation support).
    - If the value is not valid Fernet ciphertext (legacy pre-encryption
      plaintext), return it as-is — but log a warning so this is visible.
    """
    if not value:
        return value
    f = _get_fernet()
    if not f:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except InvalidToken:
        # Value is likely legacy plaintext stored before encryption was
        # enabled. Returning as-is keeps backwards compat, but surface it.
        logger.warning(
            "decrypt_secret: InvalidToken — value is not valid ciphertext under any known key. "
            "Treating as legacy plaintext. Rotate and re-encrypt this record."
        )
        return value
    except Exception as e:
        logger.error(f"Unexpected decryption error: {type(e).__name__}: {e}")
        if settings.ENVIRONMENT == "production":
            # Don't silently leak plaintext on unexpected errors in prod.
            raise
        return value
