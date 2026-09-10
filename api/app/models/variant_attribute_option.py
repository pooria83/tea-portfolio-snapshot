from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class VariantAttributeOption(Base):
    __tablename__ = "variant_attribute_options"

    variant_id: Mapped[str] = mapped_column(String(36), ForeignKey("product_variants.id", ondelete="CASCADE"), primary_key=True)
    attribute_option_id: Mapped[str] = mapped_column(String(36), ForeignKey("attribute_options.id", ondelete="CASCADE"), primary_key=True)
