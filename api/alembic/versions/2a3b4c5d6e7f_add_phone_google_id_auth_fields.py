"""Add phone, google_id, make email/username/password nullable

Revision ID: 2a3b4c5d6e7f
Revises: 915b50f5b03b
Create Date: 2026-07-08 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "2a3b4c5d6e7f"
down_revision: str | None = "915b50f5b03b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("google_id", sa.String(length=255), nullable=True))
    op.alter_column("users", "email", nullable=True)
    op.alter_column("users", "username", nullable=True)
    op.alter_column("users", "hashed_password", nullable=True)
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)
    op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_google_id", table_name="users")
    op.drop_index("ix_users_phone", table_name="users")
    op.alter_column("users", "hashed_password", nullable=False)
    op.alter_column("users", "username", nullable=False)
    op.alter_column("users", "email", nullable=False)
    op.drop_column("users", "google_id")
    op.drop_column("users", "phone")
