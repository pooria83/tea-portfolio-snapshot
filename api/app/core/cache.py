"""Redis cache layer — key registry + helpers.

All cache key prefixes and their TTLs live in :class:`CacheKeys` (one source
of truth); a :class:`CacheKey` carries both the prefix and its TTL so they
can never drift apart. Repositories reference ``CacheKeys.X`` when reading
or writing cache entries, and writes invalidate cached reads via the
``TOUCHES`` -> ``PREFIX_BY_TABLE`` mapping. Every helper is fail-open: a
Redis error is logged and the caller falls back to the database so caching
never breaks a request.
"""

import asyncio
import contextlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

from loguru import logger
from redis.asyncio import Redis as AsyncRedis


@dataclass(frozen=True, slots=True)
class CacheKey:
    """A Redis cache key definition: its prefix and the TTL in seconds."""

    prefix: str
    ttl: int


_TABLE_TO_PREFIXES: dict[str, tuple[str, ...]] = {
    "system_settings": ("sys:settings:", "sys:setting:", "embed:active-model"),
    "prompt_templates": ("sys:prompt:",),
    "llm_settings": ("llm:setting",),
    "llm_models": ("llm:config:", "llm:models:"),
    "llm_api_keys": ("llm:config:", "llm:models:"),
    "embed_models": ("embed:model:", "embed:active-model"),
    "product_types": ("cat:product_types:", "cat:categories:"),
    "categories": ("cat:categories:",),
    "attributes": ("cat:attributes:", "cat:attribute_groups:", "cat:attribute_options:"),
    "attribute_groups": ("cat:attribute_groups:", "cat:attributes:"),
    "attribute_options": ("cat:attribute_options:", "cat:attributes:"),
    "brands": ("cat:brands:",),
    "product_type_image_view_types": ("cat:image_view_types:",),
    "store_types": ("cat:store_types:",),
    "countries": ("cat:countries:",),
    "currencies": ("cat:currencies:",),
    "store_products": ("product:detail:", "store:stats:", "product:info:", "product:random:"),
    "product_images": ("product:info:", "product:random:"),
    "product_variants": ("product:info:",),
    "product_sizes": ("product:info:",),
    "product_pieces": ("product:info:",),
    "product_embeddings": ("product:info:", "embed:model:"),
    "search_eval_queries": ("seval:metrics:",),
    "search_eval_judgments": ("seval:metrics:",),
}


class CacheKeys:
    """Single registry of every Redis cache key in the system.

    Each member is a :class:`CacheKey` pairing the key prefix with its TTL in
    seconds, so the whole key space stays centralized and the TTL can never
    diverge from the key. Repositories must build keys through these
    constants/builders so the ``PREFIX_BY_TABLE`` mapping remains the
    authority used for invalidation.
    """

    SYSTEM_SETTINGS = CacheKey("sys:settings:", 300)
    SYSTEM_SETTING = CacheKey("sys:setting:", 300)
    PROMPT = CacheKey("sys:prompt:", 600)
    LLM_SETTING = CacheKey("llm:setting", 300)
    EMBED_MODEL = CacheKey("embed:active-model", 60)
    EMBED_MODEL_BY_NAME = CacheKey("embed:model:", 60)
    LLM_MODEL_CONFIG = CacheKey("llm:config:", 120)
    LLM_MODELS = CacheKey("llm:models:", 300)
    CAT_PRODUCT_TYPES = CacheKey("cat:product_types:", 3600)
    CAT_CATEGORIES = CacheKey("cat:categories:", 3600)
    CAT_ATTRIBUTES = CacheKey("cat:attributes:", 3600)
    CAT_ATTRIBUTE_GROUPS = CacheKey("cat:attribute_groups:", 3600)
    CAT_ATTRIBUTE_OPTIONS = CacheKey("cat:attribute_options:", 3600)
    CAT_BRANDS = CacheKey("cat:brands:", 3600)
    CAT_IMAGE_VIEW_TYPES = CacheKey("cat:image_view_types:", 3600)
    CAT_STORE_TYPES = CacheKey("cat:store_types:", 3600)
    CAT_COUNTRIES = CacheKey("cat:countries:", 3600)
    CAT_CURRENCIES = CacheKey("cat:currencies:", 3600)
    PRODUCT_INFO = CacheKey("product:info:", 600)
    PRODUCT_DETAIL = CacheKey("product:detail:", 300)
    STORE_STATS = CacheKey("store:stats:", 60)
    RANDOM = CacheKey("product:random:", 3600)
    SEARCH_EVAL_METRICS = CacheKey("seval:metrics:", 300)

    # key builders ---------------------------------------------------------
    @staticmethod
    def system_setting(key: str) -> str:
        return f"{CacheKeys.SYSTEM_SETTING.prefix}{key}"

    @staticmethod
    def prompt(type_: str) -> str:
        return f"{CacheKeys.PROMPT.prefix}{type_}"

    @staticmethod
    def embed_model_by_name(model_name: str) -> str:
        return f"{CacheKeys.EMBED_MODEL_BY_NAME.prefix}{model_name}"

    @staticmethod
    def llm_model_config(model_id: str) -> str:
        return f"{CacheKeys.LLM_MODEL_CONFIG.prefix}{model_id}"

    @staticmethod
    def product_info(product_id: str, lang: str) -> str:
        return f"{CacheKeys.PRODUCT_INFO.prefix}{product_id}:{lang}"

    @staticmethod
    def product_detail(store_id: str, product_id: str) -> str:
        return f"{CacheKeys.PRODUCT_DETAIL.prefix}{store_id}:{product_id}"

    @staticmethod
    def store_stats(signature: str) -> str:
        return f"{CacheKeys.STORE_STATS.prefix}{signature}"

    @staticmethod
    def random(limit: int) -> str:
        return f"{CacheKeys.RANDOM.prefix}{limit}"

    @staticmethod
    def search_eval_metrics(signature: str) -> str:
        return f"{CacheKeys.SEARCH_EVAL_METRICS.prefix}{signature}"


