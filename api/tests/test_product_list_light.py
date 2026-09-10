from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.cache import CacheKeys
from tests.test_cache import FakeRedis


def _product_row(product_id: str, store_id: str = "store-1", name_en: str = "Nike Air") -> SimpleNamespace:
    product = SimpleNamespace(
        id=product_id,
        store_id=store_id,
        product_type_id="pt-1",
        name_ar=name_en,
        name_en=name_en,
        name_fa=name_en,
        brand="brand-1",
        status="active",
        has_variants=False,
        price=199.0,
        original_price=249.0,
        sale_price=179.0,
        currency="SAR",
        quantity=5,
    )
    return SimpleNamespace(StoreProduct=product, brand_ar="نایکی", brand_en="Nike", brand_fa="نایکی", store_name="Nike Store")


@pytest.mark.asyncio
async def test_repo_list_by_store_ids_light_flattens_rows_and_resolves_first_image():
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.all.return_value = [_product_row("p-1"), _product_row("p-2", name_en="Nike Pro")]
    images_mock = MagicMock()
    images_mock.all.return_value = [("p-1", "product-graph/a.jpg"), ("p-1", "product-graph/b.jpg"), ("p-2", "product-graph/c.jpg")]
    calls = iter([result_mock, images_mock])

    async def _execute(_stmt) -> MagicMock:  # noqa: ANN001
        return next(calls)

    db.execute.side_effect = _execute

    from app.repositories.product_definition import StoreProductRepository

    items = await StoreProductRepository(db).list_by_store_ids_light(["store-1"], skip=0, limit=10)
    assert len(items) == 2
    assert items[0]["id"] == "p-1"
    assert items[0]["brand_name"] == "Nike"
    assert items[0]["store_name"] == "Nike Store"
    assert items[0]["image_url"] == "product-graph/a.jpg"
    assert items[1]["image_url"] == "product-graph/c.jpg"


@pytest.mark.asyncio
async def test_repo_search_by_name_light_returns_total():
    db = AsyncMock()
    rows_mock = MagicMock()
    rows_mock.all.return_value = [_product_row("p-1")]
    count_mock = MagicMock()
    count_mock.scalar_one.return_value = 7
    images_mock = MagicMock()
    images_mock.all.return_value = [("p-1", "product-graph/a.jpg")]
    calls = iter([rows_mock, count_mock, images_mock])

    async def _execute(_stmt) -> MagicMock:  # noqa: ANN001
        return next(calls)

    db.execute.side_effect = _execute

    from app.repositories.product_definition import StoreProductRepository

    items, total = await StoreProductRepository(db).search_by_name_light("Nike", store_ids=["store-1"], skip=0, limit=10)
    assert total == 7
    assert items[0]["name_en"] == "Nike Air"


@pytest.mark.asyncio
async def test_list_my_products_light_resolves_image_urls():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.list_by_store_ids_light.return_value = [
            {"id": "p-1", "image_url": "product-graph/a.jpg"},
            {"id": "p-2", "image_url": "https://cdn.example.com/b.jpg"},
        ]
        mock_repo.count_by_store_ids.return_value = 2
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import list_my_products_light

        items, total = await list_my_products_light(AsyncMock(), ["store-1"], skip=0, limit=10)
        assert total == 2
        assert items[0]["image_url"].startswith("https://")
        assert items[1]["image_url"] == "https://cdn.example.com/b.jpg"
        mock_repo.list_by_store_ids_light.assert_called_once_with(["store-1"], skip=0, limit=10)


@pytest.mark.asyncio
async def test_random_products_light_caches_and_skips_db_on_hit():
    redis = FakeRedis()
    db = AsyncMock()

    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.random_light.return_value = [{"id": "p-1", "image_url": "product-graph/a.jpg"}]
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import random_products_light

        first = await random_products_light(db, redis, limit=20)
        assert first[0]["image_url"].startswith("https://")
        assert CacheKeys.random(20) in redis.store

        mock_repo.random_light.reset_mock()
        second = await random_products_light(db, redis, limit=20)
        assert second == first
        mock_repo.random_light.assert_not_called()


@pytest.mark.asyncio
async def test_random_products_light_without_redis_hits_db():
    with patch("app.services.product_definition_service.StoreProductRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.random_light.return_value = [{"id": "p-1", "image_url": None}]
        mock_repo_cls.return_value = mock_repo

        from app.services.product_definition_service import random_products_light

        items = await random_products_light(AsyncMock(), None, limit=5)
        assert items[0]["image_url"] is None
        mock_repo.random_light.assert_awaited_once_with(limit=5)


@pytest.mark.asyncio
async def test_random_cache_key_builder():
    assert CacheKeys.random(20) == "product:random:20"
    assert CacheKeys.RANDOM.ttl == 3600


@pytest.mark.asyncio
async def test_repo_search_by_name_light_store_scope_anded_with_name_match():
    """Regression: store scope must be AND-ed with the name OR-group.

    The old build appended ``store_id IN (...)`` into the same list combined with
    ``or_()``, so the store condition alone matched every owned product and the
    ``q`` filter had no effect.
    """
    from app.repositories.product_definition import StoreProductRepository

    captured: list = []

    def _side_effect(stmt, *args, **kwargs):
        captured.append(stmt)
        rows_result = MagicMock()
        rows_result.all.return_value = []
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        return rows_result if len(captured) == 1 else count_result

    db = AsyncMock()
    db.execute.side_effect = _side_effect

    await StoreProductRepository(db).search_by_name_light("bra", store_ids=["s1"], skip=0, limit=10)

    assert len(captured) == 2, "expected the data statement and the count statement"
    for stmt in captured:
        sql = " ".join(str(stmt.compile(compile_kwargs={"literal_binds": True})).split())
        assert ") AND store_products.store_id IN" in sql, f"store scope not AND-ed with name match: {sql}"
        assert "OR store_products.store_id IN" not in sql, f"store scope leaked into the name OR-group: {sql}"


@pytest.mark.asyncio
async def test_repo_search_by_name_light_multi_word_similarity_ranking():
    """Multi-word query: per-token trigram matching, exact-phrase bonus first in ORDER BY."""
    from app.repositories.product_definition import StoreProductRepository

    captured: list = []

    def _side_effect(stmt, *args, **kwargs):
        captured.append(stmt)
        rows_result = MagicMock()
        rows_result.all.return_value = []
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        return rows_result if len(captured) == 1 else count_result

    db = AsyncMock()
    db.execute.side_effect = _side_effect

    await StoreProductRepository(db).search_by_name_light("RAFFIA BRAIDED VISOR", store_ids=["s1"], skip=0, limit=10)

    data_sql = " ".join(str(captured[0].compile(compile_kwargs={"literal_binds": True})).split()).lower()

    # WHERE: whole phrase substring + every token as trigram match
    assert "like lower('%raffia braided visor%')" in data_sql
    assert "name_en % 'braided'" in data_sql and "name_ar % 'braided'" in data_sql
    assert "name_en % 'raffia'" in data_sql and "name_en % 'visor'" in data_sql

    # ORDER BY: phrase bonus CASE + greatest(per-token similarity) descending
    order_clause = data_sql.split(" order by ")[1]
    assert "then 1.0 else 0.0 end" in order_clause
    assert "greatest(similarity(store_products.name_en" in order_clause
    assert "similarity(store_products.name_ar, 'raffia')" in order_clause

    # store scope still AND-ed with the whole OR-group
    assert ") and store_products.store_id in ('s1')" in data_sql
