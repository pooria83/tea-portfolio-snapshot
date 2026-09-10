from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.attribute import Attribute
    from app.models.store_product import StoreProduct


class ProductAttributeValue(Base):
    __tablename__ = "product_attribute_values"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("store_products.id", ondelete="CASCADE"), nullable=False)
    attribute_id: Mapped[str] = mapped_column(String(36), ForeignKey("attributes.id"), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)

    product: Mapped[StoreProduct] = relationship(back_populates="attribute_values")
    attribute: Mapped[Attribute] = relationship()
