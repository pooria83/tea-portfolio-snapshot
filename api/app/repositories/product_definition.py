from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, case, desc, func, literal, or_, select, text
from sqlalchemy.orm import selectinload

from app.models.ai_description_version import AIDescriptionVersion
from app.models.attribute import Attribute
from app.models.brand import Brand
from app.models.product_attribute_value import ProductAttributeValue
from app.models.product_color_set import ProductColorSet, ProductColorSetValue
from app.models.product_image import ProductImage
from app.models.product_piece import ProductPiece
from app.models.product_size import ProductSize
from app.models.product_variant import ProductVariant
from app.models.store import Store
from app.models.store_product import StoreProduct
from app.models.variant_attribute_option import VariantAttributeOption
from app.repositories.base import BaseRepository


def _name_match_and_score(q: str) -> tuple[ColumnElement[bool], ColumnElement[Any]]:
    """Fuzzy product-name matcher used by every store-product name search.

    Builds a WHERE clause that accepts the exact phrase (case-insensitive substring)
    or any individual word hitting its pg_trgm similarity threshold, plus an ORDER BY
    relevance score: perfect phrase matches first, then products sharing more/closer
    words. AND the clause with scope filters and sort by the score descending.
    """
    en = StoreProduct.name_en
    ar = StoreProduct.name_ar
    phrase = " ".join(q.split())
    phrase_hit = or_(en.ilike(f"%{phrase}%"), ar.ilike(f"%{phrase}%"))

    match_clauses: list[ColumnElement[bool]] = [phrase_hit]
    score_terms: list[ColumnElement[Any]] = [case((phrase_hit, literal(1.0)), else_=literal(0.0))]
    for token in sorted({t for t in q.split() if len(t) >= 2}):
        match_clauses.append(or_(en.op("%")(token), ar.op("%")(token)))
        score_terms.append(func.greatest(func.similarity(en, token), func.similarity(ar, token)))

    score: ColumnElement[Any] = score_terms[0]
    for term in score_terms[1:]:
        score = score + term
    return or_(*match_clauses), score


