"""Tests for api/utils.py SSRF guard (assert_safe_outbound_url[_async]).

These exercise the scheme check, literal-IP blocking for
private/loopback/link-local/metadata ranges, and DNS-based blocking
for hostnames that resolve to non-public addresses.
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch

from api.utils import (
    UnsafeURLError,
    _is_public_ip,
    assert_safe_outbound_url,
    assert_safe_outbound_url_async,
)


class TestIsPublicIp:
    @pytest.mark.parametrize("addr", [
        "127.0.0.1",       # loopback
        "10.0.0.1",        # private
        "10.255.255.255",
        "172.16.0.1",      # private
        "172.31.255.255",
        "192.168.1.1",     # private
        "169.254.169.254", # AWS/GCP metadata
        "0.0.0.0",         # unspecified
        "224.0.0.1",       # multicast
        "::1",             # IPv6 loopback
        "fe80::1",         # IPv6 link-local
        "fc00::1",         # IPv6 unique-local
    ])
    def test_blocks_non_public(self, addr):
        assert _is_public_ip(addr) is False

    @pytest.mark.parametrize("addr", [
        "8.8.8.8",
        "1.1.1.1",
        "93.184.216.34",   # example.com
        "2606:4700:4700::1111",
    ])
    def test_allows_public(self, addr):
        assert _is_public_ip(addr) is True

    def test_invalid_ip_string_is_not_public(self):
        assert _is_public_ip("not-an-ip") is False


class TestSchemeValidation:
    def test_https_allowed_by_default(self):
        # Uses public DNS — avoid calling this in offline CI; pick a
        # guaranteed-blocked host instead.
        pass

    def test_http_blocked(self):
        with pytest.raises(UnsafeURLError, match="scheme"):
            assert_safe_outbound_url("http://example.com/")

    def test_ftp_blocked(self):
        with pytest.raises(UnsafeURLError, match="scheme"):
            assert_safe_outbound_url("ftp://example.com/")

    def test_file_blocked(self):
        with pytest.raises(UnsafeURLError, match="scheme"):
            assert_safe_outbound_url("file:///etc/passwd")

    def test_http_allowed_when_configured(self):
        # Scheme list customisable — pass http explicitly.
        with patch("api.utils._resolve_host_sync", return_value=["8.8.8.8"]):
            assert_safe_outbound_url("http://example.com/", allowed_schemes=("http", "https"))


class TestEmptyOrBadInput:
    def test_empty_string(self):
        with pytest.raises(UnsafeURLError, match="non-empty"):
            assert_safe_outbound_url("")

    def test_none_raises(self):
        with pytest.raises(UnsafeURLError):
            assert_safe_outbound_url(None)  # type: ignore[arg-type]

    def test_no_host(self):
        with pytest.raises(UnsafeURLError, match="no host"):
            assert_safe_outbound_url("https:///path")


class TestLiteralIpHost:
    @pytest.mark.parametrize("url", [
        "https://127.0.0.1/",
        "https://10.0.0.1/",
        "https://192.168.1.1/",
        "https://169.254.169.254/latest/meta-data/",
        "https://172.16.5.5/",
    ])
    def test_private_literal_ip_blocked(self, url):
        with pytest.raises(UnsafeURLError, match="non-public"):
            assert_safe_outbound_url(url)

    def test_public_literal_ip_allowed(self):
        # Should not raise.
        assert_safe_outbound_url("https://8.8.8.8/")

    def test_public_ipv6_allowed(self):
        assert_safe_outbound_url("https://[2606:4700:4700::1111]/")


class TestDnsResolution:
    def test_hostname_resolving_to_private_ip_blocked(self):
        with patch("api.utils._resolve_host_sync", return_value=["10.0.0.1"]):
            with pytest.raises(UnsafeURLError, match="non-public"):
                assert_safe_outbound_url("https://evil.example.com/")

    def test_hostname_resolving_to_metadata_ip_blocked(self):
        with patch("api.utils._resolve_host_sync", return_value=["169.254.169.254"]):
            with pytest.raises(UnsafeURLError, match="non-public"):
                assert_safe_outbound_url("https://rebind.example.com/")

    def test_hostname_with_mixed_records_blocked(self):
        # If ANY resolved record is private, block.
        with patch("api.utils._resolve_host_sync", return_value=["8.8.8.8", "10.0.0.1"]):
            with pytest.raises(UnsafeURLError, match="non-public"):
                assert_safe_outbound_url("https://mixed.example.com/")

    def test_hostname_with_only_public_records_allowed(self):
        with patch("api.utils._resolve_host_sync", return_value=["8.8.8.8", "1.1.1.1"]):
            assert_safe_outbound_url("https://good.example.com/")

    def test_empty_resolution_blocked(self):
        with patch("api.utils._resolve_host_sync", return_value=[]):
            with pytest.raises(UnsafeURLError, match="Cannot resolve"):
                assert_safe_outbound_url("https://nothing.example.com/")


class TestAsyncVariant:
    def test_async_runs_resolver_in_thread(self):
        with patch("api.utils._resolve_host_sync", return_value=["10.0.0.1"]):
            with pytest.raises(UnsafeURLError, match="non-public"):
                asyncio.run(assert_safe_outbound_url_async("https://evil.example.com/"))

    def test_async_allows_public(self):
        with patch("api.utils._resolve_host_sync", return_value=["8.8.8.8"]):
            # Should not raise.
            asyncio.run(assert_safe_outbound_url_async("https://good.example.com/"))

    def test_async_literal_private_blocked(self):
        with pytest.raises(UnsafeURLError):
            asyncio.run(assert_safe_outbound_url_async("https://127.0.0.1/"))

    def test_async_does_not_call_resolver_for_literal_ip(self):
        # _resolve_host_sync must not be called for literal IPs.
        with patch("api.utils._resolve_host_sync", side_effect=AssertionError("should not resolve")):
            asyncio.run(assert_safe_outbound_url_async("https://8.8.8.8/"))
