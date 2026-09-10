import json

import pytest

from app.core.cache import (
    PREFIX_BY_TABLE,
    CacheKeys,
    cache_get,
    cache_or_fetch,
    cache_set,
    invalidate_prefix,
    invalidate_tables,
)


class FakeRedis:
    """In-memory stand-in for the AsyncRedis client used by cache helpers."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.locks: set[str] = set()

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool:
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        removed = sum(1 for k in keys if self.store.pop(k, None) is not None)
        return removed

    async def scan_iter(self, match: str = "*", count: int = 100):  # noqa: ARG002
        prefix = match.rstrip("*") if match.endswith("*") else match
        for key in list(self.store):
            if key.startswith(prefix):
                yield key

    async def ping(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_cache_set_get_roundtrip():
    redis = FakeRedis()
    await cache_set(redis, "k:1", {"a": 1, "b": "x"}, ttl=10)
    assert await cache_get(redis, "k:1") == {"a": 1, "b": "x"}
    assert redis.store["k:1"] == json.dumps({"a": 1, "b": "x"})


@pytest.mark.asyncio
async def test_cache_get_miss_returns_none():
    redis = FakeRedis()
    assert await cache_get(redis, "missing") is None


@pytest.mark.asyncio
async def test_cache_get_corrupt_json_returns_none():
    redis = FakeRedis()
    redis.store["k"] = "{not-json"
    assert await cache_get(redis, "k") is None


@pytest.mark.asyncio
async def test_invalidate_prefix_deletes_matching_keys():
    redis = FakeRedis()
    await cache_set(redis, "sys:setting:a", 1, ttl=10)
    await cache_set(redis, "sys:setting:b", 2, ttl=10)
    await cache_set(redis, "other:key", 3, ttl=10)
    await invalidate_prefix(redis, "sys:setting:")
    assert redis.store == {"other:key": "3"}


@pytest.mark.asyncio
async def test_invalidate_prefix_no_keys_is_noop():
    redis = FakeRedis()
    await invalidate_prefix(redis, "empty:")
    assert redis.store == {}


@pytest.mark.asyncio
async def test_invalidate_tables_maps_to_prefixes_and_dedupes():
    redis = FakeRedis()
    await cache_set(redis, CacheKeys.system_setting("x"), 1, ttl=10)
    await cache_set(redis, CacheKeys.SYSTEM_SETTINGS.prefix + "all", 2, ttl=10)
    await cache_set(redis, CacheKeys.EMBED_MODEL.prefix, 3, ttl=10)
    await cache_set(redis, "llm:models:all", 4, ttl=10)
    await invalidate_tables(redis, {"system_settings", "llm_models", "llm_api_keys"})
    assert redis.store == {}


@pytest.mark.asyncio
async def test_cache_or_fetch_hit_skips_fetch():
    redis = FakeRedis()
    await cache_set(redis, "k", {"v": 1}, ttl=10)
    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        return {"v": 2}

    result = await cache_or_fetch(redis, "k", 10, fetch)
    assert result == {"v": 1}
    assert calls == 0


@pytest.mark.asyncio
async def test_cache_or_fetch_miss_fetches_and_stores():
    redis = FakeRedis()
    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        return {"v": 2}

    result = await cache_or_fetch(redis, "k", 10, fetch)
    assert result == {"v": 2}
    assert calls == 1
    assert await cache_get(redis, "k") == {"v": 2}


@pytest.mark.asyncio
async def test_cache_or_fetch_read_error_falls_back_to_fetch():
    redis = FakeRedis()

    async def failing_get(key: str) -> str | None:
        raise OSError("connection refused")

    redis.get = failing_get  # type: ignore[method-assign]
    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        return "db-value"

    result = await cache_or_fetch(redis, "k", 10, fetch)
    assert result == "db-value"
    assert calls == 1


@pytest.mark.asyncio
async def test_cache_or_fetch_write_error_still_returns_value():
    redis = FakeRedis()

    async def failing_set(key: str, value: str, ex: int | None = None, nx: bool = False) -> bool:
        raise OSError("connection refused")

    redis.set = failing_set  # type: ignore[method-assign]

    async def fetch():
        return "db-value"

    result = await cache_or_fetch(redis, "k", 10, fetch)
    assert result == "db-value"


@pytest.mark.asyncio
async def test_cache_or_fetch_lock_acquired_fetches_and_releases():
    redis = FakeRedis()
    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        return "db-value"

    result = await cache_or_fetch(redis, "k", 10, fetch, lock=True)
    assert result == "db-value"
    assert calls == 1
    assert await cache_get(redis, "k") == "db-value"
    assert "k:lock" not in redis.store


@pytest.mark.asyncio
async def test_cache_or_fetch_lock_wait_reads_owner_value():
    redis = FakeRedis()
    redis.store["k:lock"] = "1"

    async def fetch():
        return "db-value"

    await cache_set(redis, "k", "owner-value", ttl=10)
    result = await cache_or_fetch(redis, "k", 10, fetch, lock=True)
    assert result == "owner-value"


@pytest.mark.asyncio
async def test_key_builders():
    assert CacheKeys.system_setting("x") == "sys:setting:x"
    assert CacheKeys.prompt("chat") == "sys:prompt:chat"
    assert CacheKeys.embed_model_by_name("m") == "embed:model:m"
    assert CacheKeys.llm_model_config("mid") == "llm:config:mid"
    assert CacheKeys.product_info("p", "ar") == "product:info:p:ar"
    assert CacheKeys.product_detail("s", "p") == "product:detail:s:p"
    assert CacheKeys.store_stats("sig") == "store:stats:sig"
    assert CacheKeys.search_eval_metrics("sig") == "seval:metrics:sig"
    assert PREFIX_BY_TABLE["system_settings"] == ("sys:settings:", "sys:setting:", "embed:active-model")
