"""Color-set and piece upsert helpers."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import E
from app.core.exceptions import ValidationError
from app.models.attribute_option import AttributeOption
from app.models.product_color_set import ProductColorSet, ProductColorSetValue
from app.models.product_piece import ProductPiece
from app.schemas.product_definition import ProductColorSetInput, ProductPieceInput


async def _existing_piece_map(db: AsyncSession, product_id: str) -> dict[int, str]:
    stmt = select(ProductPiece).where(ProductPiece.product_id == product_id)
    result = await db.execute(stmt)
    return {p.sort_order: p.id for p in result.scalars().all()}


async def _existing_color_set_map(db: AsyncSession, product_id: str) -> dict[int, str]:
    stmt = select(ProductColorSet).where(ProductColorSet.product_id == product_id)
    result = await db.execute(stmt)
    return {cs.sort_order: cs.id for cs in result.scalars().all()}


async def _upsert_pieces(
    db: AsyncSession,
    product_id: str,
    pieces: list[ProductPieceInput],
) -> dict[int, str]:
    """Upsert pieces by sort_order, preserving existing IDs when the order matches."""
    stmt = select(ProductPiece).where(ProductPiece.product_id == product_id).order_by(ProductPiece.sort_order)
    result = await db.execute(stmt)
    existing: dict[int, ProductPiece] = {}
    for piece in result.scalars().all():
        existing.setdefault(piece.sort_order, piece)

    incoming_orders = {p.sort_order for p in pieces}
    for order, existing_piece in list(existing.items()):
        if order not in incoming_orders:
            await db.delete(existing_piece)

    order_map: dict[int, str] = {}
    used: set[int] = set()
    for piece_data in pieces:
        matched = existing.get(piece_data.sort_order)
        if matched is not None and piece_data.sort_order not in used:
            matched.name_en = piece_data.name_en
            matched.name_ar = piece_data.name_ar
            used.add(piece_data.sort_order)
            order_map[piece_data.sort_order] = matched.id
        else:
            new_piece = ProductPiece(
                id=str(uuid.uuid4()),
                product_id=product_id,
                name_en=piece_data.name_en,
                name_ar=piece_data.name_ar,
                sort_order=piece_data.sort_order,
            )
            db.add(new_piece)
            await db.flush()
            order_map[piece_data.sort_order] = new_piece.id
    return order_map


async def _clear_color_set_values(db: AsyncSession, product_id: str) -> None:
    subq = select(ProductColorSet.id).where(ProductColorSet.product_id == product_id)
    await db.execute(delete(ProductColorSetValue).where(ProductColorSetValue.color_set_id.in_(subq)))


def _resolve_piece_ref(ref: str, piece_by_order: dict[int, str]) -> str | None:
    try:
        pos = int(ref)
        return piece_by_order.get(pos)
    except (ValueError, TypeError):
        return ref if ref in piece_by_order.values() else None


def _resolve_color_set_ref(ref: str, color_set_by_order: dict[int, str]) -> str | None:
    try:
        pos = int(ref)
        return color_set_by_order.get(pos)
    except (ValueError, TypeError):
        return ref if ref in color_set_by_order.values() else None


async def _validate_color_set_refs(
    db: AsyncSession,
    color_sets: list[ProductColorSetInput],
    piece_by_order: dict[int, str],
) -> None:
    """Resolve/remap piece references and validate option references in color sets."""
    option_ids: set[str] = set()
    for cs in color_sets:
        for val in cs.values:
            if val.color_option_id:
                option_ids.add(val.color_option_id)
            if val.piece_id:
                resolved = _resolve_piece_ref(val.piece_id, piece_by_order)
                if resolved is None:
                    raise ValidationError("Invalid piece reference in color set", translation_key=E.VALIDATION_ERROR)
                val.piece_id = resolved
    if option_ids:
        result = await db.execute(select(AttributeOption.id).where(AttributeOption.id.in_(option_ids)))
        valid = {row[0] for row in result.all()}
        missing = option_ids - valid
        if missing:
            raise ValidationError("Invalid color option reference in color set", translation_key=E.VALIDATION_ERROR)


async def _upsert_color_sets(
    db: AsyncSession,
    product_id: str,
    color_sets: list[ProductColorSetInput],
) -> dict[int, str]:
    """Upsert color sets by sort_order, preserving existing IDs when the order matches."""
    stmt = select(ProductColorSet).where(ProductColorSet.product_id == product_id).order_by(ProductColorSet.sort_order)
    result = await db.execute(stmt)
    existing: dict[int, ProductColorSet] = {}
    for cs in result.scalars().all():
        existing.setdefault(cs.sort_order, cs)

    incoming_orders = {cs.sort_order for cs in color_sets}
    for order, existing_cs in list(existing.items()):
        if order not in incoming_orders:
            await db.delete(existing_cs)

    order_map: dict[int, str] = {}
    used: set[int] = set()
    for cs_data in color_sets:
        matched_cs = existing.get(cs_data.sort_order)
        if matched_cs is not None and cs_data.sort_order not in used:
            cs = matched_cs
            used.add(cs_data.sort_order)
            order_map[cs_data.sort_order] = cs.id
        else:
            cs = ProductColorSet(id=str(uuid.uuid4()), product_id=product_id, sort_order=cs_data.sort_order)
            db.add(cs)
            await db.flush()
            order_map[cs_data.sort_order] = cs.id
        for val_data in cs_data.values:
            db.add(
                ProductColorSetValue(
                    id=str(uuid.uuid4()),
                    color_set_id=cs.id,
                    piece_id=val_data.piece_id,
                    color_option_id=val_data.color_option_id,
                )
            )
    return order_map
