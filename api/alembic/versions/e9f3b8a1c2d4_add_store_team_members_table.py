"""add store_team_members table

Revision ID: e9f3b8a1c2d4
Revises: b259312e166c
Create Date: 2026-07-29 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e9f3b8a1c2d4"
down_revision: str | None = "b259312e166c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_team_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("store_id", sa.String(36), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Enum("owner", "manager", name="store_member_role"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("store_id", "user_id", name="uq_store_team_members_store_user"),
    )

    op.execute(
        """INSERT INTO store_team_members (id, store_id, user_id, role)
           SELECT gen_random_uuid()::text, id, owner_id, 'owner'
           FROM stores
           WHERE is_active = true"""
    )


def downgrade() -> None:
    op.execute("DROP TYPE IF EXISTS store_member_role")
    op.drop_table("store_team_members")
