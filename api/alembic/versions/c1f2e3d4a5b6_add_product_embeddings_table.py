"""add product_embeddings table

Revision ID: c1f2e3d4a5b6
Revises: a3f9b7c1e2d5
Create Date: 2026-08-11 12:00:00.000000

Backfills per-model embedding status rows from the legacy
store_products.embedding_status/embedding_error columns, then drops them.
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1f2e3d4a5b6"
down_revision: str | None = "a3f9b7c1e2d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"


def _active_model(connection: sa.engine.Connection) -> str:
    row = connection.execute(sa.text("SELECT value FROM system_settings WHERE key = 'embedding_provider' LIMIT 1")).fetchone()
    if not row or not row[0]:
        return DEFAULT_EMBEDDING_MODEL
    try:
        parsed = json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return DEFAULT_EMBEDDING_MODEL
    if isinstance(parsed, dict):
        model = str(parsed.get("model") or "").strip()
        if model:
            return model
    return DEFAULT_EMBEDDING_MODEL


def upgrade() -> None:
    op.create_table(
        "product_embeddings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("model_id", sa.String(length=36), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("embedding_status", sa.String(length=20), nullable=False),
        sa.Column("embedding_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["embed_models.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["store_products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "model_name", name="uq_product_embedding_product_model"),
    )
    op.create_index(op.f("ix_product_embeddings_product_id"), "product_embeddings", ["product_id"], unique=False)
    op.create_index(
        "ix_product_embeddings_model_name_status",
        "product_embeddings",
        ["model_name", "embedding_status"],
        unique=False,
    )

    connection = op.get_bind()
    model = _active_model(connection)

    connection.execute(
        sa.text(
            """
            INSERT INTO product_embeddings (id, product_id, model_id, model_name, embedding_status, embedding_error)
            SELECT md5(p.id || ':' || :model),
                   p.id,
                   em.id,
                   :model,
                   COALESCE(p.embedding_status, 'pending'),
                   p.embedding_error
            FROM store_products p
            LEFT JOIN embed_models em ON em.model_name = :model
            """
        ),
        {"model": model},
    )

    op.drop_column("store_products", "embedding_error")
    op.drop_column("store_products", "embedding_status")


def downgrade() -> None:
    op.add_column("store_products", sa.Column("embedding_status", sa.String(length=20), nullable=True))
    op.add_column("store_products", sa.Column("embedding_error", sa.Text(), nullable=True))
    op.drop_index("ix_product_embeddings_model_name_status", table_name="product_embeddings")
    op.drop_index(op.f("ix_product_embeddings_product_id"), table_name="product_embeddings")
    op.drop_table("product_embeddings")
