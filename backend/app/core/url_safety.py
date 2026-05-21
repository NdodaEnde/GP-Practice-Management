"""SSRF guard for outbound requests to user-supplied URLs (e.g. a workspace's
FHIR server URL). Blocks requests that resolve to private / loopback /
link-local / reserved address space — notably the cloud metadata endpoint
(169.254.169.254) which can leak instance credentials.

Use BEFORE any httpx call to a caller-controlled URL, and pair with
follow_redirects=False so a public host can't 302 to an internal one.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURLError(ValueError):
    """Raised when a URL is not safe to fetch (bad scheme or internal target)."""


def assert_safe_external_url(url: str) -> None:
    """Raise UnsafeURLError unless `url` is an http(s) URL whose host resolves
    only to public, routable addresses."""
    if not url or not isinstance(url, str):
        raise UnsafeURLError("empty URL")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError(f"scheme must be http/https, got {parsed.scheme!r}")

    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL has no host")

    # Resolve every address the host maps to; reject if ANY is non-public
    # (defends against a hostname that points at an internal IP).
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as e:
        raise UnsafeURLError(f"could not resolve host {host!r}: {e}")

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            raise UnsafeURLError(f"unresolvable address {ip_str!r}")
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise UnsafeURLError(
                f"host {host!r} resolves to a non-public address ({ip_str}) — refused (SSRF guard)"
            )
