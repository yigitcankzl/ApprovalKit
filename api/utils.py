"""Shared utility functions."""
import ipaddress
import socket
from datetime import time
from urllib.parse import urlparse


def parse_time(t: str | None) -> time | None:
    """Parse 'HH:MM' string to time object."""
    if not t:
        return None
    parts = t.split(":")
    return time(int(parts[0]), int(parts[1]))


class UnsafeURLError(ValueError):
    """Raised when a user-supplied URL points at a disallowed host."""


def _is_public_ip(addr: str) -> bool:
    """Return True only for globally-routable public IPs."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    # is_global excludes private, loopback, link-local, multicast, reserved,
    # unspecified, and the AWS/GCP metadata ranges.
    return ip.is_global


def assert_safe_outbound_url(url: str, *, allowed_schemes: tuple[str, ...] = ("https",)) -> None:
    """
    Validate a user-supplied URL for outbound HTTP calls (SSRF guard).

    Blocks:
      - non-allowed schemes (default: https only)
      - missing/empty hostname
      - literal private / loopback / link-local / metadata IPs
      - hostnames that resolve to any non-public IP

    Raises UnsafeURLError on any violation.
    """
    if not url or not isinstance(url, str):
        raise UnsafeURLError("URL must be a non-empty string")

    parsed = urlparse(url)
    if parsed.scheme.lower() not in allowed_schemes:
        raise UnsafeURLError(f"URL scheme must be one of {allowed_schemes}")
    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL has no host")

    # If the host is a literal IP, check directly.
    try:
        ipaddress.ip_address(host)
        if not _is_public_ip(host):
            raise UnsafeURLError(f"URL host resolves to non-public address: {host}")
        return
    except ValueError:
        pass  # not a literal IP, fall through to DNS

    # Resolve hostname → ensure every A/AAAA record is public.
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise UnsafeURLError(f"Cannot resolve host {host!r}: {e}") from e

    for info in infos:
        addr = info[4][0]
        if not _is_public_ip(addr):
            raise UnsafeURLError(f"Host {host!r} resolves to non-public IP: {addr}")
