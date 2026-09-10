from fastapi import APIRouter, Depends
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import RateLimit
from app.core.redis import get_redis
from app.services.product_info_service import get_product_info

router = APIRouter(prefix="/product-info", tags=["product-info"])


@router.get("/{product_id}/{lang}", dependencies=[Depends(RateLimit(max_requests=120, window_seconds=60))])
async def product_info(
    product_id: str,
    lang: str,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> dict[str, object]:
    return await get_product_info(db, product_id, lang, redis)
