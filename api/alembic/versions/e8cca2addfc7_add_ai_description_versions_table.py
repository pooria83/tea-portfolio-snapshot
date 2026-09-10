"""add ai_description_versions table

Revision ID: e8cca2addfc7
Revises: 80b1fb555a0b
Create Date: 2026-07-21 10:52:46.749023

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e8cca2addfc7"
down_revision: str | None = "80b1fb555a0b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_description_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("description_en", sa.Text(), nullable=True),
        sa.Column("description_ar", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default="now()", nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["store_products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_description_versions_product_id"), "ai_description_versions", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_description_versions_product_id"), table_name="ai_description_versions")
    op.drop_table("ai_description_versions")
