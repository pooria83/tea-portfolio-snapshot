"""Shared Redis cache invalidation for seed scripts.

Seed scripts write to the database directly (``session.add`` / raw ``text``
SQL), bypassing the repository write methods that normally invalidate Redis.
After seeding, scripts should call :func:`invalidate_seed_cache` with the set
of touched tables so stale cached DTOs are dropped.
"""

from redis.asyncio import Redis

from app.core.cache import invalidate_tables
from app.core.config import settings


async def invalidate_seed_cache(tables: set[str]) -> None:
    try:
        redis = Redis.from_url(str(settings.redis_url))
        try:
            await invalidate_tables(redis, tables)
        finally:
            await redis.aclose()
    except Exception as exc:  # noqa: BLE001 - seeding must never fail on cache
        print(f"WARNING: Redis cache invalidation failed after seeding: {exc}")
