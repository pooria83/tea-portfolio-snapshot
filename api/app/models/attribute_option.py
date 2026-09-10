from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.attribute import Attribute
    from app.models.product_variant import ProductVariant


class AttributeOption(Base):
    __tablename__ = "attribute_options"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    attribute_id: Mapped[str] = mapped_column(String(36), ForeignKey("attributes.id"), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    value_ar: Mapped[str] = mapped_column(Text, nullable=False)
    value_en: Mapped[str] = mapped_column(Text, nullable=False)
    value_fa: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color_hex: Mapped[str | None] = mapped_column(String(7), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    color_family: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_major: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    attribute: Mapped[Attribute] = relationship(back_populates="options")
    variants: Mapped[list[ProductVariant]] = relationship(
        secondary="variant_attribute_options",
        back_populates="attribute_options",
    )
