#!/usr/bin/env python3
"""Seed the database with product definition data: types, categories, attribute groups, attributes, options, image view types."""

import asyncio
import json
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from scripts.seed_cache_invalidation import invalidate_seed_cache

SEED_DIR = Path(__file__).parent / "seed_data"

# Product type attribute files: (filename, product_type_code)
PER_TYPE_ATTR_FILES = [
    ("05_attributes_fashion.json", "dresses"),
    ("08_attributes_bags.json", "bags"),
    ("09_attributes_beauty.json", "beauty"),
    ("19_attributes_necklaces_pendants.json", "necklaces_pendants"),
    ("20_attributes_bracelets_anklets.json", "bracelets_anklets"),
    ("21_attributes_earrings.json", "earrings"),
    ("22_attributes_rings.json", "rings"),
    ("23_attributes_other_jewelry.json", "other_jewelry"),
    ("15_attributes_athletic_sneakers.json", "athletic_sneakers"),
    ("16_attributes_boots.json", "boots"),
    ("17_attributes_heels_dress_shoes.json", "heels_dress_shoes"),
    ("18_attributes_sandals_slippers.json", "sandals_slippers"),
    ("11_attributes_belts_leather_goods.json", "belts_leather_goods"),
    ("12_attributes_head_accessories.json", "head_accessories"),
    ("13_attributes_textile_accessories.json", "textile_accessories"),
    ("14_attributes_specialty_accessories.json", "specialty_accessories"),
    ("24_attributes_dresses.json", "dresses"),
    ("25_attributes_tops.json", "tops"),
    ("26_attributes_bottoms.json", "bottoms"),
    ("27_attributes_outerwear.json", "outerwear"),
    ("28_attributes_activewear.json", "activewear"),
    ("29_attributes_swimwear.json", "swimwear"),
    ("30_attributes_lingerie_sleepwear.json", "lingerie_sleepwear"),
    ("31_attributes_abayas.json", "abayas"),
    ("32_attributes_scarves_hijabs.json", "scarves_hijabs"),
    ("33_attributes_fragrance.json", "fragrance"),
    ("34_attributes_watches.json", "watches"),
    ("35_attributes_eyewear.json", "eyewear"),
    ("36_attributes_skirts.json", "skirts"),
    ("37_attributes_suits_formalwear.json", "suits_formalwear"),
    ("38_attributes_body_care.json", "body_care"),
]

# Shared fashion attributes that should be linked to all fashion product types
SHARED_FASHION_ATTR_CODES = [
    "primary_color",
    "pattern",
    "size",
    "main_material",
    "fabric_composition",
    "care_instructions",
    "style",
    "occasion",
    "season",
    "modesty_level",
    "target_customer",
    "features",
    "fashion_tags",
]

# All fashion product type codes (shared attrs linked to each)
FASHION_PT_CODES = ["dresses", "tops", "bottoms", "outerwear", "activewear", "swimwear", "lingerie_sleepwear", "abayas", "scarves_hijabs", "skirts", "suits_formalwear"]


async def seed() -> None:
    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.begin() as conn:
        product_types = _load_json("01_product_types.json", "product_types")
        if product_types:
            pt_map = await _seed_product_types(conn, product_types)
        else:
            pt_map = {}

        categories = _load_json("03_categories.json", "categories")
        if categories:
            await _seed_categories(conn, categories, pt_map)

        attribute_groups = _load_json("02_attribute_groups.json", "attribute_groups")
        if attribute_groups:
            ag_map = await _seed_attribute_groups(conn, attribute_groups)
        else:
            ag_map = {}

        if ag_map and pt_map:
            await _seed_per_type_attributes(conn, ag_map, pt_map)

        await _apply_search_affecting_flags(conn)

        image_view_types = _load_json("04_image_view_types.json", "image_view_types")
        if image_view_types and pt_map:
            await _seed_image_view_types(conn, image_view_types, pt_map)

        brands = _load_json("05_brands.json", "brands")
        if brands:
            await _seed_brands(conn, brands)

    await engine.dispose()
    await invalidate_seed_cache({"product_types", "categories", "attribute_groups", "attributes", "attribute_options", "product_type_image_view_types", "brands"})
    print("Product definition seed complete.")


def _load_json(filename: str, key: str) -> list[dict]:
    path = SEED_DIR / filename
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    return data.get(key, [])


