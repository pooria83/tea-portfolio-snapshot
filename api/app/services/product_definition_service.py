import uuid
from itertools import product as cartesian_product
from typing import Any

from loguru import logger
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CacheKeys, cache_or_fetch, invalidate_tables
from app.core.error_codes import E
from app.core.exceptions import NotFoundError, ValidationError
from app.models.attribute import Attribute
from app.models.product_attribute_value import ProductAttributeValue
from app.models.product_color_set import ProductColorSet, ProductColorSetValue
from app.models.product_image import ProductImage
from app.models.product_piece import ProductPiece
from app.models.product_size import ProductSize
from app.models.product_variant import ProductVariant
from app.models.store_product import StoreProduct
from app.models.variant_attribute_option import VariantAttributeOption
from app.repositories.catalog import (
    AttributeGroupRepository,
    AttributeOptionRepository,
    AttributeRepository,
    BrandRepository,
    CategoryRepository,
    ImageViewTypeRepository,
    ProductTypeRepository,
    _attribute_dto,
)
from app.repositories.product_definition import ProductImageRepository, ProductVariantRepository, StoreProductRepository
from app.schemas.product_definition import (
    CategoryTreeResponse,
    ProductVariantUpdate,
    StoreProductCreate,
    StoreProductResponse,
    StoreProductUpdate,
)
from app.services.product_definition.attributes import _resolve_attribute_values
from app.services.product_definition.images import _update_product_images
from app.services.product_definition.pieces import (
    _clear_color_set_values,
    _existing_color_set_map,
    _existing_piece_map,
    _resolve_color_set_ref,
    _resolve_piece_ref,
    _upsert_color_sets,
    _upsert_pieces,
    _validate_color_set_refs,
)
from app.services.product_definition.variants import (
    _build_existing_variant_map,
    _create_variant,
    _deduplicate_variant_data,
    _merge_variants,
    _variant_signature,
)
from app.services.storage_service import StorageService

__all__ = [
    "_build_existing_variant_map",
    "_clear_color_set_values",
    "_create_variant",
    "_deduplicate_variant_data",
    "_existing_color_set_map",
    "_existing_piece_map",
    "_merge_variants",
    "_resolve_attribute_values",
    "_resolve_color_set_ref",
    "_resolve_piece_ref",
    "_update_product_images",
    "_upsert_color_sets",
    "_upsert_pieces",
    "_validate_color_set_refs",
    "_variant_signature",
]


async def get_product_types(db: AsyncSession, redis: AsyncRedis | None = None) -> list[dict[str, object]]:
    repo = ProductTypeRepository(db, redis)
    return await repo.list_all_dto()


async def get_product_type_detail(db: AsyncSession, product_type_id: str, redis: AsyncRedis | None = None) -> dict[str, object]:
    repo = ProductTypeRepository(db, redis)

    async def _fetch() -> dict[str, object]:
        product_type = await repo.get_with_attributes(product_type_id)
        if not product_type:
            raise NotFoundError("Product type not found", translation_key=E.PRODUCT_TYPE_NOT_FOUND)
        return {
            "id": product_type.id,
            "code": product_type.code,
            "name_ar": product_type.name_ar,
            "name_en": product_type.name_en,
            "name_fa": product_type.name_fa,
            "icon": product_type.icon,
            "sort_order": product_type.sort_order,
            "categories": [],
            "attributes": [_attribute_dto(pta.attribute) for pta in product_type.product_type_attributes],
        }

    if redis is None:
        return await _fetch()
    return await cache_or_fetch(redis, f"{CacheKeys.CAT_PRODUCT_TYPES.prefix}detail:{product_type_id}", CacheKeys.CAT_PRODUCT_TYPES.ttl, _fetch)


async def get_categories_tree(db: AsyncSession, product_type_id: str | None = None, redis: AsyncRedis | None = None) -> list[CategoryTreeResponse]:
    repo = CategoryRepository(db, redis)
    if product_type_id:
        all_cats = await repo.list_by_product_type_dto(product_type_id)
    else:
        all_cats = await repo.list_all_dto()
    return _build_tree(all_cats)


