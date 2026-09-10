from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CacheKeys, cache_get, cache_set
from app.models.system_setting import SystemSetting
from app.repositories.settings import SystemSettingRepository
from app.services import system_setting_service
from tests.test_cache import FakeRedis


def _db_with_setting(setting: SystemSetting | None) -> AsyncMock:
    db = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none.return_value = setting
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_get_by_key_returns_dto_and_caches():
    db = _db_with_setting(SystemSetting(key="site_name", value="Tea"))
    redis = FakeRedis()
    repo = SystemSettingRepository(db, redis)

    first = await repo.get_by_key("site_name")
    second = await repo.get_by_key("site_name")

    assert first == {"key": "site_name", "value": "Tea"}
    assert second == first
    assert db.execute.await_count == 1
    assert await cache_get(redis, CacheKeys.system_setting("site_name")) == first


@pytest.mark.asyncio
async def test_get_by_key_without_redis_hits_db_each_time():
    db = _db_with_setting(SystemSetting(key="k", value="v"))
    repo = SystemSettingRepository(db)

    assert await repo.get_by_key("k") == {"key": "k", "value": "v"}
    assert await repo.get_by_key("k") == {"key": "k", "value": "v"}
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_get_by_key_orm_returns_model_uncached():
    setting = SystemSetting(key="k", value="v")
    db = _db_with_setting(setting)
    repo = SystemSettingRepository(db, FakeRedis())

    assert await repo.get_by_key_orm("k") is setting
    assert await repo.get_by_key_orm("k") is setting
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_list_all_returns_dtos_and_caches():
    db = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        SystemSetting(key="a", value="1"),
        SystemSetting(key="b", value="2"),
    ]
    db.execute = AsyncMock(return_value=result)
    redis = FakeRedis()
    repo = SystemSettingRepository(db, redis)

    assert await repo.list_all() == [{"key": "a", "value": "1"}, {"key": "b", "value": "2"}]
    assert await repo.list_all() == [{"key": "a", "value": "1"}, {"key": "b", "value": "2"}]
    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_list_by_keys_returns_dtos_and_caches():
    db = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        SystemSetting(key="a", value="1"),
        SystemSetting(key="b", value="2"),
    ]
    db.execute = AsyncMock(return_value=result)
    redis = FakeRedis()
    repo = SystemSettingRepository(db, redis)

    assert await repo.list_by_keys(["b", "a"]) == [{"key": "a", "value": "1"}, {"key": "b", "value": "2"}]
    assert await repo.list_by_keys(["b", "a"]) == [{"key": "a", "value": "1"}, {"key": "b", "value": "2"}]
    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_update_setting_invalidates_system_settings_cache():
    db = _db_with_setting(None)
    redis = FakeRedis()
    ai_client = AsyncMock()
    await cache_set(redis, CacheKeys.SYSTEM_SETTINGS.prefix + "all", [{"key": "x", "value": "y"}], ttl=10)
    await cache_set(redis, CacheKeys.system_setting("x"), {"key": "x", "value": "y"}, ttl=10)
    await cache_set(redis, CacheKeys.EMBED_MODEL.prefix, {"model": "m", "dims": 1024}, ttl=10)

    setting = await system_setting_service.update_setting(db, ai_client, "site_name", "Tea", redis=redis)

    assert setting.key == "site_name"
    assert setting.value == "Tea"
    assert redis.store == {}


@pytest.mark.asyncio
async def test_update_setting_without_redis_skips_invalidation():
    db = _db_with_setting(None)

    setting = await system_setting_service.update_setting(db, AsyncMock(), "site_name", "Tea")

    assert setting.key == "site_name"
    db.commit.assert_awaited_once()
