"""Service reachability probes used for chat pre-flight checks."""

import time
from collections.abc import Awaitable, Callable

from loguru import logger

from app.core.http_client import create_http_client

_HEALTHY_TTL = 20.0
_UNHEALTHY_TTL = 5.0


class TTLHealthCache:
    """TTL cache for reachability probes.

    Healthy entries live longer than unhealthy ones: a healthy service adds
    ~zero latency per request (cached hit), while a down service still fails
    fast (unhealthy TTL) without being hammered by every request.
    """

    def __init__(self, healthy_ttl: float = _HEALTHY_TTL, unhealthy_ttl: float = _UNHEALTHY_TTL) -> None:
        self._healthy_ttl = healthy_ttl
        self._unhealthy_ttl = unhealthy_ttl
        self._cache: tuple[bool, float] | None = None

    def get(self) -> bool | None:
        """Return the cached verdict when fresh, else None."""
        if self._cache is None:
            return None
        healthy, checked_at = self._cache
        ttl = self._healthy_ttl if healthy else self._unhealthy_ttl
        if time.monotonic() - checked_at < ttl:
            return healthy
        return None

    def set(self, healthy: bool) -> None:
        self._cache = (healthy, time.monotonic())


async def ping_openai_endpoint(base_url: str, timeout: float = 2.0) -> bool:
    """Reachability probe for an OpenAI-compatible endpoint (``GET /models``).

    Any HTTP response proves the server answers — status codes like 401/404
    still mean reachable. Only connection/timeout failures count as down.
    Two attempts with escalating timeouts (2s → 6s) absorb brief network
    blips and cold tunnel starts. Never raises.
    """
    url = f"{base_url.rstrip('/')}/models"
    for attempt in range(2):
        try:
            async with create_http_client(timeout=timeout * (3**attempt)) as client:
                await client.get(url)
            return True
        except Exception as exc:
            if attempt == 1:
                logger.warning("ping_failed url={} error={}", url, repr(exc))
    return False


async def probe_with_cache(probe: Callable[[], Awaitable[bool]], cache: TTLHealthCache) -> bool:
    """Run *probe* honoring the TTL cache: fresh hits skip the network call."""
    cached = cache.get()
    if cached is not None:
        return cached
    healthy = await probe()
    cache.set(healthy)
    return healthy
