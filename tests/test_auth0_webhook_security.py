"""Tests for Auth0 webhook signature + replay protection."""
import asyncio
import hashlib
import hmac
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ["HMAC_SECRET"] = "webhook-hmac-secret"

from unittest.mock import AsyncMock, MagicMock, patch

import importlib
from api.config import get_settings
get_settings.cache_clear()
from api.routes import auth0_webhook
importlib.reload(auth0_webhook)


def _sign(secret: str, body: bytes, timestamp: str) -> str:
    msg = timestamp.encode() + b"." + body
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


class TestVerifySignature:
    def test_valid_signature_accepted(self):
        body = b'{"event":"x"}'
        ts = str(int(time.time()))
        sig = _sign("webhook-hmac-secret", body, ts)
        assert auth0_webhook._verify_signature(body, sig, ts) is True

    def test_wrong_secret_rejected(self):
        body = b'{"event":"x"}'
        ts = str(int(time.time()))
        sig = _sign("different-secret", body, ts)
        assert auth0_webhook._verify_signature(body, sig, ts) is False

    def test_tampered_body_rejected(self):
        body = b'{"event":"legit"}'
        ts = str(int(time.time()))
        sig = _sign("webhook-hmac-secret", body, ts)
        # Change body after signing.
        tampered = b'{"event":"evil"}'
        assert auth0_webhook._verify_signature(tampered, sig, ts) is False

    def test_tampered_timestamp_rejected(self):
        """An attacker who takes a valid (body, sig) cannot freshen the
        request by changing the timestamp — because the timestamp is
        bound INTO the HMAC."""
        body = b'{"x":1}'
        ts = "1000"
        sig = _sign("webhook-hmac-secret", body, ts)
        # Use the SAME (body, sig) but a different timestamp.
        assert auth0_webhook._verify_signature(body, sig, "2000") is False

    def test_empty_secret_rejects_all(self):
        body = b'{"x":1}'
        ts = str(int(time.time()))
        with patch.object(auth0_webhook.settings, "HMAC_SECRET", ""):
            sig = _sign("", body, ts)
            # Even a valid MAC over the empty secret must be rejected.
            assert auth0_webhook._verify_signature(body, sig, ts) is False


class TestNonceReplay:
    def test_first_use_returns_false_not_seen(self):
        fake = MagicMock()
        fake.set = AsyncMock(return_value=True)  # SET NX success
        with patch("api.routes.auth0_webhook.get_redis", return_value=fake):
            seen = asyncio.run(auth0_webhook._nonce_seen("nonce-abc"))
        assert seen is False
        fake.set.assert_awaited_once()
        # Must use nx=True
        assert fake.set.call_args.kwargs.get("nx") is True

    def test_replay_detected(self):
        fake = MagicMock()
        fake.set = AsyncMock(return_value=None)  # SETNX collision
        with patch("api.routes.auth0_webhook.get_redis", return_value=fake):
            seen = asyncio.run(auth0_webhook._nonce_seen("nonce-abc"))
        assert seen is True

    def test_redis_failure_fails_closed(self):
        fake = MagicMock()
        fake.set = AsyncMock(side_effect=RuntimeError("redis down"))
        with patch("api.routes.auth0_webhook.get_redis", return_value=fake):
            seen = asyncio.run(auth0_webhook._nonce_seen("anything"))
        assert seen is True  # fail-closed: treat as replay

    def test_empty_nonce_returns_false(self):
        # Empty nonce means caller forgot to pass one — treat as not
        # seen so callers can decide to reject via a separate check.
        with patch("api.routes.auth0_webhook.get_redis") as m:
            seen = asyncio.run(auth0_webhook._nonce_seen(""))
        assert seen is False
        m.assert_not_called()
