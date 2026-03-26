"""
Field-level encryption for workspace credentials
=================================================
Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).
The encryption key is derived from CREDENTIALS_KEY in .env.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

from api.config import get_settings

settings = get_settings()


def _get_fernet() -> Fernet | None:
    key = settings.CREDENTIALS_KEY or settings.HMAC_SECRET
    if not key:
        return None
    # Derive a valid Fernet key (32 bytes, base64-encoded)
    derived = hashlib.sha256(key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(derived)
    return Fernet(fernet_key)


def encrypt_secret(value: str | None) -> str | None:
    """Encrypt a secret value. Returns base64-encoded ciphertext."""
    if not value:
        return value
    f = _get_fernet()
    if not f:
        if settings.ENVIRONMENT == "production":
            raise RuntimeError("CREDENTIALS_KEY or HMAC_SECRET must be set in production — refusing to store secrets in plaintext")
        logger.warning("CREDENTIALS_KEY not set — storing secret in plaintext (dev mode only)")
        return value
    return f.encrypt(value.encode()).decode()


def decrypt_secret(value: str | None) -> str | None:
    """Decrypt a secret value. Falls back to plain text if decryption fails."""
    if not value:
        return value
    f = _get_fernet()
    if not f:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        # Value might be plain text (pre-encryption) — return as-is
        return value
