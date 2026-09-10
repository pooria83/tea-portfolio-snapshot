"""add_activity_logs_table

Revision ID: 569ab8dcb5ee
Revises: e9f3b8a1c2d4
Create Date: 2026-07-30 13:23:49.202076

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "569ab8dcb5ee"
down_revision: str | None = "e9f3b8a1c2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=True),
        sa.Column("resource_id", sa.String(length=36), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("translation_key", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("request_body", sa.Text(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("path", sa.String(length=500), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_activity_logs_actor", "activity_logs", ["actor_type", "actor_id"], unique=False)
    op.create_index("idx_activity_logs_created_at", "activity_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_activity_logs_created_at", table_name="activity_logs")
    op.drop_index("idx_activity_logs_actor", table_name="activity_logs")
    op.drop_table("activity_logs")
