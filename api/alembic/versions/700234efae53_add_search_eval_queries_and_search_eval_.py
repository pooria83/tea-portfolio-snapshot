"""add search_eval_queries and search_eval_judgments tables

Revision ID: 700234efae53
Revises: a7f3e1d9c2b4
Create Date: 2026-08-15 20:00:34.780873

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "700234efae53"
down_revision: str | None = "a7f3e1d9c2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_eval_queries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("locale", sa.String(length=5), nullable=False),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("rewritten_query", sa.Text(), nullable=True),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("text", "locale", name="uq_search_eval_query_text_locale"),
    )
    op.create_index(op.f("ix_search_eval_queries_locale"), "search_eval_queries", ["locale"], unique=False)
    op.create_index(op.f("ix_search_eval_queries_source"), "search_eval_queries", ["source"], unique=False)
    op.create_index(op.f("ix_search_eval_queries_status"), "search_eval_queries", ["status"], unique=False)
    op.create_table(
        "search_eval_judgments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("query_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("relevant", sa.Boolean(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["query_id"], ["search_eval_queries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("query_id", "product_id", name="uq_search_eval_judgment_query_product"),
    )
    op.create_index(op.f("ix_search_eval_judgments_query_id"), "search_eval_judgments", ["query_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_search_eval_judgments_query_id"), table_name="search_eval_judgments")
    op.drop_table("search_eval_judgments")
    op.drop_index(op.f("ix_search_eval_queries_status"), table_name="search_eval_queries")
    op.drop_index(op.f("ix_search_eval_queries_source"), table_name="search_eval_queries")
    op.drop_index(op.f("ix_search_eval_queries_locale"), table_name="search_eval_queries")
    op.drop_table("search_eval_queries")
