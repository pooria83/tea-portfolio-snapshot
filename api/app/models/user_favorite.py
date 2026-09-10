from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.store import Store
    from app.models.store_product import StoreProduct
    from app.models.user import User


class UserFavorite(Base, TimestampMixin):
    __tablename__ = "user_favorites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("store_products.id", ondelete="CASCADE"), nullable=False)

    user: Mapped[User] = relationship(back_populates="favorites")
    product: Mapped[StoreProduct] = relationship()
    store: Mapped[Store] = relationship()

    __table_args__ = (UniqueConstraint("user_id", "store_id", "product_id", name="uq_user_favorites_user_store_product"),)
