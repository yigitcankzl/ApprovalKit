"""Tests for Token Vault improvements.

Validates:
1. Management API fallback removed
2. Token caching (Redis)
3. Refresh token rotation detection
4. Scope validation logging

No external deps needed — uses asyncio.run() instead of pytest-asyncio.
"""

import sys
import os
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, AsyncMock, patch


# ---------------------------------------------------------------------------
# 1. Management API fallback removed
# ---------------------------------------------------------------------------

def test_management_api_fallback_removed():
    """get_token_from_auth0 should no longer exist on TokenVaultService."""
    from api.services.token_vault import TokenVaultService
    assert not hasattr(TokenVaultService, "get_token_from_auth0"), \
        "get_token_from_auth0 should be removed — no Management API fallback"


# ---------------------------------------------------------------------------
# 2. Token cache helpers
# ---------------------------------------------------------------------------

def test_token_cache_set_and_get():
    """Cache helpers should write/read via Redis."""
    from api.services.token_vault import TokenVaultService

    svc = TokenVaultService.__new__(TokenVaultService)  # skip __init__

    mock_redis = MagicMock()
    mock_redis.get.return_value = "cached-access-token"

    with patch("api.services.token_vault.auth0_breaker") as mock_breaker:
        mock_breaker._get_redis.return_value = mock_redis

        # set
        svc._set_cached_token("test-key", "my-token", 120)
        mock_redis.setex.assert_called_once_with("test-key", 120, "my-token")

        # get
        result = svc._get_cached_token("test-key")
        assert result == "cached-access-token"


def test_token_cache_returns_none_without_redis():
    """Cache helpers should return None if Redis is unavailable."""
    from api.services.token_vault import TokenVaultService

    svc = TokenVaultService.__new__(TokenVaultService)

    with patch("api.services.token_vault.auth0_breaker") as mock_breaker:
        mock_breaker._get_redis.return_value = None

        assert svc._get_cached_token("key") is None
        svc._set_cached_token("key", "val")  # should not raise


# ---------------------------------------------------------------------------
# 3. Refresh token rotation detection
# ---------------------------------------------------------------------------

def test_refresh_token_rotation_detection():
    """When Auth0 returns a new refresh_token, it should be stored on the service."""
    from api.services.token_vault import TokenVaultService

    svc = TokenVaultService.__new__(TokenVaultService)
    svc.domain = "test.auth0.com"
    svc.client_id = "cid"
    svc.client_secret = "csec"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "new-access",
        "refresh_token": "rotated-refresh-token",
        "scope": "read:data write:data",
    }

    with patch("api.services.token_vault.auth0_breaker") as mock_breaker, \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_breaker.allow_request.return_value = True
        mock_breaker.record_success = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        token = asyncio.run(svc.get_token_via_exchange("stripe", "old-refresh"))

        assert token == "new-access"
        assert svc._rotated_refresh_token == "rotated-refresh-token"


def test_no_rotation_when_same_refresh_token():
    """When refresh_token in response matches input, _rotated_refresh_token should be None."""
    from api.services.token_vault import TokenVaultService

    svc = TokenVaultService.__new__(TokenVaultService)
    svc.domain = "test.auth0.com"
    svc.client_id = "cid"
    svc.client_secret = "csec"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "new-access",
        "refresh_token": "same-refresh",
        "scope": "read:data",
    }

    with patch("api.services.token_vault.auth0_breaker") as mock_breaker, \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_breaker.allow_request.return_value = True
        mock_breaker.record_success = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        token = asyncio.run(svc.get_token_via_exchange("stripe", "same-refresh"))

        assert token == "new-access"
        assert svc._rotated_refresh_token is None


# ---------------------------------------------------------------------------
# 4. Scope validation
# ---------------------------------------------------------------------------

def test_scope_returned_in_exchange():
    """Token Exchange with scope should succeed without errors."""
    from api.services.token_vault import TokenVaultService

    svc = TokenVaultService.__new__(TokenVaultService)
    svc.domain = "test.auth0.com"
    svc.client_id = "cid"
    svc.client_secret = "csec"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "tok",
        "scope": "openid profile email",
    }

    with patch("api.services.token_vault.auth0_breaker") as mock_breaker, \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_breaker.allow_request.return_value = True
        mock_breaker.record_success = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        token = asyncio.run(svc.get_token_via_exchange("google", "refresh"))
        assert token == "tok"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_cache_constants():
    """Verify cache constants are sensible."""
    from api.services.token_vault import _TOKEN_CACHE_TTL, _TOKEN_CACHE_PREFIX
    assert _TOKEN_CACHE_TTL == 270  # 4.5 minutes
    assert _TOKEN_CACHE_PREFIX == "tvault:token:"
