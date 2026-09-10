from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.attribute_option import AttributeOption
    from app.models.product_color_set import ProductColorSet
    from app.models.product_image import ProductImage
    from app.models.store_product import StoreProduct


class ProductVariant(Base, TimestampMixin):
    __tablename__ = "product_variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("store_products.id", ondelete="CASCADE"), nullable=False)
    color_set_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("product_color_sets.id"), nullable=True)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    original_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sale_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped[StoreProduct] = relationship(back_populates="variants")
    color_set: Mapped[ProductColorSet | None] = relationship()
    attribute_options: Mapped[list[AttributeOption]] = relationship(
        secondary="variant_attribute_options",
        back_populates="variants",
    )
    images: Mapped[list[ProductImage]] = relationship(back_populates="variant")
