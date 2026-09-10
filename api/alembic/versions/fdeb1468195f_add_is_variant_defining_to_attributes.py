"""add is_variant_defining to attributes

Revision ID: fdeb1468195f
Revises: 21aafc22dcd2
Create Date: 2026-07-12 22:52:25.833955

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "fdeb1468195f"
down_revision: str | None = "21aafc22dcd2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("attributes", sa.Column("is_variant_defining", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    op.execute("UPDATE attributes SET is_variant_defining = false WHERE is_variant_defining IS NULL")
    op.alter_column("attributes", "is_variant_defining", nullable=False, server_default=None)


def downgrade() -> None:
    op.drop_column("attributes", "is_variant_defining")
