from fastapi import Depends, Query, Request
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.error_codes import E
from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.rate_limit import check_rate_limit
from app.core.redis import get_redis
from app.core.security import get_current_user
from app.models.user import User


async def get_authenticated_user(
    request: Request,
    user_id: str | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if user_id:
        request.state.user_id = user_id
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found", translation_key=E.USER_NOT_FOUND)
    return user


async def get_admin_user(user: User = Depends(get_authenticated_user)) -> User:
    if user.role != "admin":
        raise AuthorizationError("Admin access required", translation_key=E.ADMIN_ACCESS_REQUIRED)
    return user


class PaginationParams:
    def __init__(self, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
        self.skip = skip
        self.limit = limit


class ProductFilterParams:
    def __init__(
        self,
        category: str | None = Query(None, max_length=100),
        min_price: float | None = Query(None, ge=0),
        max_price: float | None = Query(None, ge=0),
        sort_by: str = Query("created_at", pattern=r"^(name|price|created_at)$"),
        sort_order: str = Query("desc", pattern=r"^(asc|desc)$"),
    ):
        self.category = category
        self.min_price = min_price
        self.max_price = max_price
        self.sort_by = sort_by
        self.sort_order = sort_order


class RateLimit:
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def __call__(self, request: Request, redis: AsyncRedis = Depends(get_redis)) -> None:
        await check_rate_limit(redis, request, max_requests=self.max_requests, window_seconds=self.window_seconds)
