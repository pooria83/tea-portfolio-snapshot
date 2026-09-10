from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.repositories.misc import UserFavoriteRepository
from app.schemas.favorite import FavoriteItemResponse
from app.services.product_definition_service import get_store_product


def _resolve_url(url: str) -> str:
    if url and not url.startswith("http"):
        return f"{settings.minio_public_url}/{url}"
    return url


async def add_favorite(db: AsyncSession, user: User, store_id: str, product_id: str) -> None:
    product = await get_store_product(db, product_id, store_id)
    await UserFavoriteRepository(db).upsert(user.id, store_id, product.id)


async def remove_favorite(db: AsyncSession, user: User, store_id: str, product_id: str) -> None:
    await UserFavoriteRepository(db).delete_by_user_store_product(user.id, store_id, product_id)


async def list_favorites(
    db: AsyncSession,
    user: User,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[FavoriteItemResponse], int]:
    repo = UserFavoriteRepository(db)
    rows, total = await repo.list_with_details(user.id, skip, limit)
    items = [
        FavoriteItemResponse(
            id=product.id,
            store_id=product.store_id,
            store_name=store_name,
            name_ar=product.name_ar,
            name_en=product.name_en,
            name_fa=product.name_fa,
            brand=brand_name,
            price=product.price,
            original_price=product.original_price,
            sale_price=product.sale_price,
            currency=product.currency,
            image_url=_resolve_url(image_url) if image_url else None,
            created_at=created_at,
        )
        for product, store_name, brand_name, image_url, created_at in rows
    ]
    return items, total
