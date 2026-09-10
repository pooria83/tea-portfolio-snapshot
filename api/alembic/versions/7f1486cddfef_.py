"""

Revision ID: 7f1486cddfef
Revises: d725b2de756b
Create Date: 2026-07-21 23:46:25.318358

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7f1486cddfef"
down_revision: str | None = "d725b2de756b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("llm_api_keys", sa.Column("name", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_api_keys", "name")
