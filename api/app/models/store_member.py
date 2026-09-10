from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.store import Store
    from app.models.user import User


class StoreMember(Base, TimestampMixin):
    __tablename__ = "store_team_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(Enum("owner", "manager", name="store_member_role"), nullable=False)

    store: Mapped[Store] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="store_memberships")

    __table_args__ = (UniqueConstraint("store_id", "user_id", name="uq_store_team_members_store_user"),)
