from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ScraperHeader(Base, TimestampMixin):
    """Per-scraper raw request header block (Cookie + browser headers).

    ``header`` holds the raw multi-line header block as pasted from the
    browser DevTools. NULL means the scraper is not configured yet and must
    exit with an error on startup.
    """

    __tablename__ = "scraper_headers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    header: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready")  # ready | error
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