# Prefixes to invalidate when a table is written. Tables map to the cache
# keys their reads populate; a write to the table deletes every such key.
PREFIX_BY_TABLE = _TABLE_TO_PREFIXES


_LOCK_TTL_SECONDS = 2
_LOCK_RETRIES = 20
_LOCK_RETRY_DELAY = 0.05


async def cache_get(redis: AsyncRedis, key: str) -> Any | None:
    """Return the JSON-decoded value for *key*, or ``None`` on a miss."""
    raw = await redis.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("Corrupt cache entry for {}: {}", key, exc)
        return None


async def cache_set(redis: AsyncRedis, key: str, value: Any, ttl: int) -> None:
    """JSON-encode and store *value* under *key* with a TTL."""
    await redis.set(key, json.dumps(value, default=str), ex=ttl)


async def invalidate_prefix(redis: AsyncRedis, prefix: str) -> None:
    """Delete every cached key beginning with *prefix* (SCAN + DEL)."""
    keys = [key async for key in redis.scan_iter(match=f"{prefix}*", count=200)]
    if keys:
        await redis.delete(*keys)
        logger.debug("Invalidated {} cache keys under '{}'", len(keys), prefix)


async def invalidate_tables(redis: AsyncRedis, tables: set[str] | frozenset[str]) -> None:
    """Invalidate every cache prefix touched by the given tables."""
    seen: set[str] = set()
    for table in tables:
        for prefix in PREFIX_BY_TABLE.get(table, ()):
            if prefix in seen:
                continue
            seen.add(prefix)
            try:
                await invalidate_prefix(redis, prefix)
            except Exception as exc:
                logger.warning("Cache invalidation failed for '{}': {}", prefix, exc)


async def _wait_for_lock_holder[T](redis: AsyncRedis, key: str, fetch: Callable[[], Awaitable[T]], lock_key: str) -> T:
    """Wait briefly for the lock holder to populate the cache, then fetch."""
    for _ in range(_LOCK_RETRIES):
        await asyncio.sleep(_LOCK_RETRY_DELAY)
        cached = await cache_get(redis, key)
        if cached is not None:
            return cast(T, cached)
    logger.debug("Cache lock owner took too long for '{}'; fetching directly", key)
    await redis.delete(lock_key)
    return await fetch()


async def cache_or_fetch[T](
    redis: AsyncRedis,
    key: str,
    ttl: int,
    fetch: Callable[[], Awaitable[T]],
    lock: bool = False,
) -> T:
    """Return the cached value for *key* or compute it via *fetch* and store it.

    Fail-open: a Redis error falls through to *fetch* and never raises.
    With ``lock=True`` a short ``SET NX`` lock guards against stampedes on
    hot single-value keys (callers not holding the lock wait for the value).
    """
    try:
        cached = await cache_get(redis, key)
        if cached is not None:
            return cast(T, cached)
    except Exception as exc:
        logger.warning("Cache read failed for '{}': {}", key, exc)
        return await fetch()

    if not lock:
        value = await fetch()
    else:
        lock_key = f"{key}:lock"
        try:
            acquired = await redis.set(lock_key, "1", nx=True, ex=_LOCK_TTL_SECONDS)
        except Exception as exc:
            logger.warning("Cache lock acquire failed for '{}': {}", key, exc)
            return await fetch()
        try:
            if acquired:
                value = await fetch()
            else:
                value = await _wait_for_lock_holder(redis, key, fetch, lock_key)
        finally:
            if acquired:
                with contextlib.suppress(Exception):
                    await redis.delete(lock_key)

    try:
        await cache_set(redis, key, value, ttl)
    except Exception as exc:
        logger.warning("Cache write failed for '{}': {}", key, exc)
    return value