async def _apply_search_affecting_flags(conn) -> None:
    """Apply is_search_affecting flags from search_affecting_flags.json.

    Idempotent — re-runs safely on fresh and existing databases, keeping the
    attributes table in sync with the canonical mapping used by the embed
    text template and the Alembic migration.
    """
    path = SEED_DIR / "search_affecting_flags.json"
    if not path.exists():
        return
    with open(path) as f:
        flags = json.load(f)
    if not isinstance(flags, dict):
        return

    true_codes = [code for code, flag in flags.items() if flag]
    false_codes = [code for code, flag in flags.items() if not flag]

    if true_codes:
        await conn.execute(
            text("UPDATE attributes SET is_search_affecting = true WHERE code = ANY(:codes)"),
            {"codes": true_codes},
        )
    if false_codes:
        await conn.execute(
            text("UPDATE attributes SET is_search_affecting = false WHERE code = ANY(:codes)"),
            {"codes": false_codes},
        )
    print(f"Applied is_search_affecting flags to {len(flags)} attribute codes.")


async def _seed_product_types(conn, types: list[dict]) -> dict[str, str]:
    """Seed product_types table. Returns map of code -> id. Idempotent."""
    existing = await conn.execute(text("SELECT id, code FROM product_types"))
    pt_map: dict[str, str] = {row[1]: row[0] for row in existing.fetchall()}

    seeded = 0
    for pt in types:
        if pt["code"] in pt_map:
            continue
        pt_id = str(uuid.uuid4())
        pt_map[pt["code"]] = pt_id
        await conn.execute(
            text("INSERT INTO product_types (id, code, name_ar, name_en, name_fa, icon, sort_order) VALUES (:id, :code, :name_ar, :name_en, :name_fa, :icon, :sort_order)"),
            {
                "id": pt_id,
                "code": pt["code"],
                "name_ar": pt["name_ar"],
                "name_en": pt["name_en"],
                "name_fa": pt["name_fa"],
                "icon": pt.get("icon"),
                "sort_order": pt.get("sort_order", 0),
            },
        )
        seeded += 1
    if seeded:
        print(f"Seeded {seeded} missing product types.")
    return pt_map


async def _seed_categories(conn, categories: list[dict], pt_map: dict[str, str]) -> None:
    existing_roots = await conn.execute(text("SELECT id, product_type_id, name_en FROM categories WHERE parent_id IS NULL"))
    existing_by_pt: dict[str, tuple[str, str]] = {row[1]: (row[0], row[2]) for row in existing_roots.fetchall()}

    existing_children = await conn.execute(text("SELECT name_en, parent_id FROM categories WHERE parent_id IS NOT NULL"))
    existing_child_names: dict[str, str] = {row[0]: row[1] for row in existing_children.fetchall()}

    seeded_roots = 0
    seeded_children = 0
    for cat in categories:
        pt_code = cat.get("product_type_code", "")
        pt_id = pt_map.get(pt_code)
        if not pt_id:
            print(f"  Skipping category '{cat.get('name_en')}': product type '{pt_code}' not found")
            continue

        if pt_id in existing_by_pt:
            parent_id, _root_name = existing_by_pt[pt_id]
        else:
            parent_id = str(uuid.uuid4())
            await conn.execute(
                text(
                    "INSERT INTO categories (id, parent_id, product_type_id, name_ar, name_en, name_fa, icon, sort_order, is_active) "
                    "VALUES (:id, NULL, :product_type_id, :name_ar, :name_en, :name_fa, :icon, :sort_order, true)"
                ),
                {
                    "id": parent_id,
                    "product_type_id": pt_id,
                    "name_ar": cat["name_ar"],
                    "name_en": cat["name_en"],
                    "name_fa": cat["name_fa"],
                    "icon": cat.get("icon"),
                    "sort_order": cat.get("sort_order", 0),
                },
            )
            existing_by_pt[pt_id] = (parent_id, cat["name_en"])
            seeded_roots += 1

        for child in cat.get("children", []):
            if child["name_en"] in existing_child_names:
                continue
            child_id = str(uuid.uuid4())
            await conn.execute(
                text(
                    "INSERT INTO categories (id, parent_id, product_type_id, name_ar, name_en, name_fa, icon, sort_order, is_active) "
                    "VALUES (:id, :parent_id, :product_type_id, :name_ar, :name_en, :name_fa, :icon, :sort_order, true)"
                ),
                {
                    "id": child_id,
                    "parent_id": parent_id,
                    "product_type_id": pt_id,
                    "name_ar": child["name_ar"],
                    "name_en": child["name_en"],
                    "name_fa": child["name_fa"],
                    "icon": child.get("icon"),
                    "sort_order": child.get("sort_order", 0),
                },
            )
            existing_child_names[child["name_en"]] = parent_id
            seeded_children += 1

    if seeded_roots or seeded_children:
        print(f"Seeded {seeded_roots} root categories and {seeded_children} children.")


