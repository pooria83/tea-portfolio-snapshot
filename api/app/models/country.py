from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Country(Base, TimestampMixin):
    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(5), primary_key=True)
    name_ar: Mapped[str] = mapped_column(Text, nullable=False)
    name_en: Mapped[str] = mapped_column(Text, nullable=False)
    name_fa: Mapped[str] = mapped_column(Text, nullable=False)
