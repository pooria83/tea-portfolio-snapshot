from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.response import APIResponse, success
from app.repositories.reference import StoreTypeRepository
from app.schemas.store_type import StoreTypeResponse

router = APIRouter(prefix="/store-types", tags=["store-types"])


@router.get("", response_model=APIResponse[list[StoreTypeResponse]])
async def list_store_types(
    locale: str = Query("en", pattern=r"^(ar|en|fa)$"),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[list[StoreTypeResponse]]:
    items = await StoreTypeRepository(db, redis).list_active_dto(locale)
    return success([StoreTypeResponse.model_validate(item) for item in items])
