"""add countries, currencies tables and store country/price_unit columns

Revision ID: aafe2d25aa13
Revises: 491b63edcb63
Create Date: 2026-07-14 07:35:26.830215

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "aafe2d25aa13"
down_revision: str | None = "491b63edcb63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "countries",
        sa.Column("code", sa.String(length=5), nullable=False),
        sa.Column("name_ar", sa.Text(), nullable=False),
        sa.Column("name_en", sa.Text(), nullable=False),
        sa.Column("name_fa", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "currencies",
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("name_ar", sa.Text(), nullable=False),
        sa.Column("name_en", sa.Text(), nullable=False),
        sa.Column("name_fa", sa.Text(), nullable=False),
        sa.Column("symbol", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )

    op.execute("""
        INSERT INTO countries (code, name_ar, name_en, name_fa) VALUES
        ('SA', 'المملكة العربية السعودية', 'Saudi Arabia', 'عربستان سعودی'),
        ('AE', 'الإمارات العربية المتحدة', 'United Arab Emirates', 'امارات متحده عربی'),
        ('KW', 'الكويت', 'Kuwait', 'کویت')
    """)

    op.execute("""
        INSERT INTO currencies (code, name_ar, name_en, name_fa, symbol) VALUES
        ('SAR', 'ريال سعودي', 'Saudi Riyal', 'ریال سعودی', '﷼'),
        ('AED', 'درهم إماراتي', 'UAE Dirham', 'درهم امارات', 'د.إ'),
        ('KWD', 'دينار كويتي', 'Kuwaiti Dinar', 'دینار کویت', 'د.ك')
    """)

    op.add_column("stores", sa.Column("country_code", sa.String(length=5), nullable=True))
    op.add_column("stores", sa.Column("price_unit_code", sa.String(length=10), nullable=True))

    op.execute("UPDATE stores SET country_code = 'KW', price_unit_code = 'KWD'")

    op.alter_column("stores", "country_code", nullable=False)
    op.alter_column("stores", "price_unit_code", nullable=False)

    op.create_foreign_key(None, "stores", "countries", ["country_code"], ["code"])
    op.create_foreign_key(None, "stores", "currencies", ["price_unit_code"], ["code"])


def downgrade() -> None:
    op.drop_constraint(None, "stores", type_="foreignkey")
    op.drop_constraint(None, "stores", type_="foreignkey")
    op.drop_column("stores", "price_unit_code")
    op.drop_column("stores", "country_code")
    op.drop_table("currencies")
    op.drop_table("countries")
