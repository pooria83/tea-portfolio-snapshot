from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.models.store import Store
from app.models.store_member import StoreMember
from app.repositories.base import BaseRepository


class StoreRepository(BaseRepository[Store]):
    model = Store

    _list_relations = [
        joinedload(Store.category),
        joinedload(Store.store_type),
        joinedload(Store.country),
        joinedload(Store.price_unit),
    ]

    async def get_by_owner(self, owner_id: str) -> list[Store]:
        stmt = (
            select(Store).options(*self._list_relations).where(Store.owner_id == owner_id, Store.is_active == True)  # noqa: E712
        )
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_owner_store_count(self, owner_id: str) -> int:
        stmt = select(func.count()).select_from(Store).where(Store.owner_id == owner_id, Store.is_active == True)  # noqa: E712
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_by_user(self, user_id: str) -> list[Store]:
        stmt = (
            select(Store)
            .options(*self._list_relations)
            .where(
                Store.is_active == True,  # noqa: E712
                Store.id.in_(select(StoreMember.store_id).where(StoreMember.user_id == user_id)),
            )
        )
        result = await self.db.execute(stmt)
        member_stores = list(result.unique().scalars().all())

        owner_stores = await self.get_by_owner(user_id)
        seen = {s.id for s in owner_stores}
        for s in member_stores:
            if s.id not in seen:
                owner_stores.append(s)
        return owner_stores

    async def get_with_relations(self, store_id: str) -> Store | None:
        stmt = (
            select(Store)
            .options(
                joinedload(Store.category),
                joinedload(Store.store_type),
                joinedload(Store.country),
                joinedload(Store.price_unit),
                joinedload(Store.working_hours),
            )
            .where(Store.id == store_id)
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()
