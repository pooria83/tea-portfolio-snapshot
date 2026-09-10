from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.store_member import StoreMember
from app.models.user import User
from app.repositories.base import BaseRepository


class StoreMemberRepository(BaseRepository[StoreMember]):
    model = StoreMember

    async def get_by_store(self, store_id: str) -> list[StoreMember]:
        stmt = select(StoreMember).options(joinedload(StoreMember.user)).where(StoreMember.store_id == store_id).order_by(StoreMember.created_at)
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_by_store_and_user(self, store_id: str, user_id: str) -> StoreMember | None:
        stmt = select(StoreMember).where(
            StoreMember.store_id == store_id,
            StoreMember.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def find_user_by_phone(self, phone: str) -> User | None:
        stmt = select(User).where(User.phone == phone)
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def find_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def is_last_owner(self, store_id: str) -> bool:
        stmt = select(StoreMember).where(
            StoreMember.store_id == store_id,
            StoreMember.role == "owner",
        )
        result = await self.db.execute(stmt)
        owners = list(result.scalars().all())
        return len(owners) <= 1
