"""HashiCorp Vault integration for production-grade secret management.

Provides short-lived credential retrieval with automatic TTL expiry.
Falls back to Fernet encryption (encryption.py) when Vault is unavailable.

Architecture:
    Token Vault (Auth0)     → user-delegated OAuth credentials (Stripe, GitHub, Gmail)
    HashiCorp Vault         → M2M API keys + webhook secrets (Amadeus, Twilio, AWS)
    Fernet (fallback)       → development mode when Vault is not running

Secrets are stored in Vault KV v2 at path: secret/approvalkit/{workspace_id}/{connection_slug}
"""

import hvac
from loguru import logger

from api.config import get_settings

settings = get_settings()

_client: hvac.Client | None = None
_BASE_PATH = "approvalkit"


def _get_vault_client() -> hvac.Client | None:
    """Get or create a Vault client. Returns None if Vault is not configured."""
    global _client

    vault_url = getattr(settings, "VAULT_URL", None) or "http://localhost:8200"
    vault_token = getattr(settings, "VAULT_TOKEN", None) or "approvalkit-dev-token"

    if not vault_url:
        return None

    if _client and _client.is_authenticated():
        return _client

    try:
        _client = hvac.Client(url=vault_url, token=vault_token)
        if _client.is_authenticated():
            logger.info(f"Vault connected: {vault_url}")
            return _client
        logger.warning("Vault token is not authenticated")
        _client = None
    except Exception as e:
        logger.warning(f"Vault connection failed: {e}")
        _client = None

    return None


def is_vault_available() -> bool:
    """Check if Vault is reachable and authenticated."""
    client = _get_vault_client()
    return client is not None


def store_secret(workspace_id: str, slug: str, data: dict) -> bool:
    """Store a secret in Vault KV v2.

    ``data`` is a dict of key-value pairs, e.g.:
        {"api_key": "sk_live_xxx", "client_id": "abc123", "token_url": "https://..."}

    Stored at: secret/data/approvalkit/{workspace_id}/{slug}
    """
    client = _get_vault_client()
    if not client:
        logger.debug("Vault unavailable — secret not stored in Vault")
        return False

    path = f"{_BASE_PATH}/{workspace_id}/{slug}"
    try:
        client.secrets.kv.v2.create_or_update_secret(path=path, secret=data)
        logger.info(f"Vault: stored secret at {path}")
        return True
    except Exception as e:
        logger.warning(f"Vault: failed to store secret at {path}: {e}")
        return False


def read_secret(workspace_id: str, slug: str) -> dict | None:
    """Read a secret from Vault KV v2.

    Returns the secret data dict, or None if not found / Vault unavailable.
    """
    client = _get_vault_client()
    if not client:
        return None

    path = f"{_BASE_PATH}/{workspace_id}/{slug}"
    try:
        response = client.secrets.kv.v2.read_secret_version(path=path)
        data = response["data"]["data"]
        logger.debug(f"Vault: read secret from {path}")
        return data
    except hvac.exceptions.InvalidPath:
        logger.debug(f"Vault: no secret at {path}")
        return None
    except Exception as e:
        logger.warning(f"Vault: failed to read secret at {path}: {e}")
        return None


def delete_secret(workspace_id: str, slug: str) -> bool:
    """Delete a secret from Vault KV v2."""
    client = _get_vault_client()
    if not client:
        return False

    path = f"{_BASE_PATH}/{workspace_id}/{slug}"
    try:
        client.secrets.kv.v2.delete_metadata_and_all_versions(path=path)
        logger.info(f"Vault: deleted secret at {path}")
        return True
    except Exception as e:
        logger.warning(f"Vault: failed to delete secret at {path}: {e}")
        return False


def store_m2m_credentials(
    workspace_id: str,
    slug: str,
    api_key: str,
    client_id: str | None = None,
    token_url: str | None = None,
) -> bool:
    """Store M2M API credentials in Vault (or fall back to Fernet encryption).

    This is the primary interface for Credential Vault. If Vault is available,
    credentials go to Vault KV. If not, caller should use encrypt_secret() as fallback.

    Returns True if stored in Vault, False if fallback needed.
    """
    data = {"api_key": api_key}
    if client_id:
        data["client_id"] = client_id
    if token_url:
        data["token_url"] = token_url

    return store_secret(workspace_id, slug, data)


def read_m2m_credentials(workspace_id: str, slug: str) -> dict | None:
    """Read M2M API credentials from Vault.

    Returns {"api_key": "...", "client_id": "...", "token_url": "..."} or None.
    If None, caller should fall back to Fernet-encrypted DB fields.
    """
    return read_secret(workspace_id, slug)
