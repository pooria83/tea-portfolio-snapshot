"""SSRF protection for outbound webhook URLs.

``/embed-product`` accepts a caller-supplied ``webhook_url`` that is POSTed
by the engine. Without validation an attacker could point it at internal
services (Qdrant, Postgres, cloud metadata endpoints). This module validates
that a URL is safe to POST to: HTTPS-only, no userinfo, host resolved to a
public IP (with a DNS-rebinding re-check), and no redirects followed.
"""

import ipaddress
import socket
from urllib.parse import urlparse

from loguru import logger

ALLOWED_SCHEMES = {"https"}

# Addresses that must never be reachable as webhook targets.
BLOCKED_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def is_safe_webhook_url(url: str) -> bool:
    """Return True when *url* is safe to POST as a webhook target."""
    if not url or len(url) > 2048:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ALLOWED_SCHEMES:
        logger.warning("SSRF_REJECTED scheme={} url={}", parsed.scheme, url)
        return False
    if parsed.username is not None or parsed.password is not None:
        logger.warning("SSRF_REJECTED userinfo url={}", url)
        return False
    hostname = parsed.hostname
    if not hostname:
        logger.warning("SSRF_REJECTED no_host url={}", url)
        return False
    if not _is_public_host(hostname):
        logger.warning("SSRF_REJECTED host={} url={}", hostname, url)
        return False
    return True


def _is_public_host(hostname: str) -> bool:
    """Resolve *hostname* and reject any non-public address (DNS-rebinding safe).

    Re-resolves the hostname immediately before the connection is made so a
    DNS answer that changes between the check and the request is caught.
    """
    try:
        addrinfo = socket.getaddrinfo(hostname, None, family=socket.AF_UNSPEC)
    except socket.gaierror:
        logger.warning("SSRF_REJECTED dns_failure host={}", hostname)
        return False
    for entry in addrinfo:
        sockaddr = entry[4]
        ip = sockaddr[0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if addr.is_loopback or addr.is_link_local or addr.is_private or addr.is_unspecified:
            return False
        if any(addr in network for network in BLOCKED_NETWORKS):
            return False
    return True
