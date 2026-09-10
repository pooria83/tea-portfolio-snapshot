from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RateLimit, get_authenticated_user
from app.core.response import APIResponse, paginated
from app.models.user import User
from app.schemas.favorite import FavoriteItemResponse
from app.services import favorite_service

router = APIRouter(prefix="/users/me/favorites", tags=["favorites"])

MAX_FAVORITES_LIMIT = 100


@router.get(
    "",
    response_model=APIResponse[list[FavoriteItemResponse]],
    dependencies=[Depends(RateLimit(max_requests=60, window_seconds=60))],
)
async def list_favorites(
    skip: int = 0,
    limit: int = 20,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[FavoriteItemResponse]]:
    items, total = await favorite_service.list_favorites(db, user, skip, min(limit, MAX_FAVORITES_LIMIT))
    return paginated(items, total, skip, limit)


@router.put(
    "/{store_id}/{product_id}",
    status_code=204,
    dependencies=[Depends(RateLimit(max_requests=60, window_seconds=60))],
)
async def add_favorite(
    store_id: str,
    product_id: str,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await favorite_service.add_favorite(db, user, store_id, product_id)


@router.delete(
    "/{store_id}/{product_id}",
    status_code=204,
    dependencies=[Depends(RateLimit(max_requests=60, window_seconds=60))],
)
async def remove_favorite(
    store_id: str,
    product_id: str,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await favorite_service.remove_favorite(db, user, store_id, product_id)