def _build_tree(categories: list[dict[str, Any]]) -> list[CategoryTreeResponse]:
    cat_map = {str(c["id"]): _cat_to_tree(c) for c in categories}
    roots: list[CategoryTreeResponse] = []
    for c in categories:
        node = cat_map[str(c["id"])]
        parent_id = c.get("parent_id")
        if parent_id and str(parent_id) in cat_map:
            cat_map[str(parent_id)].children.append(node)
        else:
            roots.append(node)
    return roots


def _cat_to_tree(c: dict[str, Any]) -> CategoryTreeResponse:
    return CategoryTreeResponse(
        id=str(c["id"]),
        parent_id=str(c["parent_id"]) if c.get("parent_id") else None,
        product_type_id=str(c["product_type_id"]) if c.get("product_type_id") else None,
        name_ar=str(c["name_ar"]),
        name_en=str(c["name_en"]),
        name_fa=str(c["name_fa"]),
        icon=c.get("icon"),
        sort_order=int(c.get("sort_order") or 0),
        is_active=bool(c.get("is_active", True)),
        children=[],
    )


async def get_product_type_attributes(db: AsyncSession, product_type_id: str, group_id: str | None = None, redis: AsyncRedis | None = None) -> list[dict[str, object]]:
    repo = AttributeRepository(db, redis)
    if group_id:
        return await repo.list_by_group_dto(group_id)

    all_attrs = await repo.list_by_product_type_dto(product_type_id)
    groups = await _get_ordered_groups(db, redis)
    group_map: dict[str, list[dict[str, object]]] = {}
    for attr in all_attrs:
        group_map.setdefault(str(attr["group_id"]), []).append(attr)
    ordered: list[dict[str, object]] = []
    for g in groups:
        ordered.extend(group_map.get(str(g["id"]), []))
    return ordered


async def get_attribute_groups(db: AsyncSession, product_type_id: str | None = None, redis: AsyncRedis | None = None) -> list[dict[str, object]]:
    repo = AttributeGroupRepository(db, redis)
    if product_type_id:
        return await repo.list_by_product_type_dto(product_type_id)
    return await repo.list_all_dto()


async def _get_ordered_groups(db: AsyncSession, redis: AsyncRedis | None = None) -> list[dict[str, object]]:
    return await get_attribute_groups(db, redis=redis)


async def get_attribute_options(db: AsyncSession, attribute_id: str, redis: AsyncRedis | None = None) -> list[dict[str, object]]:
    repo = AttributeRepository(db, redis)
    attr = await repo.get(attribute_id)
    if not attr:
        raise NotFoundError("Attribute not found", translation_key=E.ATTRIBUTE_NOT_FOUND)
    return await AttributeOptionRepository(db, redis).list_by_attribute_dto(attribute_id)


async def get_image_view_types(db: AsyncSession, product_type_id: str, redis: AsyncRedis | None = None) -> list[dict[str, object]]:
    repo = ImageViewTypeRepository(db, redis)
    return await repo.list_by_product_type_dto(product_type_id)


