from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SearchEvalQuery(Base, TimestampMixin):
    """A search-quality evaluation query (admin golden set)."""

    __tablename__ = "search_eval_queries"
    __table_args__ = (UniqueConstraint("text", "locale", name="uq_search_eval_query_text_locale"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    locale: Mapped[str] = mapped_column(String(5), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="manual", index=True)  # manual | llm | seed
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending", index=True)  # pending | evaluated | skipped
    rewritten_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    filters: Mapped[dict[str, list[str]] | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)


class SearchEvalJudgment(Base):
    """Relevance judgment for one product against one eval query."""

    __tablename__ = "search_eval_judgments"
    __table_args__ = (UniqueConstraint("query_id", "product_id", name="uq_search_eval_judgment_query_product"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    query_id: Mapped[str] = mapped_column(String(36), ForeignKey("search_eval_queries.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    relevant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
