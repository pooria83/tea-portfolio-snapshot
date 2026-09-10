import hashlib
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.models.user import RefreshToken
from app.repositories.base import BaseRepository


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    model = RefreshToken

    async def get_valid(self, token: str) -> RefreshToken | None:
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token == hash_token(token),
                RefreshToken.revoked.is_(False),
                RefreshToken.expires_at > datetime.now(UTC),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, token: str) -> RefreshToken | None:
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token == hash_token(token),
                RefreshToken.expires_at > datetime.now(UTC),
            )
        )
        return result.scalar_one_or_none()

    async def revoke_all_for_user(self, user_id: str) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked.is_(False),
            )
            .values(revoked=True)
        )
        await self.db.flush()

    async def revoke_by_hash(self, token: str) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.token == hash_token(token),
                RefreshToken.revoked.is_(False),
            )
            .values(revoked=True)
        )
        await self.db.flush()
