import json
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import joinedload

from app.core.cache import CacheKeys, cache_or_fetch
from app.models.attribute import Attribute
from app.models.attribute_group import AttributeGroup
from app.models.attribute_option import AttributeOption
from app.models.brand import Brand
from app.models.category import Category
from app.models.product_type import ProductType
from app.models.product_type_attribute import ProductTypeAttribute
from app.models.product_type_image_view_type import ProductTypeImageViewType
from app.repositories.base import BaseRepository

_LANG_COLUMNS = {"en": "en", "ar": "ar", "fa": "fa"}

_COLOR_ATTR_SQL = """
    (LOWER(a.code) LIKE '%color%'
     OR LOWER(a.name_en) LIKE '%color%'
     OR LOWER(a.name_ar) LIKE '%لون%')
"""

_COLOR_FAMILY_ALIAS = {"printed": "specialty"}

_COLOR_VALUE_ALIAS = {
    "printed": "Multicolor",
    "مطبوع": "متعدد الألوان",
}


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _extract_option_uuids(raw_value: Any) -> list[str]:
    """Extract option UUIDs from a raw attribute value.

    Stored values are JSON arrays (e.g. '["878e89cb-..."]') or bare UUIDs.
    """
    if not raw_value:
        return []
    try:
        parsed: Any = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
    except (json.JSONDecodeError, TypeError):
        parsed = raw_value
    if isinstance(parsed, str):
        return [parsed] if _is_uuid(parsed) else []
    if isinstance(parsed, list):
        return [u for u in parsed if isinstance(u, str) and _is_uuid(u)]
    return []


def _normalize_color_value(value: str) -> str:
    return _COLOR_VALUE_ALIAS.get(value.strip().lower(), value)


def _product_type_dto(pt: ProductType) -> dict[str, Any]:
    return {
        "id": pt.id,
        "code": pt.code,
        "name_ar": pt.name_ar,
        "name_en": pt.name_en,
        "name_fa": pt.name_fa,
        "icon": pt.icon,
        "sort_order": pt.sort_order,
    }


def _category_dto(c: Category) -> dict[str, Any]:
    return {
        "id": c.id,
        "parent_id": c.parent_id,
        "product_type_id": c.product_type_id,
        "name_ar": c.name_ar,
        "name_en": c.name_en,
        "name_fa": c.name_fa,
        "icon": c.icon,
        "sort_order": c.sort_order,
        "is_active": c.is_active,
    }


def _option_dto(o: AttributeOption) -> dict[str, Any]:
    return {
        "id": o.id,
        "code": o.code,
        "value_ar": o.value_ar,
        "value_en": o.value_en,
        "value_fa": o.value_fa,
        "icon": o.icon,
        "color_hex": o.color_hex,
        "image_url": o.image_url,
        "color_family": o.color_family,
        "is_major": o.is_major,
        "sort_order": o.sort_order,
    }


def _attribute_dto(attr: Attribute) -> dict[str, Any]:
    return {
        "id": attr.id,
        "group_id": attr.group_id,
        "group_code": attr.group.code if attr.group else "",
        "code": attr.code,
        "name_ar": attr.name_ar,
        "name_en": attr.name_en,
        "name_fa": attr.name_fa,
        "description_ar": attr.description_ar,
        "description_en": attr.description_en,
        "description_fa": attr.description_fa,
        "value_type": attr.value_type,
        "input_type": attr.input_type,
        "icon": attr.icon,
        "unit": attr.unit,
        "is_required": attr.is_required,
        "validation_rules": attr.validation_rules,
        "is_filterable": attr.is_filterable,
        "is_searchable": attr.is_searchable,
        "is_search_affecting": attr.is_search_affecting,
        "is_visible_on_show": attr.is_visible_on_show,
        "is_variant_defining": attr.is_variant_defining,
        "sort_order": attr.sort_order,
        "options": [_option_dto(o) for o in attr.options],
    }


