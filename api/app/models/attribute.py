from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.attribute_group import AttributeGroup
    from app.models.attribute_option import AttributeOption


class Attribute(Base, TimestampMixin):
    __tablename__ = "attributes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("attribute_groups.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(255), nullable=False)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False)
    input_type: Mapped[str] = mapped_column(String(30), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_rules: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    is_filterable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_searchable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_search_affecting: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    is_visible_on_show: Mapped[bool] = mapped_column(Boolean, default=True)
    is_variant_defining: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    group: Mapped[AttributeGroup] = relationship()
    options: Mapped[list[AttributeOption]] = relationship(back_populates="attribute", cascade="all, delete-orphan")