async def create_store_product(
    db: AsyncSession,
    store_id: str,
    data: StoreProductCreate,
    product_storage: StorageService | None = None,
    temp_storage: StorageService | None = None,
    redis: AsyncRedis | None = None,
) -> StoreProduct:
    has_variants = len(data.variants) > 0
    product = StoreProduct(
        id=str(uuid.uuid4()),
        store_id=store_id,
        product_type_id=data.product_type_id,
        category_id=data.category_id,
        name_ar=data.name_ar,
        name_en=data.name_en,
        name_fa=data.name_fa,
        short_description_ar=data.short_description_ar,
        short_description_en=data.short_description_en,
        short_description_fa=data.short_description_fa,
        long_description_ar=data.long_description_ar,
        long_description_en=data.long_description_en,
        long_description_fa=data.long_description_fa,
        brand=data.brand,
        sku=data.sku,
        barcode=data.barcode,
        status=data.status,
        has_variants=has_variants,
        is_multi_piece=data.is_multi_piece,
        price=data.price,
        original_price=data.original_price,
        sale_price=data.sale_price,
        currency=data.currency,
        quantity=data.quantity,
        low_stock_threshold=data.low_stock_threshold,
        weight=data.weight,
        weight_unit=data.weight_unit,
        collection=data.collection,
        collection_ar=data.collection_ar,
        country_of_origin=data.country_of_origin,
        model_height=data.model_height,
        model_wears_size=data.model_wears_size,
        video_url=data.video_url,
        source_url=data.source_url,
    )
    repo = StoreProductRepository(db)
    product = await repo.add(product)

    for size_data in data.sizes:
        size = ProductSize(
            id=str(uuid.uuid4()),
            product_id=product.id,
            size_label=size_data.size_label,
            size_system=size_data.size_system,
            stock=size_data.stock,
            sort_order=size_data.sort_order,
        )
        db.add(size)

    piece_order_map: dict[int, str] = {}
    for i, piece_data in enumerate(data.pieces):
        piece = ProductPiece(
            id=str(uuid.uuid4()),
            product_id=product.id,
            name_en=piece_data.name_en,
            name_ar=piece_data.name_ar,
            sort_order=i,
        )
        db.add(piece)
        piece_order_map[i] = piece.id

    color_set_id_map: dict[str, str] = {}
    if data.color_sets:
        await db.flush()
        for cs_data in data.color_sets:
            cs = ProductColorSet(
                id=str(uuid.uuid4()),
                product_id=product.id,
                sort_order=cs_data.sort_order,
            )
            db.add(cs)
            await db.flush()
            color_set_id_map[str(cs_data.sort_order)] = cs.id
            for val_data in cs_data.values:
                try:
                    pos = int(val_data.piece_id)
                    resolved_piece_id = piece_order_map.get(pos, val_data.piece_id)
                except (ValueError, TypeError):
                    resolved_piece_id = val_data.piece_id
                db.add(
                    ProductColorSetValue(
                        id=str(uuid.uuid4()),
                        color_set_id=cs.id,
                        piece_id=resolved_piece_id,
                        color_option_id=val_data.color_option_id,
                    )
                )

    for av_data in await _resolve_attribute_values(db, data, product.id):
        av = ProductAttributeValue(
            id=str(uuid.uuid4()),
            product_id=product.id,
            attribute_id=av_data.attribute_id,
            value=av_data.value,
        )
        db.add(av)

    created_variants: list[ProductVariant] = []
    for variant_data in data.variants:
        if variant_data.color_set_id and variant_data.color_set_id in color_set_id_map:
            variant_data.color_set_id = color_set_id_map[variant_data.color_set_id]
        variant = await _create_variant(db, product.id, variant_data)
        created_variants.append(variant)

    created_images: list[ProductImage] = []
    for img_data in data.images:
        img_url = StorageService.strip_domain(img_data.image_url)
        if img_data.variant_signature:
            sig_set = set(img_data.variant_signature)
            matched = False
            for v_data, v in zip(data.variants, created_variants, strict=False):
                if sig_set and sig_set.issubset(set(v_data.attribute_option_ids)):
                    image = ProductImage(
                        id=str(uuid.uuid4()),
                        product_id=product.id,
                        variant_id=v.id,
                        view_type_id=img_data.view_type_id,
                        image_url=img_url,
                        alt_text_ar=img_data.alt_text_ar,
                        alt_text_en=img_data.alt_text_en,
                        alt_text_fa=img_data.alt_text_fa,
                        sort_order=img_data.sort_order,
                    )
                    db.add(image)
                    created_images.append(image)
                    matched = True
                    break
            if matched:
                continue
        elif img_data.variant_index is not None and img_data.variant_index < len(created_variants):
            image = ProductImage(
                id=str(uuid.uuid4()),
                product_id=product.id,
                variant_id=created_variants[img_data.variant_index].id,
                view_type_id=img_data.view_type_id,
                image_url=img_url,
                alt_text_ar=img_data.alt_text_ar,
                alt_text_en=img_data.alt_text_en,
                alt_text_fa=img_data.alt_text_fa,
                sort_order=img_data.sort_order,
            )
            db.add(image)
            created_images.append(image)
            continue
        image = ProductImage(
            id=str(uuid.uuid4()),
            product_id=product.id,
            variant_id=None,
            view_type_id=img_data.view_type_id,
            image_url=img_url,
            alt_text_ar=img_data.alt_text_ar,
            alt_text_en=img_data.alt_text_en,
            alt_text_fa=img_data.alt_text_fa,
            sort_order=img_data.sort_order,
        )
        db.add(image)
        created_images.append(image)

    await db.flush()

    if product_storage is not None and temp_storage is not None:
        for image in created_images:
            if not image.image_url:
                continue
            file_name = image.image_url.rsplit("/", 1)[-1]
            dest = f"products/{store_id}/{product.id}/{file_name}"
            try:
                await product_storage.cross_bucket_move(temp_storage, file_name, dest)
                image.image_url = product_storage.get_storage_path(dest)
            except Exception:
                logger.exception("Failed to move product image {}", file_name)
        await db.flush()

    if redis is not None:
        await invalidate_tables(redis, {"store_products", "product_images", "product_variants", "product_sizes", "product_pieces"})
    return product


