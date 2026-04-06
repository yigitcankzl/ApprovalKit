"""Tests for api/services/redis_pool.py.

Covers:
 - get_redis() singleton: same URL → same instance
 - get_redis() different URL → different instance
 - aclose_all() closes clients + clears dict
 - aclose_all() suppresses individual close errors
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("HMAC_SECRET", "pool-test")

from unittest.mock import AsyncMock, MagicMock, patch
from api.services import redis_pool


class TestGetRedis:
    def setup_method(self):
        redis_pool._clients.clear()

    def test_same_url_returns_same_instance(self):
        with patch("api.services.redis_pool.aioredis") as mock_aio:
            fake_client = MagicMock()
            mock_aio.from_url.return_value = fake_client
            a = redis_pool.get_redis("redis://test:6379/0")
            b = redis_pool.get_redis("redis://test:6379/0")
        assert a is b
        # from_url called only once.
        mock_aio.from_url.assert_called_once()

    def test_different_url_returns_different_instance(self):
        with patch("api.services.redis_pool.aioredis") as mock_aio:
            c1 = MagicMock()
            c2 = MagicMock()
            mock_aio.from_url.side_effect = [c1, c2]
            a = redis_pool.get_redis("redis://host1:6379")
            b = redis_pool.get_redis("redis://host2:6379")
        assert a is not b
        assert mock_aio.from_url.call_count == 2

    def test_default_url_from_settings(self):
        with patch("api.services.redis_pool.aioredis") as mock_aio:
            mock_aio.from_url.return_value = MagicMock()
            c = redis_pool.get_redis()
        mock_aio.from_url.assert_called_once_with(
            redis_pool._settings.REDIS_URL,
            decode_responses=True,
            max_connections=50,
        )

    def teardown_method(self):
        redis_pool._clients.clear()


class TestAcloseAll:
    def test_closes_all_clients_and_clears(self):
        c1 = MagicMock()
        c1.aclose = AsyncMock()
        c2 = MagicMock()
        c2.aclose = AsyncMock()
        redis_pool._clients["a"] = c1
        redis_pool._clients["b"] = c2
        asyncio.run(redis_pool.aclose_all())
        c1.aclose.assert_awaited_once()
        c2.aclose.assert_awaited_once()
        assert len(redis_pool._clients) == 0

    def test_suppresses_close_error_and_continues(self):
        c1 = MagicMock()
        c1.aclose = AsyncMock(side_effect=RuntimeError("boom"))
        c2 = MagicMock()
        c2.aclose = AsyncMock()
        redis_pool._clients["a"] = c1
        redis_pool._clients["b"] = c2
        # Must not raise.
        asyncio.run(redis_pool.aclose_all())
        c1.aclose.assert_awaited_once()
        c2.aclose.assert_awaited_once()
        assert len(redis_pool._clients) == 0

    def test_empty_dict_noop(self):
        redis_pool._clients.clear()
        asyncio.run(redis_pool.aclose_all())
        assert len(redis_pool._clients) == 0
