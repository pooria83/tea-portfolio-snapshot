"""Fix attribute group_id conflicts caused by shared attribute codes.

Attributes like `closure_type` were defined in multiple seed files with
different `group_code` values (e.g., shoe-details, dress-specs). The seed
script's dedup by code meant the first file's group was used for all
product types, causing wrong group names to appear.

This migration:
- Updates group_id for codes that changed first-owner
  (closure_type: bag-style→dress-specs, heel_height: shoe-details→heels-dress-specs,
   fragrance_family: beauty-details→fragrance-specs)
- Deletes attribute rows for codes that were fully renamed
  (toe_style, volume_ml, weight_g), including their links and option rows

Revision ID: 9d40219c5ac1
Revises: 9d40219c5ac0
Create Date: 2026-07-16 06:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9d40219c5ac1"
down_revision: str | None = "9a37978dba36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # ---- Step 1: Fix group_id for codes that changed ownership ----
    # closure_type: original owner was 08_bags (bag-style), new owner is 24_dresses (dress-specs)
    conn.execute(
        sa.text("""
            UPDATE attributes
            SET group_id = (SELECT id FROM attribute_groups WHERE code = 'dress-specs')
            WHERE code = 'closure_type'
        """)
    )
    print("  Updated closure_type group_id → dress-specs")

    # heel_height: original owner was 16_boots (shoe-details), new owner is 17_heels (heels-dress-specs)
    conn.execute(
        sa.text("""
            UPDATE attributes
            SET group_id = (SELECT id FROM attribute_groups WHERE code = 'heels-dress-specs')
            WHERE code = 'heel_height'
        """)
    )
    print("  Updated heel_height group_id → heels-dress-specs")

    # fragrance_family: original owner was 09_beauty (beauty-details), new owner is 33_fragrance (fragrance-specs)
    conn.execute(
        sa.text("""
            UPDATE attributes
            SET group_id = (SELECT id FROM attribute_groups WHERE code = 'fragrance-specs')
            WHERE code = 'fragrance_family'
        """)
    )
    print("  Updated fragrance_family group_id → fragrance-specs")

    # ---- Step 2: Delete fully renamed attribute codes ----
    # These codes no longer exist in any seed file. Old rows must be removed
    # so the seed script can create the new uniquely-named attributes.
    for code in ("toe_style", "volume_ml", "weight_g"):
        rows = conn.execute(
            sa.text("SELECT id FROM attributes WHERE code = :code"),
            {"code": code},
        ).fetchall()
        for (attr_id,) in rows:
            # Delete product attribute values (if any exist)
            conn.execute(
                sa.text("DELETE FROM product_attribute_values WHERE attribute_id = :id"),
                {"id": attr_id},
            )
            # Delete product type attribute links
            conn.execute(
                sa.text("DELETE FROM product_type_attributes WHERE attribute_id = :id"),
                {"id": attr_id},
            )
            # Delete attribute options
            conn.execute(
                sa.text("DELETE FROM attribute_options WHERE attribute_id = :id"),
                {"id": attr_id},
            )
            # Delete the attribute itself
            conn.execute(
                sa.text("DELETE FROM attributes WHERE id = :id"),
                {"id": attr_id},
            )
            print(f"  Deleted attribute '{code}' (id={attr_id}) and all links")


def downgrade() -> None:
    # No downgrade — reverting would put wrong group_ids back
    pass