async def update_store_product(db: AsyncSession, product_id: str, store_id: str, data: StoreProductUpdate, redis: AsyncRedis | None = None) -> StoreProduct:
    repo = StoreProductRepository(db)
    product = await repo.get(product_id)
    if not product or product.store_id != store_id:
        raise NotFoundError("Product not found", translation_key=E.PRODUCT_NOT_FOUND)

    update_data = data.model_dump(exclude_unset=True, exclude={"sizes", "attribute_values", "variants", "images", "pieces", "color_sets"})
    for field, value in update_data.items():
        setattr(product, field, value)

    if data.sizes is not None:
        await repo.delete_sizes(product_id)
        for size_data in data.sizes:
            db.add(ProductSize(id=str(uuid.uuid4()), product_id=product.id, size_label=size_data.size_label, size_system=size_data.size_system, stock=size_data.stock, sort_order=size_data.sort_order))

    if data.pieces is not None:
        piece_by_order = await _upsert_pieces(db, product.id, data.pieces)
    else:
        piece_by_order = await _existing_piece_map(db, product.id)

    if data.color_sets is not None:
        await _clear_color_set_values(db, product.id)
        await _validate_color_set_refs(db, data.color_sets, piece_by_order)
        color_set_by_order = await _upsert_color_sets(db, product.id, data.color_sets)
    else:
        color_set_by_order = await _existing_color_set_map(db, product.id)

    if data.attribute_values is not None:
        await repo.delete_attribute_values(product_id)
        resolved = await _resolve_attribute_values(db, data, product.id)
        for av in resolved:
            db.add(av)

    if data.variants is not None:
        for variant_data in data.variants:
            if variant_data.color_set_id:
                resolved_cs = _resolve_color_set_ref(variant_data.color_set_id, color_set_by_order)
                if resolved_cs is None:
                    raise ValidationError("Invalid color set reference", translation_key=E.VALIDATION_ERROR)
                variant_data.color_set_id = resolved_cs
        await _merge_variants(db, product.id, data.variants)
        product.has_variants = len(data.variants) > 0

    if data.images is not None:
        await _update_product_images(db, product_id, data.images, product)

    await db.flush()
    if redis is not None:
        await invalidate_tables(redis, {"store_products", "product_images", "product_variants", "product_sizes", "product_pieces"})
    return product


async def delete_store_product(db: AsyncSession, product_id: str, store_id: str, redis: AsyncRedis | None = None) -> None:
    repo = StoreProductRepository(db)
    product = await repo.get(product_id)
    if not product or product.store_id != store_id:
        raise NotFoundError("Product not found", translation_key=E.PRODUCT_NOT_FOUND)
    await repo.delete(product)
    if redis is not None:
        await invalidate_tables(redis, {"store_products", "product_images", "product_variants", "product_sizes", "product_pieces"})


async def get_variant_defining_attributes(db: AsyncSession, product_type_id: str) -> list[Attribute]:
    """Return attributes marked as variant-defining for a given product type."""
    repo = AttributeRepository(db)
    attrs = await repo.list_by_product_type(product_type_id)
    return [a for a in attrs if a.is_variant_defining]


