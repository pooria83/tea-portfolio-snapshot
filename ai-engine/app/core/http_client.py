"""Shared HTTP client helpers.

The host environment may export proxy variables (e.g. ALL_PROXY=socks://127.0.0.1:10808)
which httpx picks up by default and fails on (unknown scheme / socks support missing).
All outbound clients must opt out of environment proxies via trust_env=False.
"""

from typing import Any

import httpx
import httpx2
from openai import AsyncOpenAI

OPENCODE_OPENAI_USER_AGENT = "opencode/1.18.23 ai-sdk/provider-utils/4.0.23 runtime/bun/1.3.14"


def create_openai_client(*, api_key: str, base_url: str, timeout: float = 60.0) -> AsyncOpenAI:
    """Build an AsyncOpenAI client that ignores environment proxy variables.

    OpenCode Zen's free-tier gate keys off the ``User-Agent`` header — requests
    that do not present the opencode UA are rejected with 429
    ``FreeUsageLimitError``. The UA mirrors the opencode CLI's exact string.

    openai >= 3 vendors its own httpx fork (httpx2) for transport; the client
    must be built from that fork so `trust_env=False` still applies.
    """
    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        default_headers={"User-Agent": OPENCODE_OPENAI_USER_AGENT},
        http_client=httpx2.AsyncClient(trust_env=False),
        timeout=timeout,
    )


def create_http_client(**kwargs: Any) -> httpx.AsyncClient:
    """Build an httpx client that ignores environment proxy variables.

    A default 30s timeout guards against hung outbound calls; callers may
    override it.
    """
    kwargs.setdefault("timeout", 30.0)
    return httpx.AsyncClient(trust_env=False, **kwargs)
