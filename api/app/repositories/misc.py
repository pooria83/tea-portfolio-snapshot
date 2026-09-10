from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.activity_log import ActivityLog
from app.models.ai_description_version import AIDescriptionVersion
from app.models.brand import Brand
from app.models.product_image import ProductImage
from app.models.store import Store
from app.models.store_product import StoreProduct
from app.models.user_favorite import UserFavorite
from app.repositories.base import BaseRepository


class AIDescriptionVersionRepository(BaseRepository[AIDescriptionVersion]):
    model = AIDescriptionVersion
    TOUCHES: frozenset[str] = frozenset({"ai_description_versions"})

    async def add_version(self, version: AIDescriptionVersion) -> AIDescriptionVersion:
        self.db.add(version)
        await self.db.flush()
        return version


class UserFavoriteRepository(BaseRepository[UserFavorite]):
    model = UserFavorite
    TOUCHES: frozenset[str] = frozenset({"user_favorites"})

    async def upsert(self, user_id: str, store_id: str, product_id: str) -> None:
        stmt = pg_insert(UserFavorite).values(user_id=user_id, store_id=store_id, product_id=product_id)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_user_favorites_user_store_product")
        await self.db.execute(stmt)
        await self.db.flush()

    async def delete_by_user_store_product(self, user_id: str, store_id: str, product_id: str) -> None:
        await self.db.execute(
            delete(UserFavorite).where(
                UserFavorite.user_id == user_id,
                UserFavorite.store_id == store_id,
                UserFavorite.product_id == product_id,
            )
        )
        await self.db.flush()

    async def count_by_user(self, user_id: str) -> int:
        stmt = select(func.count()).select_from(UserFavorite).where(UserFavorite.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def list_with_details(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[tuple[StoreProduct, str | None, str | None, str | None, datetime]], int]:
        """Favorites joined with store name, brand name and first image.

        Returns (product, store_name, brand_name, image_url, created_at) rows.
        """
        first_image = (
            select(ProductImage.image_url)
            .where(ProductImage.product_id == StoreProduct.id, ProductImage.is_video == False)  # noqa: E712
            .order_by(ProductImage.sort_order.asc(), ProductImage.id.asc())
            .limit(1)
            .correlate(StoreProduct)
            .scalar_subquery()
        )
        stmt = (
            select(
                UserFavorite.created_at,
                StoreProduct,
                Store.name,
                Brand.name_en,
                first_image.label("image_url"),
            )
            .join(StoreProduct, StoreProduct.id == UserFavorite.product_id)
            .join(Store, Store.id == UserFavorite.store_id)
            .join(Brand, Brand.id == StoreProduct.brand, isouter=True)
            .where(UserFavorite.user_id == user_id)
            .order_by(UserFavorite.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).all()
        items: list[tuple[StoreProduct, str | None, str | None, str | None, datetime]] = []
        for row in rows:
            store_name = row.name if isinstance(row.name, str) else str(row.name)
            brand_name = row.name_en if row.name_en is not None else None
            image_url = row.image_url if row.image_url is not None else None
            items.append((row.StoreProduct, store_name, brand_name, image_url, row.created_at))
        return items, await self.count_by_user(user_id)


class ActivityLogRepository(BaseRepository[ActivityLog]):
    model = ActivityLog
    TOUCHES: frozenset[str] = frozenset({"activity_logs"})
