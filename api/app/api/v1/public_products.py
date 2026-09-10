from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RateLimit
from app.core.redis import get_redis
from app.core.response import APIResponse, success
from app.schemas.product_definition import StoreProductListItem
from app.services import product_definition_service

router = APIRouter(prefix="/public/products", tags=["public"])

MAX_RANDOM_LIMIT = 20


@router.get(
    "/random",
    response_model=APIResponse[list[StoreProductListItem]],
    dependencies=[Depends(RateLimit(max_requests=60, window_seconds=60))],
)
async def random_products(
    limit: int = Query(MAX_RANDOM_LIMIT, ge=1, le=MAX_RANDOM_LIMIT),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[list[StoreProductListItem]]:
    products = await product_definition_service.random_products_light(db, redis, limit=limit)
    return success([StoreProductListItem.model_validate(p) for p in products])
