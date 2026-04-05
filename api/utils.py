"""Shared utility functions."""
import asyncio
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
    """Return True only for globally-routable public unicast IPs.

    Explicitly rejects multicast and reserved ranges — Python's
    ``is_global`` considers multicast addresses global, which would
    let a webhook URL resolve to e.g. 224.0.0.1.
    """
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return False
    return ip.is_global


def _parse_and_check_scheme(url: str, allowed_schemes: tuple[str, ...]) -> str:
    if not url or not isinstance(url, str):
        raise UnsafeURLError("URL must be a non-empty string")
    parsed = urlparse(url)
    if parsed.scheme.lower() not in allowed_schemes:
        raise UnsafeURLError(f"URL scheme must be one of {allowed_schemes}")
    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL has no host")
    return host


def _check_resolved_addrs(host: str, addrs: list[str]) -> None:
    for addr in addrs:
        if not _is_public_ip(addr):
            raise UnsafeURLError(f"Host {host!r} resolves to non-public IP: {addr}")
    if not addrs:
        raise UnsafeURLError(f"Cannot resolve host {host!r}")


def _resolve_host_sync(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise UnsafeURLError(f"Cannot resolve host {host!r}: {e}") from e
    return [info[4][0] for info in infos]


def assert_safe_outbound_url(url: str, *, allowed_schemes: tuple[str, ...] = ("https",)) -> None:
    """
    Validate a user-supplied URL for outbound HTTP calls (SSRF guard).

    Blocks:
      - non-allowed schemes (default: https only)
      - missing/empty hostname
      - literal private / loopback / link-local / metadata IPs
      - hostnames that resolve to any non-public IP

    Raises UnsafeURLError on any violation.

    WARNING: this is a TOCTOU check — DNS may rebind between validate
    and fetch. Use ``resolve_safe_outbound_url`` to both validate AND
    get back a pinned IP that the caller can connect to.
    """
    host = _parse_and_check_scheme(url, allowed_schemes)
    # Literal IP — check directly.
    try:
        ipaddress.ip_address(host)
        if not _is_public_ip(host):
            raise UnsafeURLError(f"URL host resolves to non-public address: {host}")
        return
    except ValueError:
        pass
    _check_resolved_addrs(host, _resolve_host_sync(host))


async def assert_safe_outbound_url_async(
    url: str, *, allowed_schemes: tuple[str, ...] = ("https",)
) -> None:
    """Async variant of ``assert_safe_outbound_url``. Runs DNS in a thread
    so the event loop is not blocked."""
    host = _parse_and_check_scheme(url, allowed_schemes)
    try:
        ipaddress.ip_address(host)
        if not _is_public_ip(host):
            raise UnsafeURLError(f"URL host resolves to non-public address: {host}")
        return
    except ValueError:
        pass
    addrs = await asyncio.to_thread(_resolve_host_sync, host)
    _check_resolved_addrs(host, addrs)
