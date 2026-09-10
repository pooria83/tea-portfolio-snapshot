from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.product_type_image_view_type import ProductTypeImageViewType
    from app.models.product_variant import ProductVariant
    from app.models.store_product import StoreProduct


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("store_products.id", ondelete="CASCADE"), nullable=False)
    variant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    view_type_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("product_type_image_view_types.id"), nullable=True)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    alt_text_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    alt_text_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    alt_text_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_video: Mapped[bool] = mapped_column(Boolean, default=False)

    product: Mapped[StoreProduct] = relationship(back_populates="images")
    variant: Mapped[ProductVariant | None] = relationship(back_populates="images")
    view_type: Mapped[ProductTypeImageViewType | None] = relationship()
