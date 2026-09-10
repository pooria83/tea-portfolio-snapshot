"""Backfill variant attribute options for existing products.

Finds all store_products with variants missing size attribute options
and links them based on the product type and size values from JSON-LD.
"""

import asyncio
import json
import os
import sys

import asyncpg
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from scripts.scrapers.mapper import resolve_category

logger.add(sys.stderr, level="INFO")

VARIANT_SIZE_ATTR_MAP: dict[str, str] = {
    "heels_dress_shoes": "shoe_size",
    "sandals_slippers": "shoe_size",
    "athletic_sneakers": "shoe_size",
    "boots": "shoe_size",
}


def normalize_variant_size(size: str, attr_code: str) -> str:
    if attr_code == "shoe_size":
        return f"eu_{size}"
    return size.lower().replace(" ", "_")


async def main():
    conn = await asyncpg.connect("postgresql://<REDACTED>@localhost/portfolio")

    # Preload attribute map: code -> id
    attrs = await conn.fetch("SELECT id, code FROM attributes")
    attribute_map: dict[str, str] = {a["code"]: a["id"] for a in attrs}

    # Preload option map: (attr_id, code) -> option_id
    opts = await conn.fetch("SELECT id, attribute_id, code FROM attribute_options")
    option_map: dict[tuple[str, str], str] = {}
    for o in opts:
        option_map[(o["attribute_id"], o["code"])] = o["id"]

    # Get all store_products with variants
    products = await conn.fetch("""
        SELECT sp.id as store_id, sp.sku, sp.name_en,
               sc.source_id, sc.source_category,
               sc.raw_data::text as raw
        FROM store_products sp
        JOIN scrape_products sc ON sc.source_id = REPLACE(sp.sku, 'ZARA-', '')
        WHERE EXISTS (
            SELECT 1 FROM product_variants pv WHERE pv.product_id = sp.id
        )
        ORDER BY sp.created_at
    """)

    stats = {"processed": 0, "linked": 0, "errors": 0, "skipped_no_size": 0}

    for p in products:
        try:
            raw = json.loads(p["raw"])
            en_json_ld = raw.get("en", {}).get("json_ld", {})
            variants_jld = en_json_ld.get("hasVariant", [])
            if isinstance(variants_jld, dict):
                variants_jld = [variants_jld]
            if not variants_jld:
                stats["skipped_no_size"] += 1
                continue

            # Resolve product type
            source_category = p.get("source_category") or ""
            _, _, pt_code = resolve_category(source_category, p["name_en"])

            size_attr_code = VARIANT_SIZE_ATTR_MAP.get(pt_code or "", "size")
            size_attr_id = attribute_map.get(size_attr_code)

            if not size_attr_id:
                logger.warning("No attribute ID for code={} (pt={}, product={})", size_attr_code, pt_code, p["sku"])
                stats["errors"] += 1
                continue

            # Get all DB variants for this product
            db_variants = await conn.fetch(
                "SELECT id, sku FROM product_variants WHERE product_id = $1",
                p["store_id"],
            )
            sku_to_db_id = {v["sku"]: v["id"] for v in db_variants}

            product_linked = 0
            for v in variants_jld:
                sku = str(v.get("sku", ""))
                size = v.get("size", "")
                if not sku or not size:
                    continue

                db_id = sku_to_db_id.get(sku)
                if not db_id:
                    continue

                size_code = normalize_variant_size(size, size_attr_code)
                opt_id = option_map.get((size_attr_id, size_code))
                if not opt_id:
                    continue

                exists = await conn.fetchrow(
                    "SELECT 1 FROM variant_attribute_options WHERE variant_id = $1 AND attribute_option_id = $2",
                    db_id,
                    opt_id,
                )
                if not exists:
                    await conn.execute(
                        "INSERT INTO variant_attribute_options (variant_id, attribute_option_id) VALUES ($1, $2)",
                        db_id,
                        opt_id,
                    )
                    product_linked += 1
                    stats["linked"] += 1

            stats["processed"] += 1
            if product_linked > 0:
                logger.info("{}: linked {} size options (pt={}, attr={})", p["sku"], product_linked, pt_code, size_attr_code)

        except Exception as e:
            logger.error("Error processing {}: {}", p["sku"], e)
            stats["errors"] += 1

    await conn.close()

    print("\nBackfill complete:")
    print(f"  Processed: {stats['processed']}")
    print(f"  Linked:    {stats['linked']}")
    print(f"  Errors:    {stats['errors']}")
    print(f"  Skipped:   {stats['skipped_no_size']}")


if __name__ == "__main__":
    asyncio.run(main())
