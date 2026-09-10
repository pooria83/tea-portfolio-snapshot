from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.response import APIResponse, success
from app.repositories.catalog import CategoryRepository
from app.schemas.category import CategoryResponse

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=APIResponse[list[CategoryResponse]])
async def list_categories(
    locale: str = Query("en", pattern=r"^(ar|en|fa)$"),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[list[CategoryResponse]]:
    categories = await CategoryRepository(db, redis).list_all_dto()
    name_map = {"ar": "name_ar", "en": "name_en", "fa": "name_fa"}
    name_col = name_map.get(locale, "name_en")
    items = [CategoryResponse(id=str(c["id"]), name=str(c[name_col])) for c in categories]
    return success(items)
