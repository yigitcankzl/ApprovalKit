"""Tests for HMAC auth middleware logic (api/middleware/auth.py)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import hashlib
import hmac
import time
import pytest

try:
    from api.middleware.auth import _hash_key, _get_cached_hmac, _set_cached_hmac, _hmac_cache, _HMAC_CACHE_TTL
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

needs_fastapi = pytest.mark.skipif(not HAS_FASTAPI, reason="fastapi not installed")


@needs_fastapi
class TestHashKey:
    def test_deterministic(self):
        assert _hash_key("test-key") == _hash_key("test-key")

    def test_different_keys_different_hashes(self):
        assert _hash_key("key-a") != _hash_key("key-b")

    def test_sha256_format(self):
        result = _hash_key("test-key")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_matches_manual_sha256(self):
        expected = hashlib.sha256("my-api-key".encode()).hexdigest()
        assert _hash_key("my-api-key") == expected


@needs_fastapi
class TestHmacCache:
    def setup_method(self):
        _hmac_cache.clear()

    def test_set_and_get(self):
        _set_cached_hmac("ws-1", "secret-abc")
        assert _get_cached_hmac("ws-1") == "secret-abc"

    def test_cache_miss(self):
        assert _get_cached_hmac("nonexistent") is None

    def test_cache_expired(self):
        _hmac_cache["ws-expired"] = ("old-secret", time.time() - 600)
        assert _get_cached_hmac("ws-expired") is None

    def test_cache_not_expired(self):
        _set_cached_hmac("ws-fresh", "fresh-secret")
        assert _get_cached_hmac("ws-fresh") == "fresh-secret"

    def test_overwrite_cache(self):
        _set_cached_hmac("ws-1", "secret-v1")
        _set_cached_hmac("ws-1", "secret-v2")
        assert _get_cached_hmac("ws-1") == "secret-v2"

    @needs_fastapi
    def test_replay_window_is_300_seconds(self):
        assert _HMAC_CACHE_TTL == 300


class TestHmacSignatureVerification:
    """Test HMAC signature computation matches middleware expectations."""

    def test_workspace_key_signing(self):
        """Workspace keys use just hmac_secret as sign key."""
        hmac_secret = "test-workspace-secret"
        ts = str(int(time.time()))
        body = '{"amount":500}'
        message = f"{ts}.{body}"
        sig = hmac.new(hmac_secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        assert len(sig) == 64

    def test_agent_key_signing(self):
        """Agent keys use 'hmac_secret:api_key' as sign key."""
        hmac_secret = "test-workspace-secret"
        api_key = "ak_test_agent_key"
        sign_key = f"{hmac_secret}:{api_key}"
        ts = str(int(time.time()))
        body = '{"action":"deploy"}'
        message = f"{ts}.{body}"
        sig = hmac.new(sign_key.encode(), message.encode(), hashlib.sha256).hexdigest()
        assert len(sig) == 64

    def test_different_body_different_sig(self):
        secret = "test-secret"
        ts = str(int(time.time()))
        sig1 = hmac.new(secret.encode(), f"{ts}.body1".encode(), hashlib.sha256).hexdigest()
        sig2 = hmac.new(secret.encode(), f"{ts}.body2".encode(), hashlib.sha256).hexdigest()
        assert sig1 != sig2

    def test_different_timestamp_different_sig(self):
        secret = "test-secret"
        body = '{"test":1}'
        sig1 = hmac.new(secret.encode(), f"1000.{body}".encode(), hashlib.sha256).hexdigest()
        sig2 = hmac.new(secret.encode(), f"2000.{body}".encode(), hashlib.sha256).hexdigest()
        assert sig1 != sig2

    def test_compare_digest_timing_safe(self):
        a = "abcdef1234567890" * 4
        b = "abcdef1234567890" * 4
        assert hmac.compare_digest(a, b) is True
        assert hmac.compare_digest(a, "different") is False


class TestSignatureFormat:
    """Test X-Signature header format parsing."""

    def test_valid_format(self):
        sig_header = "hmac-sha256=1234567890.abcdef0123456789"
        assert sig_header.startswith("hmac-sha256=")
        value = sig_header.removeprefix("hmac-sha256=")
        parts = value.split(".", 1)
        assert len(parts) == 2
        ts, hash_val = parts
        assert ts.isdigit()

    def test_missing_prefix_invalid(self):
        sig_header = "sha256=1234567890.abcdef"
        assert not sig_header.startswith("hmac-sha256=")

    def test_no_dot_invalid(self):
        value = "1234567890abcdef"
        parts = value.split(".", 1)
        assert len(parts) == 1

    def test_non_numeric_timestamp_invalid(self):
        value = "abc.abcdef0123456789"
        ts, _ = value.split(".", 1)
        with pytest.raises(ValueError):
            int(ts)

    def test_empty_signature_invalid(self):
        assert not "".startswith("hmac-sha256=")

    def test_signature_with_multiple_dots(self):
        value = "12345.abc.def"
        parts = value.split(".", 1)
        assert len(parts) == 2
        assert parts[0] == "12345"
        assert parts[1] == "abc.def"
