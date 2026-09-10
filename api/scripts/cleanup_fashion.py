#!/usr/bin/env python3
"""Clean up old fashion product type — migrate categories, remove orphaned type."""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

NAME_TO_CODE = {
    "Dresses": "dresses",
    "Tops & Blouses": "tops",
    "Skirts & Pants": "bottoms",
    "Outerwear": "outerwear",
    "Activewear": "activewear",
    "Swimwear": "swimwear",
    "Lingerie & Sleepwear": "lingerie_sleepwear",
    "Abayas": "abayas",
    "Scarves & Hijabs": "scarves_hijabs",
}


async def cleanup():
    engine = create_async_engine(settings.database_url, echo=False)

    # Transaction 1: Migrate categories
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT id, code FROM product_types"))
        pt_map: dict[str, str] = {row[1]: row[0] for row in result.fetchall()}

        old_fashion_id = pt_map.get("fashion")
        if not old_fashion_id:
            print("Old fashion product type not found — nothing to do.")
            await engine.dispose()
            return

        for name, code in NAME_TO_CODE.items():
            await conn.execute(
                text("UPDATE categories SET product_type_id = :new_pt_id WHERE product_type_id = :old_pt_id AND name_en = :name"),
                {
                    "new_pt_id": pt_map[code],
                    "old_pt_id": old_fashion_id,
                    "name": name,
                },
            )

        result = await conn.execute(
            text(
                "UPDATE categories c "
                "SET product_type_id = p.product_type_id "
                "FROM categories p "
                "WHERE c.parent_id = p.id "
                "AND c.product_type_id = :old_fashion_id "
                "AND p.product_type_id != :old_fashion_id"
            ),
            {"old_fashion_id": old_fashion_id},
        )
        print(f"Updated {result.rowcount} child categories")

        remaining = await conn.execute(
            text("SELECT COUNT(*) FROM categories WHERE product_type_id = :id"),
            {"id": old_fashion_id},
        )
        print(f"Categories still on old fashion: {remaining.scalar()}")

    print("Transaction 1 committed (category migration)")

    # Transaction 2: Remove fashion product type (no categories remain)
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT id FROM product_types WHERE code = :code"),
            {"code": "fashion"},
        )
        row = result.fetchone()
        if not row:
            print("Old fashion already removed.")
            await engine.dispose()
            return
        old_fashion_id = row[0]

        # Nullify FK references from product_images
        await conn.execute(
            text("UPDATE product_images SET view_type_id = NULL WHERE view_type_id IN (SELECT id FROM product_type_image_view_types WHERE product_type_id = :id)"),
            {"id": old_fashion_id},
        )

        await conn.execute(
            text("DELETE FROM product_type_attributes WHERE product_type_id = :id"),
            {"id": old_fashion_id},
        )

        await conn.execute(
            text("DELETE FROM product_type_image_view_types WHERE product_type_id = :id"),
            {"id": old_fashion_id},
        )

        await conn.execute(
            text("DELETE FROM product_types WHERE id = :id"),
            {"id": old_fashion_id},
        )
        print("Deleted old fashion product type")

    # Verify
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM product_types"))
        print(f"Product types remaining: {result.scalar()}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(cleanup())