class StoreProductRepository(BaseRepository[StoreProduct]):
    model = StoreProduct

    async def get_with_all(self, product_id: str) -> StoreProduct | None:
        stmt = (
            select(StoreProduct)
            .options(
                selectinload(StoreProduct.store),
                selectinload(StoreProduct.brand_obj),
                selectinload(StoreProduct.images),
                selectinload(StoreProduct.sizes),
                selectinload(StoreProduct.pieces),
                selectinload(StoreProduct.color_sets)
                .selectinload(ProductColorSet.values)
                .options(
                    selectinload(ProductColorSetValue.color_option),
                    selectinload(ProductColorSetValue.piece),
                ),
                selectinload(StoreProduct.attribute_values).selectinload(ProductAttributeValue.attribute).selectinload(Attribute.options),
                selectinload(StoreProduct.variants).options(
                    selectinload(ProductVariant.attribute_options),
                    selectinload(ProductVariant.color_set)
                    .selectinload(ProductColorSet.values)
                    .options(
                        selectinload(ProductColorSetValue.color_option),
                        selectinload(ProductColorSetValue.piece),
                    ),
                ),
                selectinload(StoreProduct.ai_description_versions),
            )
            .where(StoreProduct.id == product_id)
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def list_names_brands(self, ids: list[str]) -> list[Any]:
        """Trilingual name + brand rows for the given product ids (chat enrichment)."""
        stmt = (
            select(
                StoreProduct.id,
                StoreProduct.name_ar,
                StoreProduct.name_en,
                StoreProduct.name_fa,
                Brand.name_ar.label("brand_ar"),
                Brand.name_en.label("brand_en"),
                Brand.name_fa.label("brand_fa"),
            )
            .outerjoin(Brand, StoreProduct.brand == Brand.id)
            .where(StoreProduct.id.in_(ids))
        )
        result = await self.db.execute(stmt)
        return list(result.all())

    def _base_list_options(self) -> list[Any]:
        return [
            selectinload(StoreProduct.store),
            selectinload(StoreProduct.brand_obj),
            selectinload(StoreProduct.images),
            selectinload(StoreProduct.sizes),
            selectinload(StoreProduct.pieces),
            selectinload(StoreProduct.color_sets)
            .selectinload(ProductColorSet.values)
            .options(
                selectinload(ProductColorSetValue.color_option),
                selectinload(ProductColorSetValue.piece),
            ),
            selectinload(StoreProduct.attribute_values).selectinload(ProductAttributeValue.attribute).selectinload(Attribute.options),
            selectinload(StoreProduct.variants).options(
                selectinload(ProductVariant.attribute_options),
                selectinload(ProductVariant.color_set)
                .selectinload(ProductColorSet.values)
                .options(
                    selectinload(ProductColorSetValue.color_option),
                    selectinload(ProductColorSetValue.piece),
                ),
            ),
            selectinload(StoreProduct.ai_description_versions),
        ]

    async def count_by_store(self, store_id: str) -> int:
        stmt = select(func.count(StoreProduct.id)).where(StoreProduct.store_id == store_id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def list_by_store(self, store_id: str, skip: int = 0, limit: int = 20) -> list[StoreProduct]:
        stmt = (
            select(StoreProduct).options(*self._base_list_options()).where(StoreProduct.store_id == store_id).order_by(desc(StoreProduct.created_at), desc(StoreProduct.id)).offset(skip).limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    async def random(self, limit: int = 20) -> list[StoreProduct]:
        stmt = select(StoreProduct).options(*self._base_list_options()).order_by(func.random()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    async def count_by_store_ids(self, store_ids: list[str], status: str | None = None) -> int:
        stmt = select(func.count(StoreProduct.id)).where(StoreProduct.store_id.in_(store_ids))
        if status:
            stmt = stmt.where(StoreProduct.status == status)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def count_ai_description_status(self) -> tuple[int, int]:
        """(total, pending) counts for the admin cron summary."""
        total = int((await self.db.execute(select(func.count()).select_from(StoreProduct))).scalar_one())
        pending = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(StoreProduct)
                    .where(
                        StoreProduct.ai_description_en.is_(None),
                        StoreProduct.ai_description_ar.is_(None),
                    )
                )
            ).scalar_one()
        )
        return total, pending

    async def list_by_store_ids(self, store_ids: list[str], skip: int = 0, limit: int = 20) -> list[StoreProduct]:
        stmt = (
            select(StoreProduct)
            .options(*self._base_list_options())
            .where(StoreProduct.store_id.in_(store_ids))
            .order_by(desc(StoreProduct.created_at), desc(StoreProduct.id))
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    async def search_by_name(
        self,
        query: str,
        store_ids: list[str] | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[StoreProduct], int]:
        min_query_length = 3
        q = query.strip()
        if len(q) < min_query_length:
            stmt = (
                select(StoreProduct)
                .options(*self._base_list_options())
                .where(
                    or_(
                        StoreProduct.name_en.ilike(f"%{q}%"),
                        StoreProduct.name_ar.ilike(f"%{q}%"),
                    ),
                )
                .order_by(desc(StoreProduct.created_at), desc(StoreProduct.id))
                .offset(skip)
                .limit(limit)
            )
            if store_ids:
                stmt = stmt.where(StoreProduct.store_id.in_(store_ids))
            count_stmt = select(func.count(StoreProduct.id)).where(
                or_(
                    StoreProduct.name_en.ilike(f"%{q}%"),
                    StoreProduct.name_ar.ilike(f"%{q}%"),
                ),
            )
            if store_ids:
                count_stmt = count_stmt.where(StoreProduct.store_id.in_(store_ids))
            result = await self.db.execute(stmt)
            items = list(result.unique().scalars().all())
            total = (await self.db.execute(count_stmt)).scalar_one()
            return items, total

        name_match, relevance = _name_match_and_score(q)

        stmt = select(StoreProduct).options(*self._base_list_options()).where(name_match)
        if store_ids:
            stmt = stmt.where(StoreProduct.store_id.in_(store_ids))
        stmt = stmt.order_by(relevance.desc(), desc(StoreProduct.created_at), desc(StoreProduct.id)).offset(skip).limit(limit)

        count_stmt = select(func.count(StoreProduct.id)).where(name_match)
        if store_ids:
            count_stmt = count_stmt.where(StoreProduct.store_id.in_(store_ids))

        result = await self.db.execute(stmt)
        items = list(result.unique().scalars().all())
        total = (await self.db.execute(count_stmt)).scalar_one()
        return items, total

    async def _first_image_map(self, product_ids: list[str]) -> dict[str, str]:
        """First image URL (lowest sort_order) per product id."""
        if not product_ids:
            return {}
        stmt = select(ProductImage.product_id, ProductImage.image_url).where(ProductImage.product_id.in_(product_ids)).order_by(ProductImage.sort_order)
        result = await self.db.execute(stmt)
        first: dict[str, str] = {}
        for pid, url in result.all():
            if pid not in first:
                first[pid] = url
        return first

    def _light_rows(
        self,
        rows: Sequence[Any],
        images: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Flatten store product rows (with brand + store joins) into list items."""
        items: list[dict[str, Any]] = []
        for row in rows:
            p = row.StoreProduct
            items.append(
                {
                    "id": p.id,
                    "store_id": p.store_id,
                    "store_name": row.store_name,
                    "product_type_id": p.product_type_id,
                    "name_ar": p.name_ar,
                    "name_en": p.name_en,
                    "name_fa": p.name_fa,
                    "brand_name": row.brand_en,
                    "status": p.status,
                    "has_variants": p.has_variants,
                    "price": p.price,
                    "original_price": p.original_price,
                    "sale_price": p.sale_price,
                    "currency": p.currency,
                    "quantity": p.quantity,
                    "image_url": images.get(p.id),
                }
            )
        return items

    async def list_by_store_ids_light(self, store_ids: list[str], skip: int = 0, limit: int = 20) -> list[dict[str, Any]]:
        """Flat product list rows (brand + store joins, no relationship chains)."""
        stmt = (
            select(
                StoreProduct,
                Brand.name_ar.label("brand_ar"),
                Brand.name_en.label("brand_en"),
                Brand.name_fa.label("brand_fa"),
                Store.name.label("store_name"),
            )
            .outerjoin(Brand, StoreProduct.brand == Brand.id)
            .outerjoin(Store, StoreProduct.store_id == Store.id)
            .where(StoreProduct.store_id.in_(store_ids))
            .order_by(desc(StoreProduct.created_at), desc(StoreProduct.id))
            .offset(skip)
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).all()
        images = await self._first_image_map([r.StoreProduct.id for r in rows])
        return self._light_rows(rows, images)

    async def search_by_name_light(
        self,
        query: str,
        store_ids: list[str] | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        q = query.strip()
        name_match, relevance = _name_match_and_score(q)
        stmt = (
            select(
                StoreProduct,
                Brand.name_ar.label("brand_ar"),
                Brand.name_en.label("brand_en"),
                Brand.name_fa.label("brand_fa"),
                Store.name.label("store_name"),
            )
            .outerjoin(Brand, StoreProduct.brand == Brand.id)
            .outerjoin(Store, StoreProduct.store_id == Store.id)
            .where(name_match)
            .order_by(relevance.desc(), desc(StoreProduct.created_at), desc(StoreProduct.id))
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count(StoreProduct.id)).where(name_match)
        if store_ids:
            stmt = stmt.where(StoreProduct.store_id.in_(store_ids))
            count_stmt = count_stmt.where(StoreProduct.store_id.in_(store_ids))
        rows = (await self.db.execute(stmt)).all()
        total = (await self.db.execute(count_stmt)).scalar_one()
        images = await self._first_image_map([r.StoreProduct.id for r in rows])
        return self._light_rows(rows, images), total

    async def random_light(self, limit: int = 20) -> list[dict[str, Any]]:
        stmt = (
            select(
                StoreProduct,
                Brand.name_ar.label("brand_ar"),
                Brand.name_en.label("brand_en"),
                Brand.name_fa.label("brand_fa"),
                Store.name.label("store_name"),
            )
            .outerjoin(Brand, StoreProduct.brand == Brand.id)
            .outerjoin(Store, StoreProduct.store_id == Store.id)
            .order_by(func.random())
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).all()
        images = await self._first_image_map([r.StoreProduct.id for r in rows])
        return self._light_rows(rows, images)

    async def delete_attribute_values(self, product_id: str) -> None:
        stmt = select(ProductAttributeValue).where(ProductAttributeValue.product_id == product_id)
        result = await self.db.execute(stmt)
        for row in result.scalars().all():
            await self.db.delete(row)

    async def delete_sizes(self, product_id: str) -> None:
        stmt = select(ProductSize).where(ProductSize.product_id == product_id)
        result = await self.db.execute(stmt)
        for row in result.scalars().all():
            await self.db.delete(row)

    async def delete_variants(self, product_id: str) -> None:
        stmt = select(ProductVariant).where(ProductVariant.product_id == product_id)
        result = await self.db.execute(stmt)
        for row in result.scalars().all():
            await self.db.delete(row)

    async def delete_images(self, product_id: str) -> None:
        stmt = select(ProductImage).where(ProductImage.product_id == product_id)
        result = await self.db.execute(stmt)
        for row in result.scalars().all():
            await self.db.delete(row)

    async def get_with_ai_versions(self, product_id: str) -> StoreProduct | None:
        stmt = select(StoreProduct).where(StoreProduct.id == product_id).options(selectinload(StoreProduct.ai_description_versions))
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_store_id(self, product_id: str) -> str | None:
        stmt = select(StoreProduct.store_id).where(StoreProduct.id == product_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_category_id(self, product_id: str) -> str | None:
        stmt = select(StoreProduct.category_id).where(StoreProduct.id == product_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_store_and_source_url(self, store_id: str, source_url: str) -> StoreProduct | None:
        stmt = select(StoreProduct).where(StoreProduct.store_id == store_id, StoreProduct.source_url == source_url)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_info_row(self, product_id: str) -> dict[str, Any] | None:
        """Full store_products row (all columns) as a dict for product-info assembly."""
        result = await self.db.execute(
            select(
                text("""
                    sp.id, sp.name_en, sp.name_ar, sp.name_fa,
                    sp.short_description_en, sp.short_description_ar, sp.short_description_fa,
                    sp.long_description_en, sp.long_description_ar, sp.long_description_fa,
                    sp.ai_description_en, sp.ai_description_ar, sp.ai_description_fa,
                    sp.brand, sp.slug, sp.sku, sp.barcode,
                    sp.status, sp.has_variants, sp.is_multi_piece,
                    sp.price, sp.original_price, sp.sale_price, sp.currency,
                    sp.quantity, sp.low_stock_threshold,
                    sp.weight, sp.weight_unit,
                    sp.collection, sp.collection_ar, sp.collection_fa,
                    sp.country_of_origin,
                    sp.care_instructions_en, sp.care_instructions_ar, sp.care_instructions_fa,
                    sp.model_height, sp.model_wears_size,
                    sp.video_url, sp.source_url,
                    sp.meta_title_en, sp.meta_title_ar, sp.meta_title_fa,
                    sp.meta_description_en, sp.meta_description_ar, sp.meta_description_fa,
                    sp.category_id, sp.product_type_id,
                    sp.created_at, sp.updated_at
                """),
            )
            .select_from(text("store_products sp"))
            .where(text("sp.id = :pid")),
            {"pid": product_id},
        )
        row = result.one_or_none()
        if row is None:
            return None
        return dict(row._mapping)

    async def list_cron_page(
        self,
        status: str | None,
        skip: int,
        limit: int,
    ) -> tuple[list[tuple[StoreProduct, datetime | None, str | None]], int]:
        """Admin cron report: products with their latest AI description version."""
        base = select(StoreProduct)
        if status == "generated":
            base = base.where(StoreProduct.ai_description_en.isnot(None) | StoreProduct.ai_description_ar.isnot(None))
        elif status == "pending":
            base = base.where(
                StoreProduct.ai_description_en.is_(None),
                StoreProduct.ai_description_ar.is_(None),
            )

        total = int((await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())

        latest_version = (
            select(AIDescriptionVersion.product_id, AIDescriptionVersion.created_at, AIDescriptionVersion.model)
            .distinct(AIDescriptionVersion.product_id)
            .order_by(AIDescriptionVersion.product_id, AIDescriptionVersion.created_at.desc())
            .subquery()
        )
        query = (
            base.add_columns(
                latest_version.c.created_at,
                latest_version.c.model,
            )
            .outerjoin(latest_version, StoreProduct.id == latest_version.c.product_id)
            .order_by(StoreProduct.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        rows = (await self.db.execute(query)).all()
        items: list[tuple[StoreProduct, datetime | None, str | None]] = [(row.StoreProduct, row.created_at, row.model) for row in rows]
        return items, total

    async def get_llm_counts(self) -> tuple[int, int]:
        """(total, pending) product counts for the cron summary."""
        total = await self.db.scalar(select(func.count()).select_from(StoreProduct)) or 0
        pending = (
            await self.db.scalar(
                select(func.count())
                .select_from(StoreProduct)
                .where(
                    StoreProduct.ai_description_en.is_(None),
                    StoreProduct.ai_description_ar.is_(None),
                )
            )
            or 0
        )
        return total, pending

    async def list_without_ai_description(self, failed_ids: set[str], limit: int = 10) -> list[StoreProduct]:
        stmt = (
            select(StoreProduct)
            .where(
                StoreProduct.ai_description_en.is_(None),
                StoreProduct.ai_description_ar.is_(None),
            )
            .order_by(StoreProduct.updated_at.asc())
            .limit(limit)
        )
        if failed_ids:
            stmt = stmt.where(StoreProduct.id.not_in(failed_ids))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class ProductImageRepository(BaseRepository[ProductImage]):
    model = ProductImage
    TOUCHES: frozenset[str] = frozenset({"product_images"})

    async def get_by_store(self, image_id: str, store_id: str) -> ProductImage | None:
        stmt = select(ProductImage).join(StoreProduct, StoreProduct.id == ProductImage.product_id).where(ProductImage.id == image_id, StoreProduct.store_id == store_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_store_and_ids(self, store_id: str, ordered_ids: list[str]) -> list[ProductImage]:
        stmt = select(ProductImage).join(StoreProduct, StoreProduct.id == ProductImage.product_id).where(StoreProduct.store_id == store_id, ProductImage.id.in_(ordered_ids))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_urls_by_variant(self, product_id: str, variant_id: str) -> list[str]:
        stmt = select(ProductImage.image_url).where(ProductImage.variant_id == variant_id, ProductImage.product_id == product_id).order_by(ProductImage.sort_order)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_temp_urls(self) -> list[str]:
        """Image URLs under the 'temp/' prefix (used by the temp-file cleanup script)."""
        result = await self.db.execute(select(ProductImage.image_url).where(ProductImage.image_url.like("temp/%")))
        return [row for row in result.scalars().all() if row]

    async def list_info_rows(self, product_id: str) -> list[Any]:
        """Product images joined with their view type, for product-info assembly."""
        result = await self.db.execute(
            select(
                text("""
                    pi.id, pi.image_url, pi.alt_text_en, pi.alt_text_ar, pi.alt_text_fa,
                    pi.is_video, pi.sort_order, ptivt.name_en AS view_type_name
                """),
            )
            .select_from(text("product_images pi"))
            .outerjoin(text("product_type_image_view_types ptivt"), text("ptivt.id = pi.view_type_id"))
            .where(text("pi.product_id = :pid"))
            .order_by(text("pi.sort_order")),
            {"pid": product_id},
        )
        return list(result.all())


class ProductVariantRepository(BaseRepository[ProductVariant]):
    model = ProductVariant
    TOUCHES: frozenset[str] = frozenset({"product_variants"})

    async def get_by_product(self, variant_id: str, product_id: str) -> ProductVariant | None:
        stmt = select(ProductVariant).where(ProductVariant.id == variant_id, ProductVariant.product_id == product_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_attribute_options(self, variant_id: str) -> ProductVariant:
        stmt = select(ProductVariant).options(selectinload(ProductVariant.attribute_options)).where(ProductVariant.id == variant_id)
        result = await self.db.execute(stmt)
        return result.unique().scalar_one()

    async def delete_attribute_links(self, variant_id: str) -> None:
        stmt = select(VariantAttributeOption).where(VariantAttributeOption.variant_id == variant_id)
        result = await self.db.execute(stmt)
        for link in result.scalars().all():
            await self.db.delete(link)

    async def list_info_rows(self, product_id: str) -> list[Any]:
        result = await self.db.execute(
            select(
                text("""
                    pv.id, pv.sku, pv.price, pv.original_price, pv.sale_price,
                    pv.quantity, pv.is_active, pv.sort_order
                """),
            )
            .select_from(text("product_variants pv"))
            .where(text("pv.product_id = :pid"))
            .order_by(text("pv.sort_order")),
            {"pid": product_id},
        )
        return list(result.all())

    async def list_option_names(self, variant_id: str, lang: str) -> list[str]:
        """Localized attribute option display names for a variant."""
        val_col = f"value_{lang}" if lang in ("en", "ar", "fa") else "value_en"
        result = await self.db.execute(
            text(f"""
                SELECT ao.{val_col} AS option_name
                FROM variant_attribute_options vaoo
                JOIN attribute_options ao ON ao.id = vaoo.attribute_option_id
                WHERE vaoo.variant_id = :vid
                ORDER BY ao.sort_order
            """),
            {"vid": variant_id},
        )
        return [row.option_name for row in result if row.option_name]


class ProductSizeRepository(BaseRepository[ProductSize]):
    model = ProductSize
    TOUCHES: frozenset[str] = frozenset({"product_sizes"})

    async def list_info_rows(self, product_id: str) -> list[Any]:
        result = await self.db.execute(
            select(
                text("""
                    ps.id, ps.size_label, ps.size_system, ps.stock, ps.sort_order
                """),
            )
            .select_from(text("product_sizes ps"))
            .where(text("ps.product_id = :pid"))
            .order_by(text("ps.sort_order")),
            {"pid": product_id},
        )
        return list(result.all())


class ProductPieceRepository(BaseRepository[ProductPiece]):
    model = ProductPiece
    TOUCHES: frozenset[str] = frozenset({"product_pieces"})

    async def list_info_rows(self, product_id: str) -> list[Any]:
        result = await self.db.execute(
            select(
                text("""
                    pp.id, pp.name_en, pp.name_ar, pp.sort_order
                """),
            )
            .select_from(text("product_pieces pp"))
            .where(text("pp.product_id = :pid"))
            .order_by(text("pp.sort_order")),
            {"pid": product_id},
        )
        return list(result.all())
