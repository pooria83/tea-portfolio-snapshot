"""Parse a raw HTTP request header block pasted from the browser DevTools.

The admin panel stores the block verbatim (as pasted). The scraper parses it
into a cookie string plus the remaining browser headers (User-Agent, Referer,
Sec-Fetch-*, ...) which Akamai expects on curl_cffi requests.
"""

from __future__ import annotations

import http.cookies
from typing import Any

HOP_BY_HOP = frozenset(
    {
        "host",
        "connection",
        "content-length",
        "transfer-encoding",
        "te",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "trailer",
        "upgrade",
        "proxy-connection",
    }
)


def parse_raw_headers(raw: str) -> dict[str, str]:
    """Parse a raw header block into a ``{name: value}`` map.

    Skips the HTTP request line (``GET /... HTTP/2``) and hop-by-hop headers
    that the HTTP client manages itself (Host, Connection, Content-Length, TE).
    """
    headers: dict[str, str] = {}
    for line in raw.splitlines():
        stripped = line.rstrip("\r")
        if not stripped.strip():
            continue
        if ":" not in stripped:
            continue
        name, _, value = stripped.partition(":")
        name = name.strip()
        value = value.strip()
        if not name or name.lower() in HOP_BY_HOP:
            continue
        headers[name] = value
    return headers


def get_header(headers: dict[str, str], name: str) -> str | None:
    """Case-insensitive header lookup."""
    lower = name.lower()
    for key, value in headers.items():
        if key.lower() == lower:
            return value
    return None


def extract_cookie_string(headers: dict[str, str]) -> str | None:
    """Return the ``Cookie:`` value, or None when absent."""
    return get_header(headers, "Cookie")


def count_cookies(headers: dict[str, str]) -> int:
    cookie = extract_cookie_string(headers)
    if not cookie:
        return 0
    return len(http.cookies.SimpleCookie(cookie))


def validate_header_block(raw: str) -> dict[str, Any]:
    """Validate a raw header block and return parsing metadata.

    Raises ValueError with a human-readable reason when the block is unusable.
    """
    if not raw or not raw.strip():
        raise ValueError("Header block is empty")
    headers = parse_raw_headers(raw)
    cookie = extract_cookie_string(headers)
    if cookie is None:
        raise ValueError("Header block has no Cookie header")
    return {
        "headers": headers,
        "cookie": cookie,
        "cookie_count": len(http.cookies.SimpleCookie(cookie)),
        "has_access_token": "access_token=" in cookie,
        "header_names": sorted(headers.keys()),
    }
