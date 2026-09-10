from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CacheKeys, cache_get
from app.repositories.settings import PromptTemplateRepository
from tests.test_cache import FakeRedis


def _db_with_content(content: str | None) -> AsyncMock:
    db = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalar_one_or_none.return_value = content
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_get_active_content_caches_and_skips_db():
    db = _db_with_content("hello")
    redis = FakeRedis()
    repo = PromptTemplateRepository(db, redis)

    assert await repo.get_active_content("pre_prompt") == "hello"
    assert await repo.get_active_content("pre_prompt") == "hello"
    assert db.execute.await_count == 1
    assert await cache_get(redis, CacheKeys.prompt("pre_prompt")) == "hello"


@pytest.mark.asyncio
async def test_get_active_content_without_redis_hits_db_each_time():
    db = _db_with_content("hello")
    repo = PromptTemplateRepository(db)

    assert await repo.get_active_content("pre_prompt") == "hello"
    assert await repo.get_active_content("pre_prompt") == "hello"
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_get_active_content_missing_row_returns_none():
    db = _db_with_content(None)
    repo = PromptTemplateRepository(db, FakeRedis())

    assert await repo.get_active_content("unknown_type") is None
    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_deactivate_active_invalidates_prompt_cache():
    db = _db_with_content("old")
    redis = FakeRedis()
    repo = PromptTemplateRepository(db, redis)
    await repo.get_active_content("pre_prompt")
    assert await cache_get(redis, CacheKeys.prompt("pre_prompt")) == "old"

    await repo.deactivate_active("pre_prompt")

    assert redis.store == {}


@pytest.mark.asyncio
async def test_prompt_caches_are_per_type():
    db = _db_with_content("pre")
    redis = FakeRedis()
    repo = PromptTemplateRepository(db, redis)

    assert await repo.get_active_content("pre_prompt") == "pre"
    assert await repo.get_active_content("ending_prompt") == "pre"
    assert await cache_get(redis, CacheKeys.prompt("pre_prompt")) == "pre"
    assert await cache_get(redis, CacheKeys.prompt("ending_prompt")) == "pre"
    assert db.execute.await_count == 2
