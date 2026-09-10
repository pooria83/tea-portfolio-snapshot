from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.ai_description_version import AIDescriptionVersion
    from app.models.brand import Brand
    from app.models.product_attribute_value import ProductAttributeValue
    from app.models.product_color_set import ProductColorSet
    from app.models.product_image import ProductImage
    from app.models.product_outfit import ProductOutfit
    from app.models.product_piece import ProductPiece
    from app.models.product_size import ProductSize
    from app.models.product_variant import ProductVariant
    from app.models.store import Store


class StoreProduct(Base, TimestampMixin):
    __tablename__ = "store_products"
    __table_args__ = (UniqueConstraint("store_id", "source_url", name="uq_store_product_source"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id"), nullable=False)
    product_type_id: Mapped[str] = mapped_column(String(36), ForeignKey("product_types.id"), nullable=False)
    category_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("categories.id"), nullable=True)

    name_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    name_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    name_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_description_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    long_description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    long_description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    long_description_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_description_fa: Mapped[str | None] = mapped_column(Text, nullable=True)

    brand: Mapped[str | None] = mapped_column(String(36), ForeignKey("brands.id"), nullable=True)
    slug: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    has_variants: Mapped[bool] = mapped_column(Boolean, default=False)
    is_multi_piece: Mapped[bool] = mapped_column(Boolean, default=False)

    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    original_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sale_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sale_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sale_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="SAR")

    quantity: Mapped[int] = mapped_column(Integer, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5)

    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_unit: Mapped[str] = mapped_column(String(10), default="kg")

    collection: Mapped[str | None] = mapped_column(String(255), nullable=True)
    collection_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    visibility_regions: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    country_of_origin: Mapped[str | None] = mapped_column(String(100), nullable=True)
    care_instructions_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    care_instructions_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    care_instructions_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_height: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_wears_size: Mapped[str | None] = mapped_column(String(20), nullable=True)
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_title_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_title_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_title_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_description_fa: Mapped[str | None] = mapped_column(Text, nullable=True)

    ai_search_boost: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    store: Mapped[Store] = relationship()
    brand_obj: Mapped[Brand | None] = relationship(back_populates="products")
    attribute_values: Mapped[list[ProductAttributeValue]] = relationship(back_populates="product", cascade="all, delete-orphan")
    images: Mapped[list[ProductImage]] = relationship(back_populates="product", cascade="all, delete-orphan")
    sizes: Mapped[list[ProductSize]] = relationship(back_populates="product", cascade="all, delete-orphan")
    variants: Mapped[list[ProductVariant]] = relationship(back_populates="product", cascade="all, delete-orphan")
    pieces: Mapped[list[ProductPiece]] = relationship(back_populates="product", cascade="all, delete-orphan", order_by="ProductPiece.sort_order")
    color_sets: Mapped[list[ProductColorSet]] = relationship(back_populates="product", cascade="all, delete-orphan", order_by="ProductColorSet.sort_order")
    ai_description_versions: Mapped[list[AIDescriptionVersion]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="AIDescriptionVersion.created_at.desc()",
    )
    outfits: Mapped[list[ProductOutfit]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        foreign_keys="ProductOutfit.product_id",
    )
