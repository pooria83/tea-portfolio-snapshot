"""add api_product_id column to scrape_products

Revision ID: 21aafc22dcd3
Revises: 21aafc22dcd2
Create Date: 2026-07-15 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "21aafc22dcd3"
down_revision: tuple[str, str] = ("21aafc22dcd2", "a1e7d878bdb8")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("scrape_products", sa.Column("api_product_id", sa.String(length=36), nullable=True))


def downgrade() -> None:
    op.drop_column("scrape_products", "api_product_id")
