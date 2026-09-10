from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.attribute_option import AttributeOption
    from app.models.product_piece import ProductPiece
    from app.models.store_product import StoreProduct


class ProductColorSet(Base, TimestampMixin):
    __tablename__ = "product_color_sets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("store_products.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped[StoreProduct] = relationship(back_populates="color_sets")
    values: Mapped[list[ProductColorSetValue]] = relationship(back_populates="color_set", cascade="all, delete-orphan")


class ProductColorSetValue(Base, TimestampMixin):
    __tablename__ = "product_color_set_values"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    color_set_id: Mapped[str] = mapped_column(String(36), ForeignKey("product_color_sets.id", ondelete="CASCADE"), nullable=False)
    piece_id: Mapped[str] = mapped_column(String(36), ForeignKey("product_pieces.id", ondelete="CASCADE"), nullable=False)
    color_option_id: Mapped[str] = mapped_column(String(36), ForeignKey("attribute_options.id"), nullable=False)

    color_set: Mapped[ProductColorSet] = relationship(back_populates="values")
    piece: Mapped[ProductPiece] = relationship()
    color_option: Mapped[AttributeOption] = relationship()

    __table_args__ = (UniqueConstraint("color_set_id", "piece_id", name="uq_color_set_piece"),)
