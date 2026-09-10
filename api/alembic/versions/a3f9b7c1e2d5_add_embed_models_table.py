"""add embed_models table

Revision ID: a3f9b7c1e2d5
Revises: d996c5e6f593
Create Date: 2026-08-11 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a3f9b7c1e2d5"
down_revision: str | None = "d996c5e6f593"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBED_MODELS: list[tuple[str, str]] = [
    ("Qwen3-Embedding-0.6B", "Qwen3 Embedding 0.6B"),
    ("Qwen3-Embedding-4B", "Qwen3 Embedding 4B"),
    ("Qwen3-Embedding-8B", "Qwen3 Embedding 8B"),
    ("F2LLM-v2-4B", "F2LLM v2 4B"),
    ("jina-embeddings-v5-text-small", "Jina v5 text-small"),
    ("BGE-M3", "BGE-M3"),
    ("Nomic Embed v2", "Nomic Embed v2"),
    ("multilingual-e5-large-instruct", "multilingual-e5-large-instruct"),
    ("multilingual-e5-base", "multilingual-e5-base"),
]


def upgrade() -> None:
    embed_models = op.create_table(
        "embed_models",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=150), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for i, (model_name, display_name) in enumerate(EMBED_MODELS):
        op.bulk_insert(
            embed_models,
            [
                {
                    "id": f"seed-embed-model-{i + 1}",
                    "model_name": model_name,
                    "display_name": display_name,
                    "is_active": True,
                }
            ],
        )


def downgrade() -> None:
    op.drop_table("embed_models")
