from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.store_product import StoreProduct


class ProductOutfit(Base):
    __tablename__ = "product_outfits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("store_products.id"), nullable=False)
    matches_product_id: Mapped[str] = mapped_column(String(36), ForeignKey("store_products.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped[StoreProduct] = relationship(back_populates="outfits", foreign_keys=[product_id])
