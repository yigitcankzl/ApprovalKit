"""
Provider factory.

Reads `APPROVAL_PROVIDER` (and per-component overrides) from settings
and returns the appropriate ApprovalChannel / CredentialStore /
IdentityProvider instances. Cached so providers act like singletons.

Existing call sites (routes, workers) can keep using the concrete
services directly — these factories exist for new code that wants to
program against the protocols, and for selecting the right backend at
startup.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from api.config import get_settings
from api.providers.base import ApprovalChannel, CredentialStore, IdentityProvider


def _resolve(override: str, default: str) -> str:
    return (override or default or "auth0").strip().lower()


@lru_cache(maxsize=1)
def get_approval_channel() -> ApprovalChannel:
    settings = get_settings()
    backend = _resolve(settings.APPROVAL_CHANNEL, settings.APPROVAL_PROVIDER)
    if backend == "local":
        from api.providers.local import LocalApprovalChannel
        return LocalApprovalChannel(
            dashboard_url=settings.FRONTEND_URL,
            auto_approve=settings.LOCAL_APPROVAL_AUTO_APPROVE,
        )
    if backend == "auth0":
        from api.providers.auth0 import Auth0CIBAChannel
        return Auth0CIBAChannel()
    raise ValueError(f"Unknown APPROVAL_CHANNEL backend: {backend!r}")


@lru_cache(maxsize=1)
def get_identity_provider() -> IdentityProvider:
    settings = get_settings()
    backend = _resolve(settings.IDENTITY_PROVIDER, settings.APPROVAL_PROVIDER)
    if backend == "local":
        from api.providers.local import LocalHeaderIdentityProvider
        return LocalHeaderIdentityProvider()
    if backend == "auth0":
        from api.providers.auth0 import Auth0JWTIdentityProvider
        return Auth0JWTIdentityProvider()
    raise ValueError(f"Unknown IDENTITY_PROVIDER backend: {backend!r}")


def _build_credential_store() -> CredentialStore:
    settings = get_settings()
    backend = _resolve(settings.CREDENTIAL_STORE, settings.APPROVAL_PROVIDER)
    if backend == "local":
        from api.providers.local import LocalCredentialStore

        async def _missing_loader(user_id: str, connection: str) -> str | None:
            return None

        # Callers that need the local store with a real loader should
        # instantiate `LocalCredentialStore` directly. The factory
        # returns a permissive default so importing it does not crash
        # when no DB-backed loader has been wired up yet.
        return LocalCredentialStore(loader=_missing_loader)
    if backend == "auth0":
        from api.providers.auth0 import Auth0TokenVaultStore

        async def _missing_lookup(user_id: str, connection: str) -> str | None:
            return None

        return Auth0TokenVaultStore(refresh_token_lookup=_missing_lookup)
    raise ValueError(f"Unknown CREDENTIAL_STORE backend: {backend!r}")


@lru_cache(maxsize=1)
def get_credential_store() -> CredentialStore:
    return _build_credential_store()


def reset_provider_cache() -> None:
    """Drop cached providers — primarily for tests that flip env vars."""
    get_approval_channel.cache_clear()
    get_identity_provider.cache_clear()
    get_credential_store.cache_clear()
