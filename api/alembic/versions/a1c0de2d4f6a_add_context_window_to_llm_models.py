"""add context_window to llm_models

Revision ID: a1c0de2d4f6a
Revises: 569ab8dcb5ee
Create Date: 2026-08-04 17:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1c0de2d4f6a"
down_revision: str | None = "569ab8dcb5ee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("llm_models", sa.Column("context_window", sa.Integer(), nullable=True))
    op.execute("UPDATE llm_models SET context_window = 8192 WHERE context_window IS NULL")


def downgrade() -> None:
    op.drop_column("llm_models", "context_window")
