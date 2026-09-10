import json
from typing import Any, cast

from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CacheKeys, cache_or_fetch
from app.core.error_codes import E
from app.core.exceptions import NotFoundError
from app.repositories.catalog import AttributeOptionRepository, AttributeRepository, BrandRepository, CategoryRepository, ProductTypeRepository, _is_uuid
from app.repositories.product_definition import ProductImageRepository, ProductPieceRepository, ProductSizeRepository, ProductVariantRepository, StoreProductRepository


def _resolve_image_url(path: str) -> str:
    if path.startswith("http"):
        return path
    from app.core.config import settings

    return f"{settings.minio_public_url}/{path}"


_LANG_MAP = {"en": "en", "ar": "ar", "fa": "fa"}


async def _get_parent_chain(db: AsyncSession, category_id: str, lang: str) -> list[dict[str, Any]]:
    chain = []
    for cid, name_en, name_ar, _parent in await CategoryRepository(db).get_chain(category_id):
        name = name_ar if lang == "ar" else name_en
        chain.append({"id": cid, "name": name})
    return chain


async def _resolve_attr_value(db: AsyncSession, raw_value: str, lang: str) -> Any:
    """Resolve a raw attribute value (UUID or JSON) to display names."""
    if not raw_value:
        return None

    # Try parsing as JSON
    try:
        parsed = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        parsed = raw_value

    # Composition: [{material: "...", percentage: N}, ...]
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict) and "material" in parsed[0]:
        resolved = []
        for item in parsed:
            mat = item.get("material", "")
            pct = item.get("percentage", 100)
            mat_name = await AttributeOptionRepository(db).get_localized_value(mat, lang) if _is_uuid(mat) else mat
            resolved.append({"material": mat_name, "percentage": pct})
        return resolved

    # Array of UUIDs (multi-select)
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], str):
        uuids = [u for u in parsed if _is_uuid(u)]
        names = []
        for uid in uuids:
            name = await AttributeOptionRepository(db).get_localized_value(uid, lang)
            if name:
                names.append(name)
        return names if names else parsed

    # Single UUID (select)
    if isinstance(raw_value, str) and _is_uuid(raw_value):
        name = await AttributeOptionRepository(db).get_localized_value(raw_value, lang)
        return name if name else raw_value

    # Plain text
    return raw_value


async def get_product_info(db: AsyncSession, product_id: str, lang: str, redis: AsyncRedis | None = None) -> dict[str, object]:
    async def _fetch() -> dict[str, object]:
        return await _build_product_info(db, product_id, lang)

    if redis is None:
        return await _fetch()
    return await cache_or_fetch(redis, CacheKeys.product_info(product_id, lang), CacheKeys.PRODUCT_INFO.ttl, _fetch)


