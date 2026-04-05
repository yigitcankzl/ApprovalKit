"""Tests for OAuth state CSRF nonce helpers.

Covers:
 - nonce mint → store → consume roundtrip
 - single-use (consume twice → False)
 - mismatched connection_id rejected (cross-connection replay)
 - short/empty nonces rejected
 - Redis failure fails-closed
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("HMAC_SECRET", "nonce-test")

from unittest.mock import AsyncMock, MagicMock, patch


def _import_helpers():
    # These live in routes/connections.py; importing the route module
    # pulls in lots of deps but module import doesn't touch the net.
    from api.routes.connections import (
        _consume_oauth_state_nonce,
        _issue_oauth_state_nonce,
    )
    return _issue_oauth_state_nonce, _consume_oauth_state_nonce


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def setex(self, key, ttl, value):
        self.store[key] = (value, ttl)
        return True

    async def getdel(self, key):
        entry = self.store.pop(key, None)
        return entry[0] if entry else None

    async def aclose(self):
        pass


class TestIssueNonce:
    def test_state_format(self):
        issue, _ = _import_helpers()
        fake = FakeRedis()
        with patch("api.services.redis_pool.get_redis", return_value=fake):
            state = asyncio.run(issue("conn-1", "ws-1"))
        assert isinstance(state, str)
        parts = state.split(":")
        assert len(parts) == 3
        nonce, conn_id, ws_id = parts
        assert conn_id == "conn-1"
        assert ws_id == "ws-1"
        # token_urlsafe(32) yields ~43 chars
        assert len(nonce) >= 40

    def test_nonce_stored_in_redis(self):
        issue, _ = _import_helpers()
        fake = FakeRedis()
        with patch("api.services.redis_pool.get_redis", return_value=fake):
            state = asyncio.run(issue("conn-2", "ws-2"))
        nonce = state.split(":")[0]
        assert f"oauth_state:{nonce}" in fake.store
        value, ttl = fake.store[f"oauth_state:{nonce}"]
        assert value == "conn-2:ws-2"
        assert ttl == 600  # 10 min

    def test_two_issues_produce_different_nonces(self):
        issue, _ = _import_helpers()
        fake = FakeRedis()
        with patch("api.services.redis_pool.get_redis", return_value=fake):
            a = asyncio.run(issue("conn", "ws"))
            b = asyncio.run(issue("conn", "ws"))
        assert a.split(":")[0] != b.split(":")[0]


class TestConsumeNonce:
    def test_roundtrip_success(self):
        issue, consume = _import_helpers()
        fake = FakeRedis()
        with patch("api.services.redis_pool.get_redis", return_value=fake):
            state = asyncio.run(issue("conn-x", "ws-x"))
            nonce = state.split(":")[0]
            ok = asyncio.run(consume(nonce, "conn-x"))
        assert ok is True

    def test_replay_fails(self):
        issue, consume = _import_helpers()
        fake = FakeRedis()
        with patch("api.services.redis_pool.get_redis", return_value=fake):
            state = asyncio.run(issue("c", "w"))
            nonce = state.split(":")[0]
            assert asyncio.run(consume(nonce, "c")) is True
            assert asyncio.run(consume(nonce, "c")) is False

    def test_mismatched_connection_id_rejected(self):
        issue, consume = _import_helpers()
        fake = FakeRedis()
        with patch("api.services.redis_pool.get_redis", return_value=fake):
            state = asyncio.run(issue("conn-A", "ws-1"))
            nonce = state.split(":")[0]
            # Attempt to consume with a DIFFERENT connection_id.
            ok = asyncio.run(consume(nonce, "conn-B"))
        assert ok is False

    def test_short_nonce_rejected(self):
        _, consume = _import_helpers()
        with patch("api.services.redis_pool.get_redis") as m:
            assert asyncio.run(consume("short", "conn")) is False
            m.assert_not_called()

    def test_empty_nonce_rejected(self):
        _, consume = _import_helpers()
        with patch("api.services.redis_pool.get_redis") as m:
            assert asyncio.run(consume("", "conn")) is False
            m.assert_not_called()

    def test_unknown_nonce_fails(self):
        _, consume = _import_helpers()
        fake = FakeRedis()
        with patch("api.services.redis_pool.get_redis", return_value=fake):
            ok = asyncio.run(consume("a" * 40, "any-conn"))
        assert ok is False

    def test_redis_failure_fails_closed(self):
        _, consume = _import_helpers()
        bad = MagicMock()
        bad.getdel = AsyncMock(side_effect=RuntimeError("redis boom"))
        with patch("api.services.redis_pool.get_redis", return_value=bad):
            ok = asyncio.run(consume("x" * 40, "c"))
        assert ok is False
