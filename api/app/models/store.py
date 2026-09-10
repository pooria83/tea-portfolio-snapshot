from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.country import Country
    from app.models.currency import Currency
    from app.models.store_member import StoreMember
    from app.models.store_type import StoreType
    from app.models.user import User
    from app.models.working_hour import WorkingHour


class Store(Base, TimestampMixin):
    __tablename__ = "stores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[str] = mapped_column(String(36), ForeignKey("categories.id"), nullable=False)
    store_type_id: Mapped[str] = mapped_column(String(36), ForeignKey("store_types.id"), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    location_lat: Mapped[float] = mapped_column(Float, nullable=False)
    location_lng: Mapped[float] = mapped_column(Float, nullable=False)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    instagram: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    country_code: Mapped[str] = mapped_column(String(5), ForeignKey("countries.code"), nullable=False)
    price_unit_code: Mapped[str] = mapped_column(String(10), ForeignKey("currencies.code"), nullable=False)

    owner: Mapped[User] = relationship(back_populates="stores")
    category: Mapped[Category] = relationship()
    store_type: Mapped[StoreType] = relationship()
    country: Mapped[Country] = relationship()
    price_unit: Mapped[Currency] = relationship()
    working_hours: Mapped[list[WorkingHour]] = relationship(back_populates="store", cascade="all, delete-orphan")
    members: Mapped[list[StoreMember]] = relationship(back_populates="store", cascade="all, delete-orphan")