def _group_dto(g: AttributeGroup) -> dict[str, Any]:
    return {
        "id": g.id,
        "code": g.code,
        "name_ar": g.name_ar,
        "name_en": g.name_en,
        "name_fa": g.name_fa,
        "icon": g.icon,
        "sort_order": g.sort_order,
    }


def _brand_dto(b: Brand) -> dict[str, Any]:
    return {
        "id": b.id,
        "code": b.code,
        "name_ar": b.name_ar,
        "name_en": b.name_en,
        "name_fa": b.name_fa,
        "logo_url": b.logo_url,
        "sort_order": b.sort_order,
    }


def _image_view_type_dto(ivt: ProductTypeImageViewType) -> dict[str, Any]:
    return {
        "id": ivt.id,
        "product_type_id": ivt.product_type_id,
        "code": ivt.code,
        "name_ar": ivt.name_ar,
        "name_en": ivt.name_en,
        "name_fa": ivt.name_fa,
        "is_video": ivt.is_video,
        "sort_order": ivt.sort_order,
    }


class CategoryRepository(BaseRepository[Category]):
    model = Category
    TOUCHES: frozenset[str] = frozenset({"categories"})

    async def list_by_product_type(self, product_type_id: str) -> list[Category]:
        stmt = (
            select(Category)
            .where(Category.product_type_id == product_type_id, Category.is_active == True)  # noqa: E712
            .order_by(Category.sort_order)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_root(self) -> list[Category]:
        stmt = (
            select(Category)
            .where(Category.parent_id.is_(None), Category.is_active == True)  # noqa: E712
            .order_by(Category.sort_order)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self) -> list[Category]:
        stmt = (
            select(Category)
            .where(Category.is_active == True)  # noqa: E712
            .order_by(Category.sort_order)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_all_dto(self) -> list[dict[str, Any]]:
        """Cached JSON-safe category rows (flat, active only)."""

        async def _fetch() -> list[dict[str, Any]]:
            stmt = (
                select(Category)
                .where(Category.is_active == True)  # noqa: E712
                .order_by(Category.sort_order)
            )
            result = await self.db.execute(stmt)
            return [_category_dto(c) for c in result.scalars().all()]

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, f"{CacheKeys.CAT_CATEGORIES.prefix}all", CacheKeys.CAT_CATEGORIES.ttl, _fetch)

    async def list_by_product_type_dto(self, product_type_id: str) -> list[dict[str, Any]]:
        """Cached JSON-safe category rows scoped to a product type."""

        async def _fetch() -> list[dict[str, Any]]:
            stmt = (
                select(Category)
                .where(Category.product_type_id == product_type_id, Category.is_active == True)  # noqa: E712
                .order_by(Category.sort_order)
            )
            result = await self.db.execute(stmt)
            return [_category_dto(c) for c in result.scalars().all()]

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, f"{CacheKeys.CAT_CATEGORIES.prefix}pt:{product_type_id}", CacheKeys.CAT_CATEGORIES.ttl, _fetch)

    async def get_children(self, parent_id: str) -> list[Category]:
        stmt = (
            select(Category)
            .where(Category.parent_id == parent_id, Category.is_active == True)  # noqa: E712
            .order_by(Category.sort_order)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_chain(self, category_id: str) -> list[tuple[str, str, str, str | None]]:
        """Leaf -> root chain of (id, name_en, name_ar, parent_id)."""
        chain: list[tuple[str, str, str, str | None]] = []
        cid = category_id
        while cid:
            result = await self.db.execute(select(Category.id, Category.name_en, Category.name_ar, Category.parent_id).where(Category.id == cid))
            row = result.one_or_none()
            if not row:
                break
            chain.append((str(row[0]), str(row[1]), str(row[2]), row[3]))
            cid = row[3]
        return chain

    async def list_minimal(self) -> list[tuple[str, str, str | None, str | None]]:
        """All categories as (id, name_en, product_type_id, parent_id)."""
        result = await self.db.execute(select(Category.id, Category.name_en, Category.product_type_id, Category.parent_id))
        return [(str(row[0]), str(row[1]), str(row[2]) if row[2] else None, str(row[3]) if row[3] else None) for row in result.fetchall()]


class BrandRepository(BaseRepository[Brand]):
    model = Brand
    TOUCHES: frozenset[str] = frozenset({"brands"})

    async def list_all(self) -> list[Brand]:
        stmt = select(Brand).order_by(Brand.sort_order)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_all_dto(self) -> list[dict[str, Any]]:
        """Cached JSON-safe brand rows."""

        async def _fetch() -> list[dict[str, Any]]:
            stmt = select(Brand).order_by(Brand.sort_order)
            result = await self.db.execute(stmt)
            return [_brand_dto(b) for b in result.scalars().all()]

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, f"{CacheKeys.CAT_BRANDS.prefix}all", CacheKeys.CAT_BRANDS.ttl, _fetch)

    async def get_name(self, brand_id: str, lang: str) -> str | None:
        name_col = f"name_{_LANG_COLUMNS.get(lang, 'en')}"
        stmt = select(getattr(Brand, name_col)).where(Brand.id == brand_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


class AttributeRepository(BaseRepository[Attribute]):
    model = Attribute
    TOUCHES: frozenset[str] = frozenset({"attributes"})

    async def list_by_group(self, group_id: str) -> list[Attribute]:
        stmt = select(Attribute).options(joinedload(Attribute.options), joinedload(Attribute.group)).where(Attribute.group_id == group_id).order_by(Attribute.sort_order)
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    async def list_by_group_dto(self, group_id: str) -> list[dict[str, Any]]:
        """Cached JSON-safe attribute rows for a group (options + group code included)."""

        async def _fetch() -> list[dict[str, Any]]:
            stmt = select(Attribute).options(joinedload(Attribute.options), joinedload(Attribute.group)).where(Attribute.group_id == group_id).order_by(Attribute.sort_order)
            result = await self.db.execute(stmt)
            return [_attribute_dto(a) for a in result.unique().scalars().all()]

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, f"{CacheKeys.CAT_ATTRIBUTES.prefix}group:{group_id}", CacheKeys.CAT_ATTRIBUTES.ttl, _fetch)

    async def list_id_code_input(self) -> list[tuple[str, str, str]]:
        """All attributes as (id, code, input_type) for scraper reference data."""
        result = await self.db.execute(select(Attribute.id, Attribute.code, Attribute.input_type))
        return [(str(row[0]), str(row[1]), str(row[2])) for row in result.fetchall()]

    async def list_by_product_type(self, product_type_id: str) -> list[Attribute]:
        stmt = (
            select(Attribute)
            .join(ProductTypeAttribute, ProductTypeAttribute.attribute_id == Attribute.id)
            .options(joinedload(Attribute.options), joinedload(Attribute.group))
            .where(ProductTypeAttribute.product_type_id == product_type_id)
            .order_by(ProductTypeAttribute.sort_order)
        )
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    async def list_by_product_type_dto(self, product_type_id: str) -> list[dict[str, Any]]:
        """Cached JSON-safe attribute rows for a product type."""

        async def _fetch() -> list[dict[str, Any]]:
            stmt = (
                select(Attribute)
                .join(ProductTypeAttribute, ProductTypeAttribute.attribute_id == Attribute.id)
                .options(joinedload(Attribute.options), joinedload(Attribute.group))
                .where(ProductTypeAttribute.product_type_id == product_type_id)
                .order_by(ProductTypeAttribute.sort_order)
            )
            result = await self.db.execute(stmt)
            return [_attribute_dto(a) for a in result.unique().scalars().all()]

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, f"{CacheKeys.CAT_ATTRIBUTES.prefix}pt:{product_type_id}", CacheKeys.CAT_ATTRIBUTES.ttl, _fetch)

    async def get_with_options(self, attribute_id: str) -> Attribute | None:
        stmt = select(Attribute).options(joinedload(Attribute.options), joinedload(Attribute.group)).where(Attribute.id == attribute_id)
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def list_search_affecting(self) -> list[Attribute]:
        stmt = (
            select(Attribute)
            .where(Attribute.is_search_affecting == True)  # noqa: E712
            .order_by(Attribute.name_en)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_value_rows_for_product(self, product_id: str) -> list[Any]:
        """Attribute code/name/value rows for a product (joins product_attribute_values)."""
        result = await self.db.execute(
            text(
                """
                SELECT a.code, a.name_en, a.name_ar, a.name_fa,
                       a.value_type, a.input_type, pav.value
                FROM product_attribute_values pav
                JOIN attributes a ON a.id = pav.attribute_id
                WHERE pav.product_id = :pid
                ORDER BY a.code
                """
            ),
            {"pid": product_id},
        )
        return list(result.all())


class AttributeGroupRepository(BaseRepository[AttributeGroup]):
    model = AttributeGroup
    TOUCHES: frozenset[str] = frozenset({"attribute_groups"})

    async def list_all(self) -> list[AttributeGroup]:
        stmt = select(AttributeGroup).order_by(AttributeGroup.sort_order)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_all_dto(self) -> list[dict[str, Any]]:
        """Cached JSON-safe attribute-group rows."""

        async def _fetch() -> list[dict[str, Any]]:
            stmt = select(AttributeGroup).order_by(AttributeGroup.sort_order)
            result = await self.db.execute(stmt)
            return [_group_dto(g) for g in result.scalars().all()]

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, f"{CacheKeys.CAT_ATTRIBUTE_GROUPS.prefix}all", CacheKeys.CAT_ATTRIBUTE_GROUPS.ttl, _fetch)

    async def list_by_product_type_dto(self, product_type_id: str) -> list[dict[str, Any]]:
        """Cached JSON-safe attribute-group rows for a product type."""

        async def _fetch() -> list[dict[str, Any]]:
            stmt = (
                select(AttributeGroup)
                .join(Attribute, Attribute.group_id == AttributeGroup.id)
                .join(ProductTypeAttribute, ProductTypeAttribute.attribute_id == Attribute.id)
                .where(ProductTypeAttribute.product_type_id == product_type_id)
                .distinct()
                .order_by(AttributeGroup.sort_order)
            )
            result = await self.db.execute(stmt)
            return [_group_dto(g) for g in result.scalars().all()]

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, f"{CacheKeys.CAT_ATTRIBUTE_GROUPS.prefix}pt:{product_type_id}", CacheKeys.CAT_ATTRIBUTE_GROUPS.ttl, _fetch)

    async def list_by_product_type(self, product_type_id: str) -> list[AttributeGroup]:
        stmt = (
            select(AttributeGroup)
            .join(Attribute, Attribute.group_id == AttributeGroup.id)
            .join(ProductTypeAttribute, ProductTypeAttribute.attribute_id == Attribute.id)
            .where(ProductTypeAttribute.product_type_id == product_type_id)
            .distinct()
            .order_by(AttributeGroup.sort_order)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class AttributeOptionRepository(BaseRepository[AttributeOption]):
    model = AttributeOption
    TOUCHES: frozenset[str] = frozenset({"attribute_options"})

    async def list_major_by_attribute(self, attribute_id: str, limit: int = 8) -> list[AttributeOption]:
        stmt = (
            select(AttributeOption)
            .where(AttributeOption.attribute_id == attribute_id, AttributeOption.is_major == True)  # noqa: E712
            .order_by(AttributeOption.sort_order)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_major_by_attribute_dto(self, attribute_id: str, limit: int = 8) -> list[dict[str, Any]]:
        """Cached JSON-safe major option rows for an attribute."""

        async def _fetch() -> list[dict[str, Any]]:
            stmt = (
                select(AttributeOption)
                .where(AttributeOption.attribute_id == attribute_id, AttributeOption.is_major == True)  # noqa: E712
                .order_by(AttributeOption.sort_order)
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            return [_option_dto(o) for o in result.scalars().all()]

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, f"{CacheKeys.CAT_ATTRIBUTE_OPTIONS.prefix}major:{attribute_id}:{limit}", CacheKeys.CAT_ATTRIBUTE_OPTIONS.ttl, _fetch)

    async def list_by_attribute_dto(self, attribute_id: str) -> list[dict[str, Any]]:
        """Cached JSON-safe option rows for an attribute (all options)."""

        async def _fetch() -> list[dict[str, Any]]:
            stmt = select(AttributeOption).where(AttributeOption.attribute_id == attribute_id).order_by(AttributeOption.sort_order)
            result = await self.db.execute(stmt)
            return [_option_dto(o) for o in result.scalars().all()]

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, f"{CacheKeys.CAT_ATTRIBUTE_OPTIONS.prefix}all:{attribute_id}", CacheKeys.CAT_ATTRIBUTE_OPTIONS.ttl, _fetch)

    async def get_localized_value(self, option_id: str, lang: str) -> str | None:
        """Display value of an attribute option in the requested language column."""
        val_col = f"value_{_LANG_COLUMNS.get(lang, 'en')}"
        stmt = select(getattr(AttributeOption, val_col)).where(AttributeOption.id == option_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_minimal(self) -> list[tuple[str, str, str]]:
        """All options as (attribute_id, code, id) for scraper reference data."""
        result = await self.db.execute(select(AttributeOption.attribute_id, AttributeOption.code, AttributeOption.id))
        return [(str(row[0]), row[1] or "", str(row[2])) for row in result.fetchall()]

    async def list_color_family_by_attribute(self, attribute_id: str) -> list[tuple[str, str, str, str]]:
        """Options of an attribute as (id, code, value_en, color_family)."""
        result = await self.db.execute(
            select(
                AttributeOption.id,
                AttributeOption.code,
                AttributeOption.value_en,
                AttributeOption.color_family,
            ).where(AttributeOption.attribute_id == attribute_id)
        )
        return [(str(row[0]), row[1] or "", row[2] or "", row[3] or "") for row in result.fetchall()]

    async def max_sort_order(self, attribute_id: str) -> int:
        stmt = select(AttributeOption.sort_order).where(AttributeOption.attribute_id == attribute_id).order_by(AttributeOption.sort_order.desc()).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def fetch_color_data(self, product_id: str) -> tuple[list[str], list[str]]:
        """Collect colors and color families from product attributes AND variants.

        Returns (color_values, color_families): bilingual display names (en + ar,
        aliased, deduped) and coarse semantic buckets for embedding filters.
        """
        option_ids: set[str] = set()

        rows = await self.db.execute(
            text(
                f"""
                SELECT pav.value
                FROM product_attribute_values pav
                JOIN attributes a ON a.id = pav.attribute_id
                WHERE pav.product_id = :pid AND {_COLOR_ATTR_SQL}
                """
            ),
            {"pid": product_id},
        )
        for row in rows:
            option_ids.update(_extract_option_uuids(row[0]))

        rows = await self.db.execute(
            text(
                f"""
                SELECT DISTINCT ao.id
                FROM product_variants pv
                JOIN variant_attribute_options vaoo ON vaoo.variant_id = pv.id
                JOIN attribute_options ao ON ao.id = vaoo.attribute_option_id
                JOIN attributes a ON a.id = ao.attribute_id
                WHERE pv.product_id = :pid
                  AND pv.is_active = true
                  AND {_COLOR_ATTR_SQL}
                """
            ),
            {"pid": product_id},
        )
        for row in rows:
            option_ids.add(row[0])

        colors: list[str] = []
        families: set[str] = set()
        if option_ids:
            opt_rows = await self.db.execute(
                text(
                    """
                    SELECT code, value_en, value_ar, color_family
                    FROM attribute_options
                    WHERE id = ANY(:ids)
                    """
                ),
                {"ids": list(option_ids)},
            )
            for opt in opt_rows:
                code = str(opt.code or "").strip().lower()
                value_en = str(opt.value_en or "").strip()
                if value_en:
                    colors.append(_COLOR_VALUE_ALIAS.get(value_en.strip().lower(), value_en))
                value_ar = str(opt.value_ar or "").strip()
                if value_ar:
                    colors.append(_COLOR_VALUE_ALIAS.get(value_ar.strip().lower(), value_ar))
                family = opt.color_family
                if not family:
                    family = _COLOR_FAMILY_ALIAS.get(code)
                if family:
                    families.add(family)

        return list(dict.fromkeys(colors)), sorted(families)


class ProductTypeRepository(BaseRepository[ProductType]):
    model = ProductType
    TOUCHES: frozenset[str] = frozenset({"product_types"})

    async def get_with_attributes(self, product_type_id: str) -> ProductType | None:
        stmt = (
            select(ProductType)
            .options(
                joinedload(ProductType.product_type_attributes).joinedload(ProductTypeAttribute.attribute).joinedload(Attribute.options),
                joinedload(ProductType.product_type_attributes).joinedload(ProductTypeAttribute.attribute).joinedload(Attribute.group),
            )
            .where(ProductType.id == product_type_id)
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def list_all(self) -> list[ProductType]:
        stmt = select(ProductType).order_by(ProductType.sort_order)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_all_dto(self) -> list[dict[str, Any]]:
        """Cached JSON-safe product-type rows."""

        async def _fetch() -> list[dict[str, Any]]:
            stmt = select(ProductType).order_by(ProductType.sort_order)
            result = await self.db.execute(stmt)
            return [_product_type_dto(pt) for pt in result.scalars().all()]

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, f"{CacheKeys.CAT_PRODUCT_TYPES.prefix}all", CacheKeys.CAT_PRODUCT_TYPES.ttl, _fetch)

    async def list_id_code(self) -> list[tuple[str, str]]:
        """All product types as (id, code) for scraper reference data."""
        result = await self.db.execute(select(ProductType.id, ProductType.code))
        return [(str(row[0]), str(row[1])) for row in result.fetchall()]

    async def get_name(self, product_type_id: str, lang: str) -> str | None:
        name_col = f"name_{_LANG_COLUMNS.get(lang, 'en')}"
        stmt = select(getattr(ProductType, name_col)).where(ProductType.id == product_type_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


class ImageViewTypeRepository(BaseRepository[ProductTypeImageViewType]):
    model = ProductTypeImageViewType
    TOUCHES: frozenset[str] = frozenset({"product_type_image_view_types"})

    async def list_by_product_type(self, product_type_id: str) -> list[ProductTypeImageViewType]:
        stmt = select(ProductTypeImageViewType).where(ProductTypeImageViewType.product_type_id == product_type_id).order_by(ProductTypeImageViewType.sort_order)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_product_type_dto(self, product_type_id: str) -> list[dict[str, Any]]:
        """Cached JSON-safe image-view-type rows for a product type."""

        async def _fetch() -> list[dict[str, Any]]:
            stmt = select(ProductTypeImageViewType).where(ProductTypeImageViewType.product_type_id == product_type_id).order_by(ProductTypeImageViewType.sort_order)
            result = await self.db.execute(stmt)
            return [_image_view_type_dto(ivt) for ivt in result.scalars().all()]

        if self.redis is None:
            return await _fetch()
        return await cache_or_fetch(self.redis, f"{CacheKeys.CAT_IMAGE_VIEW_TYPES.prefix}pt:{product_type_id}", CacheKeys.CAT_IMAGE_VIEW_TYPES.ttl, _fetch)

    async def list_by_code(self, code: str) -> list[tuple[str, str | None]]:
        """All rows matching a code as (id, product_type_id)."""
        result = await self.db.execute(select(ProductTypeImageViewType.id, ProductTypeImageViewType.product_type_id).where(ProductTypeImageViewType.code == code))
        return [(str(row[0]), str(row[1]) if row[1] else None) for row in result.fetchall()]
