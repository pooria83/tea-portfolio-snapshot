"""add llm_settings table

Revision ID: 7f3777bdd0fc
Revises: 7f1486cddfef
Create Date: 2026-07-22 00:42:41.062342

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7f3777bdd0fc"
down_revision: str | None = "7f1486cddfef"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("default_llm_model_id", sa.String(length=36), nullable=True),
        sa.Column("user_comm_model_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["default_llm_model_id"], ["llm_models.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_comm_model_id"], ["llm_models.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("llm_settings")