async def _build_product_info(db: AsyncSession, product_id: str, lang: str) -> dict[str, object]:
    lang = lang if lang in _LANG_MAP else "en"
    name_col = f"name_{lang}"
    short_desc_col = f"short_description_{lang}"
    long_desc_col = f"long_description_{lang}"
    ai_desc_col = f"ai_description_{lang}"
    care_instructions_col = f"care_instructions_{lang}"
    collection_col = f"collection{'' if lang == 'en' else '_' + lang}"

    row = await StoreProductRepository(db).get_info_row(product_id)
    if not row:
        raise NotFoundError("Product not found", translation_key=E.PRODUCT_NOT_FOUND)

    # Brand
    brand_name: str | None = None
    if row["brand"]:
        brand_name = await BrandRepository(db).get_name(row["brand"], lang)

    # Category chain
    category_chain: list[dict[str, Any]] = []
    if row["category_id"]:
        category_chain = await _get_parent_chain(db, row["category_id"], lang)

    # Product type
    product_type_name: str | None = None
    if row["product_type_id"]:
        product_type_name = await ProductTypeRepository(db).get_name(row["product_type_id"], lang)

    # Images
    images = []
    for img in await ProductImageRepository(db).list_info_rows(product_id):
        alt = getattr(img, f"alt_text_{lang}") or img.alt_text_en or ""
        images.append(
            {
                "id": img.id,
                "url": _resolve_image_url(img.image_url),
                "alt_text": alt,
                "is_video": img.is_video,
                "sort_order": img.sort_order,
                "view_type": img.view_type_name,
            }
        )

    # Attribute values
    attributes = []
    for attr in await AttributeRepository(db).list_value_rows_for_product(product_id):
        resolved = await _resolve_attr_value(db, attr.value, lang)
        attr_name = getattr(attr, f"name_{lang}", attr.name_en) or attr.name_en
        attributes.append(
            {
                "code": attr.code,
                "name": attr_name,
                "value_type": attr.value_type,
                "value": resolved,
            }
        )

    # Sizes
    sizes = [
        {
            "label": s.size_label,
            "system": s.size_system,
            "stock": s.stock,
            "sort_order": s.sort_order,
        }
        for s in await ProductSizeRepository(db).list_info_rows(product_id)
    ]

    # Variants
    variants = []
    for v in await ProductVariantRepository(db).list_info_rows(product_id):
        # Get variant option names
        option_names = await ProductVariantRepository(db).list_option_names(v.id, lang)

        # Get variant images
        vimgs = [_resolve_image_url(url) for url in await ProductImageRepository(db).list_urls_by_variant(product_id, v.id)]

        discount_pct = round((1 - v.price / v.original_price) * 100) if v.original_price and v.original_price > 0 and v.price else 0

        variants.append(
            {
                "id": v.id,
                "sku": v.sku,
                "price": v.price,
                "original_price": v.original_price,
                "sale_price": v.sale_price,
                "discount_percentage": discount_pct,
                "stock": v.quantity,
                "is_active": v.is_active,
                "options": option_names,
                "images": vimgs,
            }
        )

    # Pieces
    pieces = [
        {
            "id": p.id,
            "name": getattr(p, f"name_{lang}", p.name_en) or p.name_en,
            "sort_order": p.sort_order,
        }
        for p in await ProductPieceRepository(db).list_info_rows(product_id)
    ]

    result_data: dict[str, Any] = {
        "id": row["id"],
        "name": row[name_col] or row["name_en"],
        "name_ar": row["name_ar"],
        "slug": row["slug"],
        "sku": row["sku"],
        "barcode": row["barcode"],
        "status": row["status"],
        "has_variants": row["has_variants"],
        "is_multi_piece": row["is_multi_piece"],
        "brand": brand_name,
        "category": category_chain[-1] if category_chain else None,
        "category_parents": category_chain[:-1] if len(category_chain) > 1 else [],
        "product_type": product_type_name,
        "price": row["price"],
        "original_price": row["original_price"],
        "sale_price": row["sale_price"],
        "currency": row["currency"],
        "quantity": row["quantity"],
        "low_stock_threshold": row["low_stock_threshold"],
        "weight": row["weight"],
        "weight_unit": row["weight_unit"],
        "collection": row[collection_col] or row["collection"],
        "country_of_origin": row["country_of_origin"],
        "model_height": row["model_height"],
        "model_wears_size": row["model_wears_size"],
        "video_url": row["video_url"],
        "source_url": row["source_url"],
        "short_description": row[short_desc_col] or row["short_description_en"],
        "long_description": row[long_desc_col] or row["long_description_en"],
        "ai_description": row[ai_desc_col] or row["ai_description_en"],
        "care_instructions": row[care_instructions_col] or row["care_instructions_en"],
        "images": images,
        "attributes": attributes,
        "sizes": sizes,
        "variants": variants,
        "pieces": pieces,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }

    return result_data


def minify_product_info(data: dict[str, Any]) -> dict[str, Any]:
    sizes: list[str] = []
    for v in cast("list[dict[str, Any]]", data.get("variants", [])):
        for opt in v.get("options", []):
            if opt not in sizes:
                sizes.append(opt)

    alt_texts: list[str] = []
    for img in cast("list[dict[str, Any]]", data.get("images", [])):
        if img.get("alt_text"):
            alt_texts.append(img["alt_text"])
            if len(alt_texts) >= 2:
                break

    result: dict[str, Any] = {}
    for key, value in data.items():
        if key in ("images", "variants", "pieces", "sizes"):
            continue
        if value is not None:
            result[key] = _strip_nulls(value)

    result["image_alt_texts"] = alt_texts
    result["available_sizes"] = sizes
    return result


def _strip_nulls(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, object] = {}
        for k, v in value.items():
            if v is not None:
                cleaned[k] = _strip_nulls(v)
        return cleaned
    if isinstance(value, list):
        return [_strip_nulls(item) for item in value if item is not None]
    return value
