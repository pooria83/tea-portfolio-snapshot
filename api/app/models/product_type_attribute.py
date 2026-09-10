from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.attribute import Attribute
    from app.models.product_type import ProductType


class ProductTypeAttribute(Base):
    __tablename__ = "product_type_attributes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_type_id: Mapped[str] = mapped_column(String(36), ForeignKey("product_types.id"), nullable=False)
    attribute_id: Mapped[str] = mapped_column(String(36), ForeignKey("attributes.id"), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    product_type: Mapped[ProductType] = relationship(back_populates="product_type_attributes")
    attribute: Mapped[Attribute] = relationship()
