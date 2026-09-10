"""add prompt column to ai_description_versions

Revision ID: 99e1c0dc1708
Revises: 792c06cfcca7
Create Date: 2026-07-22 12:44:45.356615

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "99e1c0dc1708"
down_revision: str | None = "792c06cfcca7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_description_versions", sa.Column("prompt", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_description_versions", "prompt")
