"""Backfill product images for all variants sharing the same color.

For each product, images linked to a specific variant (color + size) are
duplicated for all other variants of the same color, so that every color
variant has its own set of images.
"""

import asyncio
import sys
import uuid

import asyncpg
from loguru import logger

logger.add(sys.stderr, level="INFO")

PRIMARY_COLOR_CODE = "primary_color"


async def main():
    conn = await asyncpg.connect("postgresql://<REDACTED>@localhost/portfolio")

    # Preload attribute code -> id
    attr_rows = await conn.fetch("SELECT id, code FROM attributes")
    attr_map = {a["code"]: a["id"] for a in attr_rows}
    color_attr_id = attr_map.get(PRIMARY_COLOR_CODE)

    if not color_attr_id:
        logger.error("Primary color attribute not found")
        return

    # Get all store_products with multiple variants that have color options
    products = await conn.fetch(
        """
        SELECT DISTINCT sp.id, sp.sku, sp.name_en
        FROM store_products sp
        JOIN product_variants pv ON pv.product_id = sp.id
        JOIN variant_attribute_options vao ON vao.variant_id = pv.id
        JOIN attribute_options ao ON ao.id = vao.attribute_option_id
        WHERE ao.attribute_id = $1
        AND sp.id IN (
            SELECT product_id FROM product_variants
            GROUP BY product_id
            HAVING COUNT(*) > 1
        )
        ORDER BY sp.sku
    """,
        color_attr_id,
    )

    stats = {"processed": 0, "images_added": 0, "errors": 0, "skipped": 0}

    for p in products:
        try:
            pid = p["id"]

            # Get all variants with their color option IDs
            variants = await conn.fetch(
                """
                SELECT pv.id, pv.sku, array_agg(vao.attribute_option_id) as attr_opt_ids
                FROM product_variants pv
                LEFT JOIN variant_attribute_options vao ON vao.variant_id = pv.id
                WHERE pv.product_id = $1
                GROUP BY pv.id, pv.sku
                ORDER BY pv.sku
            """,
                pid,
            )

            # Group variants by color option ID
            color_to_variants: dict[str, list[dict]] = {}
            for v in variants:
                opt_ids = [o for o in v["attr_opt_ids"] if o]
                # Find the color option(s) for this variant
                color_opts = []
                if opt_ids:
                    color_opts = await conn.fetch(
                        """
                        SELECT id FROM attribute_options
                        WHERE id = ANY($1::text[]) AND attribute_id = $2
                    """,
                        opt_ids,
                        color_attr_id,
                    )
                for co in color_opts:
                    co_id = co["id"]
                    if co_id not in color_to_variants:
                        color_to_variants[co_id] = []
                    color_to_variants[co_id].append(v)

            # Get all images for this product, grouped by color option
            all_images = await conn.fetch(
                """
                SELECT pi.id, pi.image_url, pi.sort_order, pi.view_type_id,
                       pi.alt_text_ar, pi.alt_text_en, pi.alt_text_fa,
                       pi.variant_id, pi.is_video
                FROM product_images pi
                WHERE pi.product_id = $1
                ORDER BY pi.sort_order
            """,
                pid,
            )

            # For each image linked to a variant, check which color it belongs to
            # and duplicate for all other variants of that color
            for img in all_images:
                if not img["variant_id"]:
                    continue  # general image, skip

                # Find what color option this variant has
                img_variant = next((v for v in variants if v["id"] == img["variant_id"]), None)
                if not img_variant:
                    continue

                img_variant_opt_ids = [o for o in img_variant["attr_opt_ids"] if o]
                if not img_variant_opt_ids:
                    continue

                img_color_opts = await conn.fetch(
                    """
                    SELECT id FROM attribute_options
                    WHERE id = ANY($1::text[]) AND attribute_id = $2
                """,
                    img_variant_opt_ids,
                    color_attr_id,
                )

                for co in img_color_opts:
                    co_id = co["id"]
                    same_color_variants = color_to_variants.get(co_id, [])
                    for target_v in same_color_variants:
                        if target_v["id"] == img["variant_id"]:
                            continue  # same variant, skip

                        # Check if this target variant already has an image at this sort_order
                        existing = await conn.fetchrow(
                            """
                            SELECT 1 FROM product_images
                            WHERE product_id = $1 AND variant_id = $2 AND sort_order = $3
                        """,
                            pid,
                            target_v["id"],
                            img["sort_order"],
                        )

                        if existing:
                            continue  # already has an image at this position

                        await conn.execute(
                            """
                            INSERT INTO product_images
                                (id, product_id, variant_id, view_type_id, image_url,
                                 alt_text_ar, alt_text_en, alt_text_fa, sort_order,
                                 is_video)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        """,
                            str(uuid.uuid4()),
                            pid,
                            target_v["id"],
                            img["view_type_id"],
                            img["image_url"],
                            img["alt_text_ar"],
                            img["alt_text_en"],
                            img["alt_text_fa"],
                            img["sort_order"],
                            img["is_video"],
                        )
                        stats["images_added"] += 1

            stats["processed"] += 1
            if stats["processed"] % 20 == 0:
                logger.info("Progress: {}/{} products, {} images added", stats["processed"], len(products), stats["images_added"])

        except Exception as e:
            logger.error("Error processing {} ({}): {}", p["sku"], p["id"], e)
            stats["errors"] += 1

    await conn.close()

    print("\nBackfill complete:")
    print(f"  Processed: {stats['processed']}")
    print(f"  Images added: {stats['images_added']}")
    print(f"  Errors: {stats['errors']}")


if __name__ == "__main__":
    asyncio.run(main())
