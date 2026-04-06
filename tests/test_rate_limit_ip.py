"""Tests for api/middleware/rate_limit.py IP extraction with trusted proxies."""
import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("HMAC_SECRET", "ratelimit-test")

from unittest.mock import MagicMock

from api.config import get_settings
from api.middleware import rate_limit


def _make_request(peer_ip="203.0.113.7", xff=None):
    req = MagicMock()
    req.headers = {}
    if xff is not None:
        req.headers = {"X-Forwarded-For": xff}
    req.client = MagicMock()
    req.client.host = peer_ip
    return req


def _set_trusted_proxy_count(n: int):
    os.environ["TRUSTED_PROXY_COUNT"] = str(n)
    get_settings.cache_clear()
    importlib.reload(rate_limit)


class TestClientIpExtraction:
    def test_no_proxy_ignores_xff(self):
        _set_trusted_proxy_count(0)
        req = _make_request(peer_ip="1.2.3.4", xff="9.9.9.9")
        assert rate_limit._client_ip(req) == "1.2.3.4"

    def test_no_proxy_missing_client_returns_unknown(self):
        _set_trusted_proxy_count(0)
        req = MagicMock()
        req.headers = {"X-Forwarded-For": "9.9.9.9"}
        req.client = None
        assert rate_limit._client_ip(req) == "unknown"

    def test_one_trusted_proxy_takes_rightmost_xff(self):
        """With 1 trusted proxy, the last entry in XFF is the proxy's
        view of the real client."""
        _set_trusted_proxy_count(1)
        req = _make_request(peer_ip="10.0.0.1", xff="203.0.113.7")
        assert rate_limit._client_ip(req) == "203.0.113.7"

    def test_attacker_prepend_cannot_spoof_with_one_proxy(self):
        """Attacker sets XFF: evil. Proxy appends real IP. With 1 trusted
        hop we take the entry at index len-1 (the proxy's addition)."""
        _set_trusted_proxy_count(1)
        req = _make_request(
            peer_ip="10.0.0.1",
            xff="1.2.3.4, 5.6.7.8",  # attacker added "1.2.3.4"
        )
        assert rate_limit._client_ip(req) == "5.6.7.8"

    def test_two_trusted_proxies(self):
        _set_trusted_proxy_count(2)
        req = _make_request(
            peer_ip="10.0.0.1",
            xff="spoofed, real-client, proxy1",
        )
        # With 2 trusted hops, idx = len-2 = 1.
        assert rate_limit._client_ip(req) == "real-client"

    def test_xff_shorter_than_trusted_count_falls_back_to_peer(self):
        _set_trusted_proxy_count(3)
        req = _make_request(peer_ip="10.0.0.1", xff="only-one")
        # idx = 1 - 3 = -2 → out of bounds → fall back to peer.
        assert rate_limit._client_ip(req) == "10.0.0.1"

    def test_empty_xff_with_trusted_proxy_falls_back(self):
        _set_trusted_proxy_count(1)
        req = _make_request(peer_ip="10.0.0.1", xff="")
        assert rate_limit._client_ip(req) == "10.0.0.1"

    def test_no_xff_header_at_all(self):
        _set_trusted_proxy_count(1)
        req = _make_request(peer_ip="10.0.0.1")
        assert rate_limit._client_ip(req) == "10.0.0.1"

    def test_xff_whitespace_stripped(self):
        _set_trusted_proxy_count(1)
        req = _make_request(peer_ip="10.0.0.1", xff="  203.0.113.7  ")
        assert rate_limit._client_ip(req) == "203.0.113.7"

    def test_xff_with_empty_segments_ignored(self):
        _set_trusted_proxy_count(1)
        req = _make_request(peer_ip="10.0.0.1", xff=", , 203.0.113.7")
        assert rate_limit._client_ip(req) == "203.0.113.7"

    def teardown_method(self):
        _set_trusted_proxy_count(0)
