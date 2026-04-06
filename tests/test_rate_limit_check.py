"""Tests for check_api_rate_limit (the FastAPI dependency).

Covers:
 - Authenticated path: rate-limits by api key
 - Unauthenticated path: rate-limits by IP
 - Rate limit exceeded → 429 HTTPException
"""
import asyncio
import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("HMAC_SECRET", "rl-test")
os.environ["TRUSTED_PROXY_COUNT"] = "0"

from unittest.mock import AsyncMock, MagicMock, patch

from api.config import get_settings
get_settings.cache_clear()

from api.middleware import rate_limit as rl_mod

try:
    from fastapi import HTTPException
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

needs_fastapi = pytest.mark.skipif(not HAS_FASTAPI, reason="fastapi not installed")


def _make_request(api_key="", peer_ip="10.0.0.1"):
    req = MagicMock()
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": headers.get(key, default)
    req.client = MagicMock()
    req.client.host = peer_ip
    return req


@needs_fastapi
class TestCheckApiRateLimit:
    def test_authenticated_uses_apikey_key(self):
        req = _make_request(api_key="my-key")
        rl_mod.rate_limiter.check_rate_limit = AsyncMock(return_value=True)
        asyncio.run(rl_mod.check_api_rate_limit(req))
        call_kwargs = rl_mod.rate_limiter.check_rate_limit.call_args.kwargs
        assert call_kwargs["key"] == "apikey:my-key"

    def test_unauthenticated_uses_ip_key(self):
        req = _make_request(peer_ip="99.99.99.99")
        rl_mod.rate_limiter.check_rate_limit = AsyncMock(return_value=True)
        asyncio.run(rl_mod.check_api_rate_limit(req))
        call_kwargs = rl_mod.rate_limiter.check_rate_limit.call_args.kwargs
        assert call_kwargs["key"] == "ip:99.99.99.99"

    def test_authenticated_rate_exceeded_raises_429(self):
        req = _make_request(api_key="my-key")
        rl_mod.rate_limiter.check_rate_limit = AsyncMock(return_value=False)
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(rl_mod.check_api_rate_limit(req))
        assert exc_info.value.status_code == 429

    def test_unauthenticated_rate_exceeded_raises_429(self):
        req = _make_request(peer_ip="1.2.3.4")
        rl_mod.rate_limiter.check_rate_limit = AsyncMock(return_value=False)
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(rl_mod.check_api_rate_limit(req))
        assert exc_info.value.status_code == 429

    def test_allowed_no_exception(self):
        req = _make_request(api_key="k")
        rl_mod.rate_limiter.check_rate_limit = AsyncMock(return_value=True)
        # Must not raise.
        asyncio.run(rl_mod.check_api_rate_limit(req))
