from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.store import Store


@pytest.mark.asyncio
async def test_store_repo_get_by_owner():
    from app.repositories.store import StoreRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
    mock_db.execute.return_value = mock_result

    repo = StoreRepository(mock_db)
    result = await repo.get_by_owner("owner-1")
    assert len(result) == 2


@pytest.mark.asyncio
async def test_store_repo_get_by_owner_empty():
    from app.repositories.store import StoreRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    repo = StoreRepository(mock_db)
    result = await repo.get_by_owner("owner-1")
    assert result == []


@pytest.mark.asyncio
async def test_store_repo_get_owner_store_count():
    from app.repositories.store import StoreRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 2
    mock_db.execute.return_value = mock_result

    repo = StoreRepository(mock_db)
    result = await repo.get_owner_store_count("owner-1")
    assert result == 2


@pytest.mark.asyncio
async def test_store_repo_get_owner_store_count_zero():
    from app.repositories.store import StoreRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    mock_db.execute.return_value = mock_result

    repo = StoreRepository(mock_db)
    result = await repo.get_owner_store_count("owner-1")
    assert result == 0


@pytest.mark.asyncio
async def test_store_repo_get_with_relations():
    from app.repositories.store import StoreRepository

    mock_db = AsyncMock()
    store = MagicMock(spec=Store)
    mock_result = MagicMock()
    mock_result.unique.return_value.scalar_one_or_none.return_value = store
    mock_db.execute.return_value = mock_result

    repo = StoreRepository(mock_db)
    result = await repo.get_with_relations("store-1")
    assert result is store


