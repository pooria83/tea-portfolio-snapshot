from typing import Any

from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import invalidate_tables
from app.models.base import Base


class BaseRepository[T: Base]:
    model: type[T]

    # Tables this repository's reads can touch — used for cache invalidation:
    # a write to table X invalidates every cached read whose TOUCHES contains X.
    TOUCHES: frozenset[str] = frozenset()

    def __init__(self, db: AsyncSession, redis: AsyncRedis | None = None) -> None:
        self.db = db
        self.redis = redis

    async def _invalidate(self) -> None:
        """Invalidate cached reads for every table this repository touches."""
        if self.redis is not None and self.TOUCHES:
            await invalidate_tables(self.redis, self.TOUCHES)

    async def get(self, id: str) -> T | None:
        return await self.db.get(self.model, id)

    async def list(self, skip: int = 0, limit: int = 20, **filters: Any) -> list[T]:
        stmt = select(self.model)
        for field, value in filters.items():
            if hasattr(self.model, field):
                stmt = stmt.where(getattr(self.model, field) == value)
        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add(self, instance: T) -> T:
        self.db.add(instance)
        await self.db.flush()
        await self._invalidate()
        return instance

    async def delete(self, instance: T) -> None:
        await self.db.delete(instance)
        await self.db.flush()
        await self._invalidate()
