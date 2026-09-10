from typing import Any

from sqlalchemy import Select, func, select

from app.models.product import Product
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    model = Product

    def _apply_filters(
        self,
        stmt: Select[Any],
        category: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
    ) -> Select[Any]:
        stmt = stmt.where(Product.is_active.is_(True))
        if category:
            stmt = stmt.where(Product.category == category)
        if min_price is not None:
            stmt = stmt.where(Product.price >= min_price)
        if max_price is not None:
            stmt = stmt.where(Product.price <= max_price)
        return stmt

    async def count_active(self, category: str | None = None, min_price: float | None = None, max_price: float | None = None) -> int:
        stmt = self._apply_filters(select(func.count(Product.id)), category, min_price, max_price)
        result = await self.db.execute(stmt)
        return result.scalar_one()  # type: ignore[no-any-return]

    async def list_active(
        self,
        skip: int = 0,
        limit: int = 20,
        category: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> list[Product]:
        stmt = self._apply_filters(select(Product), category, min_price, max_price)
        sort_col = getattr(Product, sort_by)
        stmt = stmt.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())
        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_active(self, product_id: str) -> Product | None:
        result = await self.db.execute(select(Product).where(Product.id == product_id, Product.is_active.is_(True)))
        return result.scalar_one_or_none()

    async def soft_delete(self, product_id: str) -> Product | None:
        product = await self.get(product_id)
        if product:
            product.is_active = False
            await self.db.flush()
        return product