async def generate_variant_combinations(db: AsyncSession, product_type_id: str, selected_option_ids: dict[str, list[str]]) -> list[dict[str, object]]:
    """
    Generate all cartesian product combinations from selected option IDs
    grouped by variant-defining attribute IDs.

    Returns list of dicts like::
        {"attribute_option_ids": ["opt1", "opt2"], "label": "Black | S"}
    """
    variant_defining = await get_variant_defining_attributes(db, product_type_id)
    option_groups: list[list[str]] = []
    attr_labels: list[str] = []

    for attr in variant_defining:
        opts = selected_option_ids.get(attr.id, [])
        if opts:
            option_groups.append(opts)
            attr_labels.append(attr.code)

    if not option_groups:
        return []

    result_list: list[dict[str, object]] = []
    for combo in cartesian_product(*option_groups):
        label = " | ".join(str(o) for o in combo)
        result_list.append(
            {
                "attribute_option_ids": list(combo),
                "label": label,
            }
        )

    return result_list


async def get_store_product(db: AsyncSession, product_id: str, store_id: str) -> StoreProduct:
    repo = StoreProductRepository(db)
    product = await repo.get_with_all(product_id)
    if not product or product.store_id != store_id:
        raise NotFoundError("Product not found", translation_key=E.PRODUCT_NOT_FOUND)
    return product


def _resolve_url(url: str) -> str:
    if url and not url.startswith("http"):
        from app.core.config import settings

        return f"{settings.minio_public_url}/{url}"
    return url


def _store_product_to_response(product: StoreProduct) -> StoreProductResponse:
    resp = StoreProductResponse.model_validate(product)
    if product.store:
        resp.store_name = product.store.name
    if product.brand_obj:
        resp.brand_name = product.brand_obj.name_en
    for img in resp.images:
        img.image_url = _resolve_url(img.image_url)
    return resp


async def get_store_product_response(db: AsyncSession, redis: AsyncRedis | None, product_id: str, store_id: str) -> StoreProductResponse:
    """Public product detail as a cached, JSON-safe response (TTL 300s).

    The DB-backed :func:`get_store_product` remains for owner flows that need
    fresh ORM rows; this variant serves the hot public product view.
    """

    async def _fetch() -> dict[str, Any]:
        product = await get_store_product(db, product_id, store_id)
        return _store_product_to_response(product).model_dump(mode="json")

    if redis is None:
        product = await get_store_product(db, product_id, store_id)
        return _store_product_to_response(product)
    dto = await cache_or_fetch(redis, CacheKeys.product_detail(store_id, product_id), CacheKeys.PRODUCT_DETAIL.ttl, _fetch)
    return StoreProductResponse.model_validate(dto)


async def list_store_products(db: AsyncSession, store_id: str, skip: int = 0, limit: int = 20) -> tuple[list[StoreProduct], int]:
    repo = StoreProductRepository(db)
    items = await repo.list_by_store(store_id, skip=skip, limit=limit)
    total = await repo.count_by_store(store_id)
    return items, total


async def search_store_products(db: AsyncSession, store_id: str, query: str, skip: int = 0, limit: int = 20) -> tuple[list[StoreProduct], int]:
    repo = StoreProductRepository(db)
    return await repo.search_by_name(query, store_ids=[store_id], skip=skip, limit=limit)


async def list_my_products(db: AsyncSession, store_ids: list[str], skip: int = 0, limit: int = 20, store_id: str | None = None) -> tuple[list[StoreProduct], int]:
    if not store_ids:
        return [], 0
    repo = StoreProductRepository(db)
    if store_id:
        if store_id not in store_ids:
            return [], 0
        store_ids = [store_id]
    items = await repo.list_by_store_ids(store_ids, skip=skip, limit=limit)
    total = await repo.count_by_store_ids(store_ids)
    return items, total


async def count_my_products(db: AsyncSession, store_ids: list[str], status: str | None = None) -> int:
    if not store_ids:
        return 0
    repo = StoreProductRepository(db)
    return await repo.count_by_store_ids(store_ids, status=status)


async def get_my_products_stats(db: AsyncSession, redis: AsyncRedis | None, store_ids: list[str]) -> dict[str, int]:
    """Cached {total, active} product counts for the seller dashboard (TTL 60s)."""

    async def _fetch() -> dict[str, int]:
        total = await count_my_products(db, store_ids)
        active = await count_my_products(db, store_ids, status="active")
        return {"total": total, "active": active}

    if redis is None:
        return await _fetch()
    signature = ",".join(sorted(store_ids)) if store_ids else "none"
    return await cache_or_fetch(redis, CacheKeys.store_stats(signature), CacheKeys.STORE_STATS.ttl, _fetch)


