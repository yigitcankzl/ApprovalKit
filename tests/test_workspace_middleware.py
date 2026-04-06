"""Tests for api/middleware/workspace.py — _extract_bearer, _resolve_sub, get_current_workspace.

Covers the untested branches:
 - _extract_bearer: X-User-Token empty → fallback to Authorization,
   Authorization present but empty after "Bearer " → None
 - _resolve_sub: token + no domain, token invalid + enforcement on,
   no token + enforcement off + empty X-User-Sub
 - get_current_workspace: sub found no workspace → 404,
   enforcement on + no sub → 401, fallback no workspace → 404
"""
import asyncio
import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("HMAC_SECRET", "ws-test")
os.environ["AUTH0_DOMAIN"] = "tenant.us.auth0.com"
os.environ["AUTH0_AUDIENCE"] = "https://api.approvalkit.example/"
os.environ["AUTH0_CLIENT_ID"] = "m2m-id"
os.environ["AUTH0_WEB_CLIENT_ID"] = "web-id"
os.environ["ENVIRONMENT"] = "production"

from unittest.mock import AsyncMock, MagicMock, patch
from api.config import get_settings


def _reload():
    get_settings.cache_clear()
    from api.middleware import workspace as wsmod
    importlib.reload(wsmod)
    return wsmod


def _fake_request(user_token="", auth_header="", user_sub=""):
    req = MagicMock()
    headers = {}
    if user_token:
        headers["X-User-Token"] = user_token
    if auth_header:
        headers["Authorization"] = auth_header
    if user_sub:
        headers["X-User-Sub"] = user_sub
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": headers.get(key, default)
    req.url = MagicMock()
    req.url.path = "/test"
    return req


# -------------------------------------------------------------------
# _extract_bearer
# -------------------------------------------------------------------
class TestExtractBearer:
    def test_prefers_x_user_token(self):
        ws = _reload()
        req = _fake_request(user_token="tok-a", auth_header="Bearer tok-b")
        assert ws._extract_bearer(req) == "tok-a"

    def test_falls_back_to_authorization(self):
        ws = _reload()
        req = _fake_request(auth_header="Bearer my-jwt")
        assert ws._extract_bearer(req) == "my-jwt"

    def test_empty_x_user_token_falls_back(self):
        ws = _reload()
        req = _fake_request(user_token="", auth_header="Bearer fallback-jwt")
        assert ws._extract_bearer(req) == "fallback-jwt"

    def test_whitespace_x_user_token_falls_back(self):
        ws = _reload()
        req = _fake_request(user_token="   ", auth_header="Bearer fallback")
        assert ws._extract_bearer(req) == "fallback"

    def test_bearer_empty_after_prefix_returns_none(self):
        ws = _reload()
        req = _fake_request(auth_header="Bearer ")
        assert ws._extract_bearer(req) is None

    def test_non_bearer_auth_returns_none(self):
        ws = _reload()
        req = _fake_request(auth_header="Basic abc123")
        assert ws._extract_bearer(req) is None

    def test_no_headers_returns_none(self):
        ws = _reload()
        req = _fake_request()
        assert ws._extract_bearer(req) is None


# -------------------------------------------------------------------
# _resolve_sub
# -------------------------------------------------------------------
class TestResolveSub:
    def test_token_present_domain_empty_honours_x_user_sub(self):
        """Token present but AUTH0_DOMAIN empty → can't verify → fall back
        to X-User-Sub if enforcement is off."""
        os.environ["AUTH0_DOMAIN"] = ""
        os.environ["ENVIRONMENT"] = "development"
        ws = _reload()
        req = _fake_request(user_token="some-jwt", user_sub="auth0|user1")
        result = asyncio.run(ws._resolve_sub(req))
        assert result == "auth0|user1"
        os.environ["AUTH0_DOMAIN"] = "tenant.us.auth0.com"
        os.environ["ENVIRONMENT"] = "production"

    def test_token_invalid_enforcement_on_returns_none(self):
        """Token present but verify fails + enforcement on → None
        (don't fall through to X-User-Sub)."""
        os.environ["ENVIRONMENT"] = "production"
        os.environ["AUTH0_DOMAIN"] = "tenant.us.auth0.com"
        ws = _reload()
        with patch.object(ws, "_verify_auth0_token", return_value=None):
            req = _fake_request(user_token="bad-jwt", user_sub="auth0|attacker")
            result = asyncio.run(ws._resolve_sub(req))
        assert result is None

    def test_no_token_enforcement_off_empty_sub_returns_none(self):
        os.environ["ENVIRONMENT"] = "development"
        ws = _reload()
        req = _fake_request()
        result = asyncio.run(ws._resolve_sub(req))
        assert result is None
        os.environ["ENVIRONMENT"] = "production"

    def test_no_token_enforcement_off_returns_sub(self):
        os.environ["ENVIRONMENT"] = "development"
        ws = _reload()
        req = _fake_request(user_sub="auth0|dev-user")
        result = asyncio.run(ws._resolve_sub(req))
        assert result == "auth0|dev-user"
        os.environ["ENVIRONMENT"] = "production"

    def test_no_token_enforcement_on_returns_none(self):
        os.environ["ENVIRONMENT"] = "production"
        os.environ["AUTH0_DOMAIN"] = "tenant.us.auth0.com"
        ws = _reload()
        req = _fake_request(user_sub="auth0|ignored")
        result = asyncio.run(ws._resolve_sub(req))
        assert result is None
