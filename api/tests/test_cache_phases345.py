from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.cache import CacheKeys, cache_set, invalidate_tables
from tests.test_cache import FakeRedis


@pytest.mark.asyncio
async def test_catalog_category_repo_cached_second_call_skips_db():
    redis = FakeRedis()
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [
        SimpleNamespace(
            id="cat-1",
            parent_id=None,
            product_type_id="pt-1",
            name_ar="ملابس",
            name_en="Clothes",
            name_fa="لباس",
            icon="shirt",
            sort_order=1,
            is_active=True,
        )
    ]
    db.execute.return_value = result_mock

    from app.repositories.catalog import CategoryRepository

    repo = CategoryRepository(db, redis)
    first = await repo.list_all_dto()
    assert first[0]["name_en"] == "Clothes"
    assert redis.store[f"{CacheKeys.CAT_CATEGORIES.prefix}all"] is not None

    db.execute.reset_mock()
    second = await repo.list_all_dto()
    assert second == first
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_catalog_repo_without_redis_hits_db():
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [SimpleNamespace(id="st-1", code="clothing", name_ar="ملابس", name_en="Clothing", name_fa="پوشاک", is_active=True, sort_order=1)]
    db.execute.return_value = result_mock

    from app.repositories.reference import StoreTypeRepository

    items = await StoreTypeRepository(db).list_active_dto("en")
    assert items[0]["name"] == "Clothing"
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_reference_repo_cached_second_call_skips_db():
    redis = FakeRedis()
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [SimpleNamespace(id="st-1", code="clothing", name_ar="ملابس", name_en="Clothing", name_fa="پوشاک", is_active=True, sort_order=1)]
    db.execute.return_value = result_mock

    from app.repositories.reference import StoreTypeRepository

    repo = StoreTypeRepository(db, redis)
    await repo.list_active_dto("en")

    db.execute.reset_mock()
    second = await repo.list_active_dto("en")
    assert second[0]["name"] == "Clothing"
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_get_my_products_stats_cached():
    redis = FakeRedis()
    db = AsyncMock()

    with patch("app.services.product_definition_service.count_my_products", new=AsyncMock(side_effect=[7, 5])) as mock_count:
        from app.services.product_definition_service import get_my_products_stats

        stats = await get_my_products_stats(db, redis, ["s1", "s2"])
        assert stats == {"total": 7, "active": 5}
        assert mock_count.call_count == 2

        mock_count.reset_mock()
        cached = await get_my_products_stats(db, redis, ["s1", "s2"])
        assert cached == {"total": 7, "active": 5}
        mock_count.assert_not_called()


@pytest.mark.asyncio
async def test_get_product_info_cached_skips_build():
    redis = FakeRedis()
    db = AsyncMock()

    with patch("app.services.product_info_service._build_product_info", new=AsyncMock(return_value={"id": "p-1", "name": "Shirt"})) as mock_build:
        from app.services.product_info_service import get_product_info

        info = await get_product_info(db, "p-1", "en", redis=redis)
        assert info["name"] == "Shirt"
        mock_build.assert_awaited_once()

        mock_build.reset_mock()
        cached = await get_product_info(db, "p-1", "en", redis=redis)
        assert cached["name"] == "Shirt"
        mock_build.assert_not_awaited()
        assert redis.store[CacheKeys.product_info("p-1", "en")] is not None


@pytest.mark.asyncio
async def test_get_store_product_response_cached():
    redis = FakeRedis()
    db = AsyncMock()

    with (
        patch("app.services.product_definition_service.get_store_product", new=AsyncMock()) as mock_get,
        patch("app.services.product_definition_service._store_product_to_response") as mock_to_resp,
        patch("app.services.product_definition_service.StoreProductResponse") as mock_schema,
    ):
        mock_product = MagicMock()
        mock_get.return_value = mock_product
        resp = MagicMock()
        resp.model_dump.return_value = {"id": "p-1", "name": "Shirt", "images": []}
        mock_to_resp.return_value = resp
        mock_schema.model_validate.return_value = SimpleNamespace(id="p-1")

        from app.services.product_definition_service import get_store_product_response

        result = await get_store_product_response(db, redis, "p-1", "s-1")
        assert result.id == "p-1"
        mock_get.assert_awaited_once()

        mock_get.reset_mock()
        cached = await get_store_product_response(db, redis, "p-1", "s-1")
        assert cached.id == "p-1"
        mock_get.assert_not_awaited()


