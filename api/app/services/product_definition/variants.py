"""Variant creation and merge helpers."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_variant import ProductVariant
from app.models.variant_attribute_option import VariantAttributeOption
from app.schemas.product_definition import ProductVariantCreate


async def _create_variant(db: AsyncSession, product_id: str, data: ProductVariantCreate) -> ProductVariant:
    variant = ProductVariant(
        id=str(uuid.uuid4()),
        product_id=product_id,
        color_set_id=data.color_set_id,
        sku=data.sku,
        barcode=data.barcode,
        price=data.price,
        original_price=data.original_price,
        sale_price=data.sale_price,
        quantity=data.quantity,
        low_stock_threshold=data.low_stock_threshold,
        weight=data.weight,
        is_active=data.is_active,
    )
    db.add(variant)
    await db.flush()

    for option_id in data.attribute_option_ids:
        link = VariantAttributeOption(
            variant_id=variant.id,
            attribute_option_id=option_id,
        )
        db.add(link)

    await db.flush()
    return variant


def _variant_signature(option_ids: list[str]) -> str:
    return ",".join(sorted(option_ids))


def _deduplicate_variant_data(data_list: list[ProductVariantCreate]) -> list[ProductVariantCreate]:
    seen: set[str] = set()
    unique: list[ProductVariantCreate] = []
    for v_data in data_list:
        sig = _variant_signature(v_data.attribute_option_ids)
        if sig not in seen:
            seen.add(sig)
            unique.append(v_data)
    return unique


async def _build_existing_variant_map(db: AsyncSession, product_id: str) -> dict[str, ProductVariant]:
    stmt = select(ProductVariant).where(ProductVariant.product_id == product_id).order_by(ProductVariant.sort_order)
    result = await db.execute(stmt)
    existing_map: dict[str, ProductVariant] = {}
    for v in result.scalars().all():
        junction_stmt = select(VariantAttributeOption.attribute_option_id).where(VariantAttributeOption.variant_id == v.id)
        j_result = await db.execute(junction_stmt)
        sig = _variant_signature(list(j_result.scalars().all()))
        existing_map[sig] = v
    return existing_map


async def _merge_variants(
    db: AsyncSession,
    product_id: str,
    variant_data_list: list[ProductVariantCreate],
) -> list[ProductVariant]:
    if not variant_data_list:
        stmt = select(ProductVariant).where(ProductVariant.product_id == product_id)
        result = await db.execute(stmt)
        for v in result.scalars().all():
            await db.delete(v)
        return []

    variant_data_list = _deduplicate_variant_data(variant_data_list)
    existing_map = await _build_existing_variant_map(db, product_id)
    incoming_sigs = {_variant_signature(v.attribute_option_ids) for v in variant_data_list}

    for sig, existing_v in existing_map.items():
        if sig not in incoming_sigs:
            await db.delete(existing_v)

    result_variants: list[ProductVariant] = []
    for v_data in variant_data_list:
        sig = _variant_signature(v_data.attribute_option_ids)
        if sig in existing_map:
            existing = existing_map[sig]
            for field, value in v_data.model_dump(exclude={"attribute_option_ids"}).items():
                setattr(existing, field, value)
            result_variants.append(existing)
        else:
            variant = await _create_variant(db, product_id, v_data)
            result_variants.append(variant)
    return result_variants