async def _seed_attribute_groups(conn, groups: list[dict]) -> dict[str, str]:
    existing = await conn.execute(text("SELECT id, code FROM attribute_groups"))
    ag_map: dict[str, str] = {row[1]: row[0] for row in existing.fetchall()}

    seeded = 0
    for g in groups:
        if g["code"] in ag_map:
            continue
        g_id = str(uuid.uuid4())
        ag_map[g["code"]] = g_id
        await conn.execute(
            text("INSERT INTO attribute_groups (id, code, name_ar, name_en, name_fa, icon, sort_order) VALUES (:id, :code, :name_ar, :name_en, :name_fa, :icon, :sort_order)"),
            {
                "id": g_id,
                "code": g["code"],
                "name_ar": g["name_ar"],
                "name_en": g["name_en"],
                "name_fa": g["name_fa"],
                "icon": g.get("icon"),
                "sort_order": g.get("sort_order", 0),
            },
        )
        seeded += 1
    if seeded:
        print(f"Seeded {seeded} missing attribute groups.")
    return ag_map


async def _seed_per_type_attributes(conn, ag_map: dict[str, str], pt_map: dict[str, str]) -> None:
    """Seed attributes per product type. Idempotent — skips existing attributes and links."""
    # Load existing attributes by code
    existing_attrs = await conn.execute(text("SELECT id, code, group_id FROM attributes"))
    global_attr_map: dict[str, str] = {row[1]: row[0] for row in existing_attrs.fetchall()}
    # Load existing links to avoid duplicates
    existing_links = await conn.execute(text("SELECT product_type_id, attribute_id FROM product_type_attributes"))
    link_set: set[tuple[str, str]] = {(row[0], row[1]) for row in existing_links.fetchall()}

    total_attrs = 0
    total_opts = 0
    total_links = 0

    for filename, pt_code in PER_TYPE_ATTR_FILES:
        data = _load_json(filename, "attributes")
        if not data:
            continue

        pt_id = pt_map.get(pt_code)
        if not pt_id:
            print(f"  Skipping {filename}: product type '{pt_code}' not found")
            continue

        type_attr_ids: list[str] = []

        for attr in data:
            code = attr["code"]
            group_id = ag_map.get(attr["group_code"])

            if not group_id:
                print(f"  Skipping attribute '{code}': group '{attr['group_code']}' not found")
                continue

            # Create attribute if not yet seen (shared attrs like primary_color use first file that defines them)
            if code not in global_attr_map:
                attr_id = str(uuid.uuid4())
                global_attr_map[code] = attr_id
                await conn.execute(
                    text(
                        "INSERT INTO attributes (id, group_id, code, name_ar, name_en, name_fa, "
                        "description_ar, description_en, description_fa, value_type, input_type, icon, "
                        "is_required, is_filterable, is_searchable, is_visible_on_show, is_variant_defining, sort_order, validation_rules) "
                        "VALUES (:id, :group_id, :code, :name_ar, :name_en, :name_fa, "
                        ":description_ar, :description_en, :description_fa, :value_type, :input_type, :icon, "
                        ":is_required, :is_filterable, :is_searchable, true, :is_variant_defining, :sort_order, :validation_rules)"
                    ),
                    {
                        "id": attr_id,
                        "group_id": group_id,
                        "code": attr["code"],
                        "name_ar": attr["name_ar"],
                        "name_en": attr["name_en"],
                        "name_fa": attr["name_fa"],
                        "description_ar": None,
                        "description_en": None,
                        "description_fa": None,
                        "value_type": attr["value_type"],
                        "input_type": attr["input_type"],
                        "icon": attr.get("icon"),
                        "is_required": attr.get("is_required", False),
                        "is_filterable": attr.get("is_filterable", True),
                        "is_searchable": attr.get("is_searchable", True),
                        "is_variant_defining": attr.get("is_variant_defining", False),
                        "sort_order": attr.get("sort_order", 0),
                        "validation_rules": json.dumps(attr.get("validation_rules")) if attr.get("validation_rules") else None,
                    },
                )

                # Seed options only when attribute is first created
                options = attr.get("options", [])
                for opt in options:
                    opt_id = str(uuid.uuid4())
                    await conn.execute(
                        text(
                            "INSERT INTO attribute_options (id, attribute_id, code, value_ar, value_en, value_fa, icon, color_hex, image_url, color_family, is_major, sort_order) "
                            "VALUES (:id, :attribute_id, :code, :value_ar, :value_en, :value_fa, :icon, :color_hex, :image_url, :color_family, :is_major, :sort_order)"
                        ),
                        {
                            "id": opt_id,
                            "attribute_id": attr_id,
                            "code": opt.get("code"),
                            "value_ar": opt["value_ar"],
                            "value_en": opt["value_en"],
                            "value_fa": opt["value_fa"],
                            "icon": opt.get("icon"),
                            "color_hex": opt.get("color_hex"),
                            "image_url": opt.get("image_url"),
                            "color_family": opt.get("color_family"),
                            "is_major": opt.get("is_major", False),
                            "sort_order": opt.get("sort_order", 0),
                        },
                    )
                    total_opts += 1

                total_attrs += 1
            else:
                # Update validation_rules/input_type for shared attrs redefined in other types
                rules = attr.get("validation_rules")
                await conn.execute(
                    text("UPDATE attributes SET validation_rules = :validation_rules, input_type = :input_type, is_variant_defining = :is_variant_defining WHERE id = :id"),
                    {
                        "id": global_attr_map[code],
                        "validation_rules": json.dumps(rules) if rules else None,
                        "input_type": attr["input_type"],
                        "is_variant_defining": attr.get("is_variant_defining", False),
                    },
                )

            attr_id = global_attr_map[code]
            type_attr_ids.append(attr_id)

        # Link attributes for this product type (skip if already linked)
        for attr_id in type_attr_ids:
            if (pt_id, attr_id) in link_set:
                continue
            await conn.execute(
                text("INSERT INTO product_type_attributes (id, product_type_id, attribute_id, is_required, sort_order) VALUES (:id, :product_type_id, :attribute_id, :is_required, :sort_order)"),
                {
                    "id": str(uuid.uuid4()),
                    "product_type_id": pt_id,
                    "attribute_id": attr_id,
                    "is_required": True,
                    "sort_order": 0,
                },
            )
            link_set.add((pt_id, attr_id))
            total_links += 1

        print(f"  Processed {len(type_attr_ids)} attributes for '{pt_code}' from {filename}")

    # Link shared fashion attributes to all fashion product types
    shared_linked = 0
    for pt_code in FASHION_PT_CODES:
        pt_id = pt_map.get(pt_code)
        if not pt_id:
            continue
        for attr_code in SHARED_FASHION_ATTR_CODES:
            attr_id = global_attr_map.get(attr_code)
            if not attr_id:
                continue
            if (pt_id, attr_id) in link_set:
                continue
            await conn.execute(
                text("INSERT INTO product_type_attributes (id, product_type_id, attribute_id, is_required, sort_order) VALUES (:id, :product_type_id, :attribute_id, :is_required, :sort_order)"),
                {
                    "id": str(uuid.uuid4()),
                    "product_type_id": pt_id,
                    "attribute_id": attr_id,
                    "is_required": True,
                    "sort_order": 0,
                },
            )
            link_set.add((pt_id, attr_id))
            shared_linked += 1
    if shared_linked:
        print(f"  Linked {shared_linked} shared fashion attribute-type relations.")

    print(f"Seeded {total_attrs} new attributes with {total_opts} options, {total_links} new type links.")