@pytest.mark.asyncio
async def test_llm_model_config_cached():
    redis = FakeRedis()
    db = AsyncMock()

    with patch("app.services.llm_service.LLMModelRepository") as mock_repo_cls, patch("app.services.llm_service.decrypt_api_key", return_value="sk-test"):
        mock_repo = AsyncMock()
        model = MagicMock()
        model.model = "deepseek-v4-flash-free"
        model.provider = "opencode_zen"
        model.api_keys = [SimpleNamespace(is_active=True, api_key_encrypted="enc")]
        mock_repo.get_active_with_api_keys.return_value = model
        mock_repo_cls.return_value = mock_repo

        from app.services.llm_service import resolve_model_config

        first = await resolve_model_config(db, "m-1", redis=redis)
        assert first == {"model": "deepseek-v4-flash-free", "api_key": "sk-test", "base_url": "https://opencode.ai/zen/v1"}

        mock_repo.get_active_with_api_keys.reset_mock()
        second = await resolve_model_config(db, "m-1", redis=redis)
        assert second == first
        mock_repo.get_active_with_api_keys.assert_not_called()


@pytest.mark.asyncio
async def test_search_eval_metrics_cached():
    redis = FakeRedis()
    db = AsyncMock()

    payload = {
        "overall": {
            "locale": "all",
            "query_count": 2,
            "mrr_10": 0.5,
            "recall_10": 0.6,
        },
        "per_locale": [],
    }
    await cache_set(redis, CacheKeys.search_eval_metrics("all"), payload, ttl=300)

    with patch("app.services.search_eval_service.SearchEvalQueryRepository") as mock_q_cls, patch("app.services.search_eval_service.SearchEvalJudgmentRepository") as mock_j_cls:
        mock_q = AsyncMock()
        mock_q.list_evaluated.return_value = []
        mock_q_cls.return_value = mock_q
        mock_j = AsyncMock()
        mock_j.list_all.return_value = []
        mock_j_cls.return_value = mock_j

        from app.services.search_eval_service import get_metrics

        overall, per_locale = await get_metrics(db, redis=redis)
        assert overall.mrr_10 == 0.5
        assert per_locale == []
        mock_q.list_evaluated.assert_not_called()


@pytest.mark.asyncio
async def test_product_write_invalidation_covers_detail_info_stats():
    redis = FakeRedis()
    await cache_set(redis, CacheKeys.product_detail("s-1", "p-1"), {"id": "p-1"}, ttl=300)
    await cache_set(redis, CacheKeys.product_info("p-1", "en"), {"id": "p-1"}, ttl=600)
    await cache_set(redis, CacheKeys.store_stats("s-1"), {"total": 1}, ttl=60)
    await cache_set(redis, "unrelated:key", 1, ttl=60)

    await invalidate_tables(redis, {"store_products", "product_images", "product_variants", "product_sizes", "product_pieces"})

    assert redis.store == {"unrelated:key": "1"}


@pytest.mark.asyncio
async def test_product_type_detail_cache_key_shape():
    assert f"{CacheKeys.CAT_PRODUCT_TYPES.prefix}detail:pt-1" == "cat:product_types:detail:pt-1"
    assert f"{CacheKeys.CAT_STORE_TYPES.prefix}en" == "cat:store_types:en"
    assert f"{CacheKeys.CAT_COUNTRIES.prefix}all" == "cat:countries:all"
    assert f"{CacheKeys.CAT_CURRENCIES.prefix}all" == "cat:currencies:all"
    assert CacheKeys.store_stats("s-1,s-2") == "store:stats:s-1,s-2"
