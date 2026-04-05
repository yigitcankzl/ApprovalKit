"""Tests for email approval tokens (api/services/email_approval.py).

Covers:
 - HMAC signature generation + verification
 - Tamper rejection
 - Expiry handling
 - Single-use Redis-backed consume (replay protection)
 - Fail-closed on Redis failure
"""
import asyncio
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required env vars BEFORE importing the module under test.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("HMAC_SECRET", "test-hmac-secret-for-tokens")

from unittest.mock import AsyncMock, MagicMock, patch

from api.services.email_approval import (
    _generate_approval_token,
    _token_fingerprint,
    consume_approval_token,
    verify_approval_token,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if (
        asyncio.get_event_loop_policy().get_event_loop().is_running() is False
    ) else asyncio.run(coro)


class TestTokenGeneration:
    def test_token_roundtrip(self):
        tok = _generate_approval_token("job-1", "alice@example.com", expires_in=60)
        claims = verify_approval_token(tok)
        assert claims is not None
        assert claims["job_id"] == "job-1"
        assert claims["approver_email"] == "alice@example.com"
        assert claims["expiry"] > int(time.time())

    def test_different_inputs_give_different_tokens(self):
        a = _generate_approval_token("job-1", "a@x.com", 60)
        b = _generate_approval_token("job-2", "a@x.com", 60)
        assert a != b

    def test_token_has_four_colon_segments(self):
        tok = _generate_approval_token("job-1", "a@x.com", 60)
        # job_id:email:expiry:signature
        assert tok.count(":") == 3


class TestVerifyApprovalToken:
    def test_valid_token_returns_claims(self):
        tok = _generate_approval_token("j1", "u@x.com", 60)
        assert verify_approval_token(tok) is not None

    def test_tampered_signature_rejected(self):
        tok = _generate_approval_token("j1", "u@x.com", 60)
        # Flip last two chars of the signature.
        tampered = tok[:-2] + ("00" if tok[-2:] != "00" else "11")
        assert verify_approval_token(tampered) is None

    def test_tampered_payload_rejected(self):
        tok = _generate_approval_token("j1", "u@x.com", 60)
        parts = tok.split(":")
        # Change job id — the signature no longer matches.
        parts[0] = "j2"
        bad = ":".join(parts)
        assert verify_approval_token(bad) is None

    def test_missing_signature_rejected(self):
        assert verify_approval_token("just-a-payload") is None

    def test_wrong_segment_count_rejected(self):
        assert verify_approval_token("a:b:c:d:e:f") is None

    def test_expired_token_rejected(self):
        tok = _generate_approval_token("j1", "u@x.com", expires_in=-10)
        assert verify_approval_token(tok) is None

    def test_empty_string_rejected(self):
        assert verify_approval_token("") is None


class TestTokenFingerprint:
    def test_sha256_length(self):
        fp = _token_fingerprint("anything")
        assert len(fp) == 64

    def test_deterministic(self):
        assert _token_fingerprint("abc") == _token_fingerprint("abc")

    def test_different_inputs_different_fps(self):
        assert _token_fingerprint("a") != _token_fingerprint("b")


class TestConsumeApprovalToken:
    def test_rejects_invalid_token_without_touching_redis(self):
        # No Redis mock — must not reach Redis if signature fails.
        with patch("api.services.email_approval.get_redis") as mock_get_redis:
            result = asyncio.run(consume_approval_token("bogus-token"))
            assert result is None
            mock_get_redis.assert_not_called()

    def test_first_use_succeeds(self):
        tok = _generate_approval_token("j-ok", "u@x.com", 60)
        fake = MagicMock()
        fake.set = AsyncMock(return_value=True)  # SET NX success
        with patch("api.services.email_approval.get_redis", return_value=fake):
            result = asyncio.run(consume_approval_token(tok))
        assert result is not None
        assert result["job_id"] == "j-ok"
        fake.set.assert_awaited_once()
        # Key must be used_token:{sha256} — not the raw token.
        call_args = fake.set.call_args
        key = call_args.args[0] if call_args.args else call_args.kwargs.get("name")
        assert key.startswith("used_token:")
        assert tok not in key  # raw token not stored

    def test_replay_rejected(self):
        tok = _generate_approval_token("j-replay", "u@x.com", 60)
        fake = MagicMock()
        fake.set = AsyncMock(return_value=None)  # SET NX collision
        with patch("api.services.email_approval.get_redis", return_value=fake):
            result = asyncio.run(consume_approval_token(tok))
        assert result is None

    def test_redis_failure_fails_closed(self):
        tok = _generate_approval_token("j-fail", "u@x.com", 60)
        fake = MagicMock()
        fake.set = AsyncMock(side_effect=RuntimeError("redis down"))
        with patch("api.services.email_approval.get_redis", return_value=fake):
            result = asyncio.run(consume_approval_token(tok))
        assert result is None  # fail-closed

    def test_ttl_matches_token_expiry(self):
        tok = _generate_approval_token("j-ttl", "u@x.com", expires_in=120)
        fake = MagicMock()
        fake.set = AsyncMock(return_value=True)
        with patch("api.services.email_approval.get_redis", return_value=fake):
            asyncio.run(consume_approval_token(tok))
        ttl = fake.set.call_args.kwargs.get("ex")
        # Expiry ~120s from now + 60s grace ⇒ ttl between 150 and 200.
        assert 100 < ttl <= 200

    def test_nx_flag_used(self):
        tok = _generate_approval_token("j-nx", "u@x.com", 60)
        fake = MagicMock()
        fake.set = AsyncMock(return_value=True)
        with patch("api.services.email_approval.get_redis", return_value=fake):
            asyncio.run(consume_approval_token(tok))
        assert fake.set.call_args.kwargs.get("nx") is True
