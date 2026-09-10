from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CacheKeys, cache_set
from app.models.llm_setting import LLMSetting
from app.repositories.llm import LLMSettingRepository
from app.services import llm_service
from tests.test_cache import FakeRedis


def _db_with_setting(setting: LLMSetting | None) -> AsyncMock:
    db = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none.return_value = setting
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_get_single_dto_caches_and_skips_db():
    db = _db_with_setting(LLMSetting(default_llm_model_id="m1", user_comm_model_id="m2"))
    redis = FakeRedis()
    repo = LLMSettingRepository(db, redis)

    first = await repo.get_single_dto()
    second = await repo.get_single_dto()

    assert first == {"default_llm_model_id": "m1", "user_comm_model_id": "m2"}
    assert second == first
    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_get_single_dto_without_redis_hits_db_each_time():
    db = _db_with_setting(LLMSetting(default_llm_model_id="m1", user_comm_model_id="m2"))
    repo = LLMSettingRepository(db)

    assert await repo.get_single_dto() == {"default_llm_model_id": "m1", "user_comm_model_id": "m2"}
    assert await repo.get_single_dto() == {"default_llm_model_id": "m1", "user_comm_model_id": "m2"}
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_get_single_dto_missing_row_returns_none():
    db = _db_with_setting(None)
    repo = LLMSettingRepository(db, FakeRedis())

    assert await repo.get_single_dto() is None
    assert await repo.get_single_dto() is None


@pytest.mark.asyncio
async def test_get_single_stays_orm_uncached():
    setting = LLMSetting(default_llm_model_id="m1", user_comm_model_id="m2")
    db = _db_with_setting(setting)
    repo = LLMSettingRepository(db, FakeRedis())

    assert await repo.get_single() is setting
    assert await repo.get_single() is setting
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_get_settings_dto_service_wrapper():
    db = _db_with_setting(LLMSetting(default_llm_model_id="m1", user_comm_model_id="m2"))
    redis = FakeRedis()

    assert await llm_service.get_settings_dto(db, redis) == {
        "default_llm_model_id": "m1",
        "user_comm_model_id": "m2",
    }
    assert await llm_service.get_settings_dto(db, redis) == {
        "default_llm_model_id": "m1",
        "user_comm_model_id": "m2",
    }
    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_update_settings_invalidates_llm_settings_cache():
    db = _db_with_setting(None)
    redis = FakeRedis()
    await cache_set(redis, CacheKeys.LLM_SETTING.prefix, {"default_llm_model_id": "m1", "user_comm_model_id": "m2"}, ttl=10)

    setting = await llm_service.update_settings(
        db,
        None,
        None,
        include_default=False,
        include_user_comm=False,
        redis=redis,
    )

    assert setting.default_llm_model_id is None
    assert redis.store == {}