@pytest.mark.asyncio
async def test_store_repo_get_with_relations_not_found():
    from app.repositories.store import StoreRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    repo = StoreRepository(mock_db)
    result = await repo.get_with_relations("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_store_repo_get_by_user_owner_only():
    from app.repositories.store import StoreRepository

    mock_db = AsyncMock()
    mock_store = MagicMock(spec=Store)
    mock_store.id = "store-1"
    mock_result = MagicMock()
    mock_result.unique.return_value.scalars.return_value.all.return_value = [mock_store]
    mock_db.execute.return_value = mock_result

    repo = StoreRepository(mock_db)
    result = await repo.get_by_user("user-1")
    assert result == [mock_store]


@pytest.mark.asyncio
async def test_store_repo_get_by_user_member_only():
    from app.repositories.store import StoreRepository

    mock_db = AsyncMock()
    mock_store = MagicMock(spec=Store)
    mock_store.id = "store-2"
    mock_result = MagicMock()
    mock_result.unique.return_value.scalars.return_value.all.return_value = [mock_store]
    mock_db.execute.return_value = mock_result

    repo = StoreRepository(mock_db)
    result = await repo.get_by_user("user-2")
    assert result == [mock_store]


@pytest.mark.asyncio
async def test_store_repo_get_by_user_owner_and_member_dedup():
    from app.repositories.store import StoreRepository

    mock_db = AsyncMock()
    owner_store = MagicMock(spec=Store)
    owner_store.id = "store-1"
    member_store = MagicMock(spec=Store)
    member_store.id = "store-2"
    member_store_dup = MagicMock(spec=Store)
    member_store_dup.id = "store-1"

    # First call (member query): returns [member_store, member_store_dup]
    # Second call (owner via get_by_owner): returns [owner_store]
    mock_result = MagicMock()
    mock_result.unique.return_value.scalars.return_value.all.side_effect = [
        [member_store, member_store_dup],
        [owner_store],
    ]
    mock_db.execute.return_value = mock_result

    repo = StoreRepository(mock_db)
    result = await repo.get_by_user("user-3")
    assert len(result) == 2
    assert result[0].id == "store-1"
    assert result[1].id == "store-2"


@pytest.mark.asyncio
async def test_store_repo_get_by_user_empty():
    from app.repositories.store import StoreRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalars.return_value.all.side_effect = [[], []]
    mock_db.execute.return_value = mock_result

    repo = StoreRepository(mock_db)
    result = await repo.get_by_user("user-none")
    assert result == []


@pytest.mark.asyncio
async def test_product_type_repo_get_with_attributes():
    from app.repositories.catalog import ProductTypeRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    pt = MagicMock()
    mock_result.unique.return_value.scalar_one_or_none.return_value = pt
    mock_db.execute.return_value = mock_result

    repo = ProductTypeRepository(mock_db)
    result = await repo.get_with_attributes("pt-1")
    assert result is pt


@pytest.mark.asyncio
async def test_product_type_repo_get_with_attributes_not_found():
    from app.repositories.catalog import ProductTypeRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    repo = ProductTypeRepository(mock_db)
    result = await repo.get_with_attributes("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_product_type_repo_list_all():
    from app.repositories.catalog import ProductTypeRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
    mock_db.execute.return_value = mock_result

    repo = ProductTypeRepository(mock_db)
    result = await repo.list_all()
    assert len(result) == 2


@pytest.mark.asyncio
async def test_attribute_repo_list_by_group():
    from app.repositories.catalog import AttributeRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalars.return_value.all.return_value = [MagicMock()]
    mock_db.execute.return_value = mock_result

    repo = AttributeRepository(mock_db)
    result = await repo.list_by_group("grp-fit")
    assert len(result) == 1


@pytest.mark.asyncio
async def test_attribute_repo_get_with_options():
    from app.repositories.catalog import AttributeRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    attr = MagicMock()
    mock_result.unique.return_value.scalar_one_or_none.return_value = attr
    mock_db.execute.return_value = mock_result

    repo = AttributeRepository(mock_db)
    result = await repo.get_with_options("attr-1")
    assert result is attr


@pytest.mark.asyncio
async def test_attribute_repo_get_with_options_not_found():
    from app.repositories.catalog import AttributeRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    repo = AttributeRepository(mock_db)
    result = await repo.get_with_options("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_category_repo_list_by_product_type():
    from app.repositories.catalog import CategoryRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
    mock_db.execute.return_value = mock_result

    repo = CategoryRepository(mock_db)
    result = await repo.list_by_product_type("pt-1")
    assert len(result) == 2


@pytest.mark.asyncio
async def test_category_repo_list_root():
    from app.repositories.catalog import CategoryRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [MagicMock()]
    mock_db.execute.return_value = mock_result

    repo = CategoryRepository(mock_db)
    result = await repo.list_root()
    assert len(result) == 1


@pytest.mark.asyncio
async def test_category_repo_get_children():
    from app.repositories.catalog import CategoryRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
    mock_db.execute.return_value = mock_result

    repo = CategoryRepository(mock_db)
    result = await repo.get_children("parent-1")
    assert len(result) == 2


@pytest.mark.asyncio
async def test_category_repo_get_children_none():
    from app.repositories.catalog import CategoryRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    repo = CategoryRepository(mock_db)
    result = await repo.get_children("parent-1")
    assert result == []


@pytest.mark.asyncio
async def test_store_product_repo_get_with_all():
    from app.repositories.product_definition import StoreProductRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    product = MagicMock()
    mock_result.unique.return_value.scalar_one_or_none.return_value = product
    mock_db.execute.return_value = mock_result

    repo = StoreProductRepository(mock_db)
    result = await repo.get_with_all("product-1")
    assert result is product


@pytest.mark.asyncio
async def test_store_product_repo_get_with_all_not_found():
    from app.repositories.product_definition import StoreProductRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    repo = StoreProductRepository(mock_db)
    result = await repo.get_with_all("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_store_product_repo_list_by_store():
    from app.repositories.product_definition import StoreProductRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
    mock_db.execute.return_value = mock_result

    repo = StoreProductRepository(mock_db)
    result = await repo.list_by_store("store-1", skip=0, limit=20)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_store_product_repo_list_by_store_empty():
    from app.repositories.product_definition import StoreProductRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    repo = StoreProductRepository(mock_db)
    result = await repo.list_by_store("store-1", skip=0, limit=20)
    assert result == []


@pytest.mark.asyncio
async def test_store_product_repo_list_by_store_ids():
    from app.repositories.product_definition import StoreProductRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
    mock_db.execute.return_value = mock_result

    repo = StoreProductRepository(mock_db)
    result = await repo.list_by_store_ids(["s1", "s2"], skip=0, limit=20)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_store_product_repo_delete_attribute_values():
    from app.repositories.product_definition import StoreProductRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    attr_val = MagicMock()
    mock_result.scalars.return_value.all.return_value = [attr_val]
    mock_db.execute.return_value = mock_result

    repo = StoreProductRepository(mock_db)
    await repo.delete_attribute_values("product-1")
    mock_db.execute.assert_awaited_once()
    mock_db.delete.assert_awaited_once_with(attr_val)


@pytest.mark.asyncio
async def test_store_product_repo_delete_sizes():
    from app.repositories.product_definition import StoreProductRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    size = MagicMock()
    mock_result.scalars.return_value.all.return_value = [size]
    mock_db.execute.return_value = mock_result

    repo = StoreProductRepository(mock_db)
    await repo.delete_sizes("product-1")
    mock_db.execute.assert_awaited_once()
    mock_db.delete.assert_awaited_once_with(size)


@pytest.mark.asyncio
async def test_store_product_repo_delete_variants():
    from app.repositories.product_definition import StoreProductRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    variant = MagicMock()
    mock_result.scalars.return_value.all.return_value = [variant]
    mock_db.execute.return_value = mock_result

    repo = StoreProductRepository(mock_db)
    await repo.delete_variants("product-1")
    mock_db.execute.assert_awaited_once()
    mock_db.delete.assert_awaited_once_with(variant)


@pytest.mark.asyncio
async def test_image_view_type_repo_list_by_product_type():
    from app.repositories.catalog import ImageViewTypeRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [MagicMock()]
    mock_db.execute.return_value = mock_result

    repo = ImageViewTypeRepository(mock_db)
    result = await repo.list_by_product_type("pt-1")
    assert len(result) == 1


@pytest.mark.asyncio
async def test_store_product_repo_count_by_store():
    from app.repositories.product_definition import StoreProductRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    mock_db.execute.return_value = mock_result

    repo = StoreProductRepository(mock_db)
    result = await repo.count_by_store("store-1")
    assert result == 5


@pytest.mark.asyncio
async def test_store_product_repo_count_by_store_ids():
    from app.repositories.product_definition import StoreProductRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 3
    mock_db.execute.return_value = mock_result

    repo = StoreProductRepository(mock_db)
    result = await repo.count_by_store_ids(["s1", "s2"])
    assert result == 3


@pytest.mark.asyncio
async def test_store_product_repo_search_by_name_short_query():
    from app.repositories.product_definition import StoreProductRepository

    mock_db = AsyncMock()
    products = [MagicMock(), MagicMock()]
    count_result = MagicMock()
    count_result.scalar_one.return_value = 2

    mock_result = MagicMock()
    mock_result.unique.return_value.scalars.return_value.all.return_value = products
    mock_db.execute.side_effect = [mock_result, count_result]

    repo = StoreProductRepository(mock_db)
    items, total = await repo.search_by_name("ab", skip=0, limit=20)
    assert len(items) == 2
    assert total == 2


@pytest.mark.asyncio
async def test_store_product_repo_search_by_name_short_query_with_store_ids():
    from app.repositories.product_definition import StoreProductRepository

    mock_db = AsyncMock()
    products = [MagicMock()]
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1

    mock_result = MagicMock()
    mock_result.unique.return_value.scalars.return_value.all.return_value = products
    mock_db.execute.side_effect = [mock_result, count_result]

    repo = StoreProductRepository(mock_db)
    items, total = await repo.search_by_name("xy", store_ids=["s1"], skip=0, limit=20)
    assert len(items) == 1
    assert total == 1


@pytest.mark.asyncio
async def test_store_product_repo_search_by_name_trigram():
    from app.repositories.product_definition import StoreProductRepository

    mock_db = AsyncMock()
    products = [MagicMock()]
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1

    mock_result = MagicMock()
    mock_result.unique.return_value.scalars.return_value.all.return_value = products
    mock_db.execute.side_effect = [mock_result, count_result]

    repo = StoreProductRepository(mock_db)
    items, total = await repo.search_by_name("red dress", skip=0, limit=20)
    assert len(items) == 1
    assert total == 1


@pytest.mark.asyncio
async def test_attribute_repo_list_by_product_type():
    from app.repositories.catalog import AttributeRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
    mock_db.execute.return_value = mock_result

    repo = AttributeRepository(mock_db)
    result = await repo.list_by_product_type("pt-1")
    assert len(result) == 2


@pytest.mark.asyncio
async def test_category_repo_list_all():
    from app.repositories.catalog import CategoryRepository

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [MagicMock(), MagicMock(), MagicMock()]
    mock_db.execute.return_value = mock_result

    repo = CategoryRepository(mock_db)
    result = await repo.list_all()
    assert len(result) == 3


@pytest.mark.asyncio
async def test_store_product_repo_search_by_name_trigram_store_scope_anded():
    """Regression: trigram search must AND store scope with the similarity OR-group.

    The old build appended ``store_id IN (...)`` into the same list combined with
    ``or_()``, so the store condition alone matched every owned product and the
    query text was ignored.
    """
    from app.repositories.product_definition import StoreProductRepository

    captured: list = []

    def _side_effect(stmt, *args, **kwargs):
        captured.append(stmt)
        rows_result = MagicMock()
        rows_result.unique.return_value.scalars.return_value.all.return_value = []
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        return rows_result if len(captured) == 1 else count_result

    db = AsyncMock()
    db.execute.side_effect = _side_effect

    await StoreProductRepository(db).search_by_name("bra", store_ids=["s1"], skip=0, limit=20)

    assert len(captured) == 2, "expected the data statement and the count statement"
    for stmt in captured:
        sql = " ".join(str(stmt.compile(compile_kwargs={"literal_binds": True})).split())
        assert ") AND store_products.store_id IN" in sql, f"store scope not AND-ed with name match: {sql}"
        assert "OR store_products.store_id IN" not in sql, f"store scope leaked into the name OR-group: {sql}"


@pytest.mark.asyncio
async def test_store_product_repo_search_by_name_multi_word_similarity_ranking():
    """Full-search trigram path shares tokenized scoring with the light method."""
    from app.repositories.product_definition import StoreProductRepository

    captured: list = []

    def _side_effect(stmt, *args, **kwargs):
        captured.append(stmt)
        rows_result = MagicMock()
        rows_result.unique.return_value.scalars.return_value.all.return_value = []
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        return rows_result if len(captured) == 1 else count_result

    db = AsyncMock()
    db.execute.side_effect = _side_effect

    await StoreProductRepository(db).search_by_name("RAFFIA VISOR", store_ids=["s1"], skip=0, limit=20)

    for i, stmt in enumerate(captured):
        sql = " ".join(str(stmt.compile(compile_kwargs={"literal_binds": True})).split()).lower()
        assert "like lower('%raffia visor%')" in sql
        assert "name_en % 'raffia'" in sql and "name_en % 'visor'" in sql
        assert ") and store_products.store_id in ('s1')" in sql
        if i == 0:
            order_clause = sql.split(" order by ")[1]
            assert "then 1.0 else 0.0 end" in order_clause
            assert "greatest(similarity(store_products.name_en, 'raffia'), similarity(store_products.name_ar, 'raffia'))" in order_clause
