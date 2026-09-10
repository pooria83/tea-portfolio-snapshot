"""enable pg_trgm extension and add GIN indexes for name search

Revision ID: 80b1fb555a0b
Revises: 80b1fb555a0c
Create Date: 2026-07-21 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "80b1fb555a0b"
down_revision: str | None = "80b1fb555a0c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index("idx_store_products_name_en_trgm", "store_products", ["name_en"], postgresql_using="gin", postgresql_ops={"name_en": "gin_trgm_ops"})
    op.create_index("idx_store_products_name_ar_trgm", "store_products", ["name_ar"], postgresql_using="gin", postgresql_ops={"name_ar": "gin_trgm_ops"})


def downgrade() -> None:
    op.drop_index("idx_store_products_name_en_trgm")
    op.drop_index("idx_store_products_name_ar_trgm")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