async def random_products(db: AsyncSession, limit: int = 20) -> list[StoreProduct]:
    repo = StoreProductRepository(db)
    return await repo.random(limit=limit)


async def search_my_products(db: AsyncSession, store_ids: list[str], query: str, skip: int = 0, limit: int = 20, store_id: str | None = None) -> tuple[list[StoreProduct], int]:
    if not store_ids:
        return [], 0
    if store_id:
        if store_id not in store_ids:
            return [], 0
        store_ids = [store_id]
    repo = StoreProductRepository(db)
    return await repo.search_by_name(query, store_ids=store_ids, skip=skip, limit=limit)


def _resolve_light_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve relative image URLs to full MinIO URLs for light list items."""
    for item in items:
        url = item.get("image_url")
        if url:
            item["image_url"] = _resolve_url(url)
    return items


async def list_store_products_light(db: AsyncSession, store_id: str, skip: int = 0, limit: int = 20) -> tuple[list[dict[str, Any]], int]:
    repo = StoreProductRepository(db)
    items = await repo.list_by_store_ids_light([store_id], skip=skip, limit=limit)
    total = await repo.count_by_store(store_id)
    return _resolve_light_items(items), total


async def search_store_products_light(db: AsyncSession, store_id: str, query: str, skip: int = 0, limit: int = 20) -> tuple[list[dict[str, Any]], int]:
    repo = StoreProductRepository(db)
    items, total = await repo.search_by_name_light(query, store_ids=[store_id], skip=skip, limit=limit)
    return _resolve_light_items(items), total


async def list_my_products_light(db: AsyncSession, store_ids: list[str], skip: int = 0, limit: int = 20, store_id: str | None = None) -> tuple[list[dict[str, Any]], int]:
    if not store_ids:
        return [], 0
    if store_id:
        if store_id not in store_ids:
            return [], 0
        store_ids = [store_id]
    repo = StoreProductRepository(db)
    items = await repo.list_by_store_ids_light(store_ids, skip=skip, limit=limit)
    total = await repo.count_by_store_ids(store_ids)
    return _resolve_light_items(items), total


async def search_my_products_light(db: AsyncSession, store_ids: list[str], query: str, skip: int = 0, limit: int = 20, store_id: str | None = None) -> tuple[list[dict[str, Any]], int]:
    if not store_ids:
        return [], 0
    if store_id:
        if store_id not in store_ids:
            return [], 0
        store_ids = [store_id]
    repo = StoreProductRepository(db)
    items, total = await repo.search_by_name_light(query, store_ids=store_ids, skip=skip, limit=limit)
    return _resolve_light_items(items), total


async def random_products_light(db: AsyncSession, redis: AsyncRedis | None, limit: int = 20) -> list[dict[str, Any]]:
    """Random product cards — cached for 1 hour (public, non user-scoped)."""

    async def _fetch() -> list[dict[str, Any]]:
        repo = StoreProductRepository(db)
        return _resolve_light_items(await repo.random_light(limit=limit))

    if redis is None:
        return await _fetch()
    return await cache_or_fetch(redis, CacheKeys.random(limit), CacheKeys.RANDOM.ttl, _fetch)


async def add_product_image(
    db: AsyncSession,
    product_id: str,
    store_id: str,
    image_url: str,
    view_type_id: str | None = None,
    variant_id: str | None = None,
    redis: AsyncRedis | None = None,
) -> ProductImage:
    from app.services.storage_service import StorageService

    repo = StoreProductRepository(db)
    product = await repo.get(product_id)
    if not product or product.store_id != store_id:
        raise NotFoundError("Product not found", translation_key=E.PRODUCT_NOT_FOUND)
    total_images: int = len(product.images) if hasattr(product, "images") else 0
    image = ProductImage(
        id=str(uuid.uuid4()),
        product_id=product_id,
        variant_id=variant_id,
        view_type_id=view_type_id,
        image_url=StorageService.strip_domain(image_url),
        sort_order=total_images,
    )
    db.add(image)
    await db.flush()
    if redis is not None:
        await invalidate_tables(redis, {"product_images", "store_products"})
    return image


async def update_product_image(db: AsyncSession, image_id: str, store_id: str, redis: AsyncRedis | None = None, **kwargs: str | int | None) -> ProductImage:
    image = await ProductImageRepository(db).get_by_store(image_id, store_id)
    if not image:
        raise NotFoundError("Image not found", translation_key=E.IMAGE_NOT_FOUND)
    for field, value in kwargs.items():
        if value is not None and hasattr(image, field):
            setattr(image, field, value)
    await db.flush()
    if redis is not None:
        await invalidate_tables(redis, {"product_images", "store_products"})
    return image


async def delete_product_image(db: AsyncSession, image_id: str, store_id: str, redis: AsyncRedis | None = None) -> None:
    image = await ProductImageRepository(db).get_by_store(image_id, store_id)
    if not image:
        raise NotFoundError("Image not found", translation_key=E.IMAGE_NOT_FOUND)
    await db.delete(image)
    await db.flush()
    if redis is not None:
        await invalidate_tables(redis, {"product_images", "store_products"})


async def reorder_product_images(db: AsyncSession, store_id: str, ordered_ids: list[str], redis: AsyncRedis | None = None) -> None:
    images = await ProductImageRepository(db).list_by_store_and_ids(store_id, ordered_ids)
    image_map = {img.id: img for img in images}
    for idx, img_id in enumerate(ordered_ids):
        if img_id in image_map:
            image_map[img_id].sort_order = idx
    await db.flush()
    if redis is not None:
        await invalidate_tables(redis, {"product_images", "store_products"})


async def get_brands(db: AsyncSession, redis: AsyncRedis | None = None) -> list[dict[str, object]]:
    return await BrandRepository(db, redis).list_all_dto()


async def update_product_variant(
    db: AsyncSession,
    product_id: str,
    store_id: str,
    variant_id: str,
    data: ProductVariantUpdate,
    redis: AsyncRedis | None = None,
) -> ProductVariant:
    repo = StoreProductRepository(db)
    product = await repo.get(product_id)
    if not product or product.store_id != store_id:
        raise NotFoundError("Product not found", translation_key=E.PRODUCT_NOT_FOUND)

    variant = await ProductVariantRepository(db).get_by_product(variant_id, product_id)
    if not variant:
        raise NotFoundError("Variant not found", translation_key=E.VARIANT_NOT_FOUND)

    update_data = data.model_dump(exclude_unset=True, exclude={"attribute_option_ids"})
    will_be_active = update_data.get("is_active", variant.is_active)
    will_have_price = update_data.get("price", variant.price)
    if will_be_active and will_have_price is None:
        raise ValidationError("Price is required for active variants", translation_key=E.PRICE_REQUIRED)
    will_have_sku = update_data.get("sku", variant.sku)
    if will_be_active and (not will_have_sku or not will_have_sku.strip()):
        raise ValidationError("SKU is required for active variants", translation_key=E.SKU_REQUIRED)

    for field, value in update_data.items():
        setattr(variant, field, value)

    variant_repo = ProductVariantRepository(db)
    if data.attribute_option_ids is not None:
        await variant_repo.delete_attribute_links(variant_id)

        for option_id in data.attribute_option_ids:
            link = VariantAttributeOption(
                variant_id=variant.id,
                attribute_option_id=option_id,
            )
            db.add(link)

    await db.flush()

    await db.refresh(variant)
    if redis is not None:
        await invalidate_tables(redis, {"product_variants", "store_products"})
    return await variant_repo.get_with_attribute_options(variant_id)


async def delete_product_variant(db: AsyncSession, product_id: str, store_id: str, variant_id: str, redis: AsyncRedis | None = None) -> None:
    repo = StoreProductRepository(db)
    product = await repo.get(product_id)
    if not product or product.store_id != store_id:
        raise NotFoundError("Product not found", translation_key=E.PRODUCT_NOT_FOUND)

    variant = await ProductVariantRepository(db).get_by_product(variant_id, product_id)
    if not variant:
        raise NotFoundError("Variant not found", translation_key=E.VARIANT_NOT_FOUND)
    await db.delete(variant)
    await db.flush()
    if redis is not None:
        await invalidate_tables(redis, {"product_variants", "store_products"})
