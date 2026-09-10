from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ProductEmbedding(Base, TimestampMixin):
    """Per-model embedding status for a product.

    Each row tracks the embedding lifecycle (pending/generating/done/error)
    of one product under one embedding model. ``model_name`` is a snapshot so
    rows stay meaningful even if the ``embed_models`` row is removed.
    """

    __tablename__ = "product_embeddings"
    __table_args__ = (UniqueConstraint("product_id", "model_name", name="uq_product_embedding_product_model"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("store_products.id", ondelete="CASCADE"), nullable=False)
    model_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("embed_models.id", ondelete="SET NULL"), nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    embedding_error: Mapped[str | None] = mapped_column(Text, nullable=True)
