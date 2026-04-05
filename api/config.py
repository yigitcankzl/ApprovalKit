from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://localhost:5432/approvalkit"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth0
    AUTH0_DOMAIN: str = ""
    AUTH0_CLIENT_ID: str = ""
    AUTH0_CLIENT_SECRET: str = ""
    AUTH0_WEB_CLIENT_ID: str = ""
    AUTH0_WEB_CLIENT_SECRET: str = ""
    AUTH0_AUDIENCE: str = ""
    AUTH0_MGMT_API_AUDIENCE: str = ""

    # Auth0 FGA
    FGA_API_URL: str = ""
    FGA_STORE_ID: str = ""
    FGA_MODEL_ID: str = ""
    FGA_CLIENT_ID: str = ""
    FGA_CLIENT_SECRET: str = ""

    # CIBA
    CIBA_POLL_INTERVAL: int = 2
    CIBA_MAX_POLL_INTERVAL: int = 30
    CIBA_QUOTA_LIMIT: int = 500
    CIBA_QUOTA_WARN_PERCENT: int = 80

    # Security
    HMAC_SECRET: str = ""
    HMAC_TIMESTAMP_TOLERANCE: int = 300  # 5 minutes
    API_RATE_LIMIT: int = 100
    # 32-byte URL-safe base64 key for Fernet credential encryption.
    # Auto-derived from HMAC_SECRET when empty.
    CREDENTIALS_KEY: str = ""
    # Previous key kept during rotation: decrypt attempts the current key
    # first, then this one. Leave empty when not rotating.
    CREDENTIALS_KEY_PREVIOUS: str = ""

    # HashiCorp Vault (Credential Vault for M2M API keys)
    VAULT_URL: str = ""
    VAULT_TOKEN: str = ""

    # Sentry
    SENTRY_DSN: str = ""
    ENVIRONMENT: str = "production"

    # OAuth Connect callback
    CALLBACK_BASE_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
