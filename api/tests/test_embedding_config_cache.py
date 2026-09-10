import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CacheKeys, cache_set, invalidate_tables
from app.models.system_setting import SystemSetting
from app.services.embedding_config import (
    DEFAULT_EMBEDDING_DIMS,
    DEFAULT_EMBEDDING_MODEL,
    get_active_embedding_model,
)
from tests.test_cache import FakeRedis


def _db_with_setting(setting: SystemSetting | None) -> AsyncMock:
    db = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none.return_value = setting
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_active_model_resolved_and_cached():
    db = _db_with_setting(SystemSetting(key="embedding_provider", value=json.dumps({"provider": "tei", "model": "Qwen3-Embedding-4B"})))
    redis = FakeRedis()

    first = await get_active_embedding_model(db, redis)
    second = await get_active_embedding_model(db, redis)

    assert first == ("Qwen3-Embedding-4B", 2560)
    assert second == first
    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_active_model_without_redis_hits_db():
    db = _db_with_setting(SystemSetting(key="embedding_provider", value=json.dumps({"provider": "tei", "model": "Qwen3-Embedding-0.6B"})))

    assert await get_active_embedding_model(db) == ("Qwen3-Embedding-0.6B", 1024)
    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_active_model_falls_back_to_defaults_when_unset():
    db = _db_with_setting(None)

    assert await get_active_embedding_model(db) == (DEFAULT_EMBEDDING_MODEL, DEFAULT_EMBEDDING_DIMS)


@pytest.mark.asyncio
async def test_active_model_falls_back_to_defaults_on_legacy_plain_provider():
    db = _db_with_setting(SystemSetting(key="embedding_provider", value="tei"))

    assert await get_active_embedding_model(db) == (DEFAULT_EMBEDDING_MODEL, DEFAULT_EMBEDDING_DIMS)


@pytest.mark.asyncio
async def test_active_model_invalidated_by_system_settings_write():
    redis = FakeRedis()
    await cache_set(redis, CacheKeys.EMBED_MODEL.prefix, {"model": "Qwen3-Embedding-4B", "dims": 2560}, ttl=10)

    await invalidate_tables(redis, {"system_settings"})

    assert redis.store == {}


@pytest.mark.asyncio
async def test_active_model_uses_cached_after_system_settings_read():
    db = _db_with_setting(SystemSetting(key="embedding_provider", value=json.dumps({"provider": "tei", "model": "Qwen3-Embedding-8B"})))
    redis = FakeRedis()

    assert await get_active_embedding_model(db, redis) == ("Qwen3-Embedding-8B", 4096)
    assert await get_active_embedding_model(db, redis) == ("Qwen3-Embedding-8B", 4096)
    assert db.execute.await_count == 1
