from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError


@pytest.mark.asyncio
async def test_get_product_not_found():
    with patch("app.services.product_service.ProductRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get_active.return_value = None
        mock_repo_cls.return_value = mock_repo

        from app.services.product_service import get_product

        with pytest.raises(NotFoundError, match="Product not found"):
            await get_product(AsyncMock(), "nonexistent")


@pytest.mark.asyncio
async def test_get_product_success():
    with patch("app.services.product_service.ProductRepository") as mock_repo_cls:
        product = MagicMock()
        mock_repo = AsyncMock()
        mock_repo.get_active.return_value = product
        mock_repo_cls.return_value = mock_repo

        from app.services.product_service import get_product

        result = await get_product(AsyncMock(), "product-1")
        assert result is product


@pytest.mark.asyncio
async def test_list_products_no_filters():
    with patch("app.services.product_service.ProductRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.count_active.return_value = 2
        mock_repo.list_active.return_value = [MagicMock(), MagicMock()]
        mock_repo_cls.return_value = mock_repo

        from app.core.deps import PaginationParams
        from app.services.product_service import list_products

        pagination = PaginationParams(skip=0, limit=20)
        items, total = await list_products(AsyncMock(), pagination)
        assert total == 2
        assert len(items) == 2
        mock_repo.count_active.assert_called_once_with(category=None, min_price=None, max_price=None)
        mock_repo.list_active.assert_called_once_with(
            skip=0,
            limit=20,
            category=None,
            min_price=None,
            max_price=None,
            sort_by="created_at",
            sort_order="desc",
        )


@pytest.mark.asyncio
async def test_list_products_with_filters():
    with patch("app.services.product_service.ProductRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.count_active.return_value = 1
        mock_repo.list_active.return_value = [MagicMock()]
        mock_repo_cls.return_value = mock_repo

        from app.core.deps import PaginationParams, ProductFilterParams
        from app.services.product_service import list_products

        pagination = PaginationParams(skip=0, limit=10)
        filters = ProductFilterParams(category="cat-1", min_price=10.0, max_price=100.0, sort_by="price", sort_order="asc")
        items, total = await list_products(AsyncMock(), pagination, filters)
        assert total == 1
        mock_repo.count_active.assert_called_once_with(category="cat-1", min_price=10.0, max_price=100.0)
        mock_repo.list_active.assert_called_once_with(
            skip=0,
            limit=10,
            category="cat-1",
            min_price=10.0,
            max_price=100.0,
            sort_by="price",
            sort_order="asc",
        )


@pytest.mark.asyncio
async def test_list_products_empty():
    with patch("app.services.product_service.ProductRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.count_active.return_value = 0
        mock_repo.list_active.return_value = []
        mock_repo_cls.return_value = mock_repo

        from app.core.deps import PaginationParams
        from app.services.product_service import list_products

        items, total = await list_products(AsyncMock(), PaginationParams(skip=0, limit=20))
        assert total == 0
        assert items == []


@pytest.mark.asyncio
async def test_update_product_success():
    with patch("app.services.product_service.ProductRepository") as mock_repo_cls:
        product = MagicMock()
        mock_repo = AsyncMock()
        mock_repo.get.return_value = product
        mock_repo_cls.return_value = mock_repo

        mock_db = AsyncMock(spec=AsyncSession)

        from app.schemas.product import ProductUpdate
        from app.services.product_service import update_product

        data = ProductUpdate(name="Updated", price=20.0)
        result = await update_product(mock_db, "product-1", data)
        assert result.name == "Updated"
        assert result.price == 20.0
        mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_product_not_found():
    with patch("app.services.product_service.ProductRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None
        mock_repo_cls.return_value = mock_repo

        from app.schemas.product import ProductUpdate
        from app.services.product_service import update_product

        data = ProductUpdate(name="X")
        with pytest.raises(NotFoundError, match="Product not found"):
            await update_product(AsyncMock(), "nonexistent", data)


@pytest.mark.asyncio
async def test_delete_product_success():
    with patch("app.services.product_service.ProductRepository") as mock_repo_cls:
        product = MagicMock()
        mock_repo = AsyncMock()
        mock_repo.soft_delete.return_value = product
        mock_repo_cls.return_value = mock_repo

        from app.services.product_service import delete_product

        result = await delete_product(AsyncMock(), "product-1")
        assert result is None


@pytest.mark.asyncio
async def test_delete_product_not_found():
    with patch("app.services.product_service.ProductRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.soft_delete.return_value = None
        mock_repo_cls.return_value = mock_repo

        from app.services.product_service import delete_product

        with pytest.raises(NotFoundError, match="Product not found"):
            await delete_product(AsyncMock(), "nonexistent")
