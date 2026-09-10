import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ScrapeProduct(Base, TimestampMixin):
    __tablename__ = "scrape_products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_category: Mapped[str | None] = mapped_column(String(500), nullable=True)
    country: Mapped[str] = mapped_column(String(5), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    raw_data: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    api_product_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    scrape_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    images_cached: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("source", "source_id", "country", name="uq_scrape_product_source"),)
