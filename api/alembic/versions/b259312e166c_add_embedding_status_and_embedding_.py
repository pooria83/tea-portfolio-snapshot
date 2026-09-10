"""Add embedding_status and embedding_error to store_products

Revision ID: b259312e166c
Revises: 99e1c0dc1708
Create Date: 2026-07-25 20:04:00.798024

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b259312e166c"
down_revision: str | None = "99e1c0dc1708"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("store_products", sa.Column("embedding_status", sa.String(length=20), nullable=True))
    op.add_column("store_products", sa.Column("embedding_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("store_products", "embedding_error")
    op.drop_column("store_products", "embedding_status")