async def _seed_image_view_types(conn, view_types: list[dict], pt_map: dict[str, str]) -> None:
    existing = await conn.execute(text("SELECT product_type_id, code FROM product_type_image_view_types"))
    existing_set: set[tuple[str, str]] = {(row[0], row[1]) for row in existing.fetchall()}

    seeded = 0
    for vt in view_types:
        pt_id = pt_map.get(vt["product_type_code"])
        if not pt_id:
            continue
        if (pt_id, vt["code"]) in existing_set:
            continue
        await conn.execute(
            text(
                "INSERT INTO product_type_image_view_types (id, product_type_id, code, name_ar, name_en, name_fa, is_video, sort_order) "
                "VALUES (:id, :product_type_id, :code, :name_ar, :name_en, :name_fa, false, :sort_order)"
            ),
            {
                "id": str(uuid.uuid4()),
                "product_type_id": pt_id,
                "code": vt["code"],
                "name_ar": vt["name_ar"],
                "name_en": vt["name_en"],
                "name_fa": vt["name_fa"],
                "sort_order": vt.get("sort_order", 0),
            },
        )
        seeded += 1
    if seeded:
        print(f"Seeded {seeded} new image view types.")


async def _seed_brands(conn, brands: list[dict]) -> None:
    result = await conn.execute(text("SELECT COUNT(*) FROM brands"))
    count = result.scalar()
    if count > 0:
        return

    for brand in brands:
        await conn.execute(
            text("INSERT INTO brands (id, code, name_ar, name_en, name_fa, logo_url, sort_order) VALUES (:id, :code, :name_ar, :name_en, :name_fa, :logo_url, :sort_order)"),
            {
                "id": str(uuid.uuid4()),
                "code": brand["code"],
                "name_ar": brand["name_ar"],
                "name_en": brand["name_en"],
                "name_fa": brand["name_fa"],
                "logo_url": brand.get("logo_url"),
                "sort_order": brand.get("sort_order", 0),
            },
        )
    print(f"Seeded {len(brands)} brands.")


if __name__ == "__main__":
    asyncio.run(seed())
