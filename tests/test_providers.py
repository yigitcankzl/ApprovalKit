"""Smoke tests for the pluggable provider abstraction."""
from __future__ import annotations

import pytest

from api.providers.base import (
    ActionExecutionRequest,
    ActionExecutor,
    ApprovalChannel,
    ApprovalRequest,
    ApprovalStatus,
    CredentialStore,
    Identity,
    IdentityProvider,
    ProviderUnavailable,
)
from api.providers.local.credentials import LocalCredentialStore
from api.providers.local.executor import LocalActionExecutor
from api.providers.local.identity import LocalHeaderIdentityProvider


def test_protocols_are_runtime_checkable():
    """Ensure the local providers satisfy the protocols at runtime."""
    from api.providers.local.approval import LocalApprovalChannel

    assert isinstance(LocalApprovalChannel(), ApprovalChannel)
    assert isinstance(
        LocalCredentialStore(loader=_loader_returning(None)), CredentialStore,
    )
    assert isinstance(LocalHeaderIdentityProvider(), IdentityProvider)
    assert isinstance(LocalActionExecutor(), ActionExecutor)


def test_factory_resolves_local_backend(monkeypatch):
    monkeypatch.setenv("APPROVAL_PROVIDER", "local")
    from api.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    from api.providers import (
        get_action_executor,
        get_approval_channel,
        get_credential_store,
        get_identity_provider,
        reset_provider_cache,
    )
    reset_provider_cache()

    assert get_approval_channel().name == "local"
    assert get_credential_store().name == "local-fernet"
    assert get_identity_provider().name == "local-header"
    assert get_action_executor().name == "local-noop"

    reset_provider_cache()
    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_factory_resolves_auth0_executor(monkeypatch):
    monkeypatch.setenv("APPROVAL_PROVIDER", "auth0")
    from api.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    from api.providers import get_action_executor, reset_provider_cache
    reset_provider_cache()

    assert get_action_executor().name == "auth0-token-vault"

    reset_provider_cache()
    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_local_executor_is_a_noop():
    """The local executor never runs anything server-side — it returns a
    skipped receipt so client-mode callers know to run the action themselves."""
    import asyncio

    executor = LocalActionExecutor()
    receipt = asyncio.run(executor.execute(ActionExecutionRequest(
        connection="stripe",
        action="charge",
        params={"amount": 100},
        workspace_id="ws-1",
        db=None,
    )))
    assert receipt["skipped"] is True
    assert receipt["success"] is False


def test_factory_rejects_unknown_backend(monkeypatch):
    monkeypatch.setenv("APPROVAL_PROVIDER", "fictional")
    from api.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    from api.providers import get_approval_channel, reset_provider_cache
    reset_provider_cache()

    with pytest.raises(ValueError, match="Unknown APPROVAL_CHANNEL"):
        get_approval_channel()

    reset_provider_cache()
    get_settings.cache_clear()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_local_credential_store_missing_cipher_raises():
    store = LocalCredentialStore(loader=_loader_returning(None))
    with pytest.raises(ProviderUnavailable):
        await store.get_access_token(user_id="u", connection="stripe")


@pytest.mark.asyncio
async def test_local_credential_store_decrypts(monkeypatch):
    from api.services.encryption import encrypt_secret
    cipher = encrypt_secret("super-secret-token")
    assert cipher is not None

    store = LocalCredentialStore(loader=_loader_returning(cipher))
    token = await store.get_access_token(user_id="u", connection="stripe")
    assert token == "super-secret-token"


@pytest.mark.asyncio
async def test_local_identity_requires_header(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    from api.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    provider = LocalHeaderIdentityProvider()
    with pytest.raises(ProviderUnavailable):
        await provider.authenticate(authorization=None, headers={})
    identity = await provider.authenticate(
        authorization=None,
        headers={"X-User-Sub": "auth0|123"},
    )
    assert isinstance(identity, Identity)
    assert identity.sub == "auth0|123"


@pytest.mark.asyncio
async def test_local_identity_refuses_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    from api.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    provider = LocalHeaderIdentityProvider()
    with pytest.raises(ProviderUnavailable):
        await provider.authenticate(
            authorization=None,
            headers={"X-User-Sub": "auth0|123"},
        )


def _loader_returning(value):
    async def _loader(user_id: str, connection: str):
        return value
    return _loader
