from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import PaginationParams, RateLimit, get_authenticated_user
from app.core.error_codes import E
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.core.redis import get_redis
from app.core.response import APIResponse, paginated, success
from app.models.ai_description_version import AIDescriptionVersion
from app.models.category import Category
from app.models.prompt_template import PromptTemplate
from app.models.store import Store
from app.models.store_product import StoreProduct
from app.models.user import User
from app.schemas.product_definition import (
    AIDescriptionVersionResponse,
    AttributeGroupResponse,
    AttributeOptionResponse,
    AttributeResponse,
    BrandResponse,
    CategoryTreeResponse,
    GenerateDescriptionResponse,
    GenerateDescriptionsRequest,
    ImageViewTypeResponse,
    ProductImageCreate,
    ProductImageResponse,
    ProductImageUpdate,
    ProductTypeDetailResponse,
    ProductTypeResponse,
    ProductVariantResponse,
    ProductVariantUpdate,
    StoreProductCreate,
    StoreProductListItem,
    StoreProductResponse,
    StoreProductUpdate,
)
from app.services import product_definition_service, prompt_defaults
from app.services.product_definition_service import _store_product_to_response

UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _is_uuid(value: str) -> bool:
    return bool(UUID_PATTERN.match(value))


public_router = APIRouter(prefix="/products", tags=["product-definition"])
store_router = APIRouter(prefix="/stores/{store_id}/products", tags=["product-definition"])


def _attr_to_response(attr: dict[str, Any]) -> AttributeResponse:
    return AttributeResponse.model_validate(attr)


async def _verify_store_owner(db: AsyncSession, store_id: str, user_id: str) -> Store:
    result = await db.execute(select(Store).where(Store.id == store_id, Store.owner_id == user_id, Store.is_active == True))  # noqa: E712
    store = result.scalar_one_or_none()
    if not store:
        raise NotFoundError("Store not found", translation_key=E.STORE_NOT_FOUND)
    return store


@public_router.get("/types", response_model=APIResponse[list[ProductTypeResponse]])
async def list_product_types(db: AsyncSession = Depends(get_db), redis: AsyncRedis = Depends(get_redis)) -> APIResponse[list[ProductTypeResponse]]:
    types = await product_definition_service.get_product_types(db, redis)
    return success([ProductTypeResponse.model_validate(t) for t in types])


@public_router.get("/types/{product_type_id}", response_model=APIResponse[ProductTypeDetailResponse])
async def get_product_type_detail(
    product_type_id: str,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[ProductTypeDetailResponse]:
    pt = await product_definition_service.get_product_type_detail(db, product_type_id, redis)
    return success(ProductTypeDetailResponse.model_validate(pt))


@public_router.get("/categories", response_model=APIResponse[list[CategoryTreeResponse]])
async def list_categories(
    product_type_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[list[CategoryTreeResponse]]:
    cats = await product_definition_service.get_categories_tree(db, product_type_id, redis)
    return success(cats)


@public_router.get("/attribute-groups", response_model=APIResponse[list[AttributeGroupResponse]])
async def list_attribute_groups(
    product_type_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[list[AttributeGroupResponse]]:
    groups = await product_definition_service.get_attribute_groups(db, product_type_id, redis)
    return success([AttributeGroupResponse.model_validate(g) for g in groups])


@public_router.get("/attributes", response_model=APIResponse[list[AttributeResponse]])
async def list_attributes(
    product_type_id: str = Query(...),
    group_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[list[AttributeResponse]]:
    attrs = await product_definition_service.get_product_type_attributes(db, product_type_id, group_id, redis)
    return success([_attr_to_response(a) for a in attrs])


@public_router.get("/attributes/{attribute_id}/options", response_model=APIResponse[list[AttributeOptionResponse]])
async def list_attribute_options(
    attribute_id: str,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[list[AttributeOptionResponse]]:
    options = await product_definition_service.get_attribute_options(db, attribute_id, redis)
    return success([AttributeOptionResponse.model_validate(o) for o in options])


@public_router.get("/image-view-types", response_model=APIResponse[list[ImageViewTypeResponse]])
async def list_image_view_types(
    product_type_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[list[ImageViewTypeResponse]]:
    types = await product_definition_service.get_image_view_types(db, product_type_id, redis)
    return success([ImageViewTypeResponse.model_validate(t) for t in types])


@public_router.get("/brands", response_model=APIResponse[list[BrandResponse]])
async def list_brands(
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[list[BrandResponse]]:
    brands = await product_definition_service.get_brands(db, redis)
    return success([BrandResponse.model_validate(b) for b in brands])


@store_router.post("", response_model=APIResponse[StoreProductResponse], status_code=201)
async def create_product(
    store_id: str,
    data: StoreProductCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
    current_user: User = Depends(get_authenticated_user),
) -> APIResponse[StoreProductResponse]:
    await _verify_store_owner(db, store_id, current_user.id)
    product_storage = getattr(request.app.state, "storage", None)
    temp_storage = getattr(request.app.state, "temp_storage", None)
    product = await product_definition_service.create_store_product(db, store_id, data, product_storage=product_storage, temp_storage=temp_storage, redis=redis)
    product = await product_definition_service.get_store_product(db, product.id, store_id)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = product.id
        activity["message"] = f"user {current_user.id} create product {product.id} {product.name_en} in store {store_id}"
    return success(_store_product_to_response(product))


@store_router.get("", response_model=APIResponse[list[StoreProductListItem]])
async def list_products(
    store_id: str,
    pagination: PaginationParams = Depends(),
    q: str | None = Query(None, min_length=1, description="Search by product name (English or Arabic)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> APIResponse[list[StoreProductListItem]]:
    await _verify_store_owner(db, store_id, current_user.id)
    if q:
        products, total = await product_definition_service.search_store_products_light(db, store_id, q, skip=pagination.skip, limit=pagination.limit)
    else:
        products, total = await product_definition_service.list_store_products_light(db, store_id, skip=pagination.skip, limit=pagination.limit)
    return paginated(
        items=[StoreProductListItem.model_validate(p) for p in products],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@store_router.get(
    "/{product_id}",
    response_model=APIResponse[StoreProductResponse],
    dependencies=[Depends(RateLimit(max_requests=120, window_seconds=60))],
)
async def get_product(
    store_id: str,
    product_id: str,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[StoreProductResponse]:
    resp = await product_definition_service.get_store_product_response(db, redis, product_id, store_id)
    return success(resp)


@store_router.put("/{product_id}", response_model=APIResponse[StoreProductResponse])
async def update_product(
    store_id: str,
    product_id: str,
    data: StoreProductUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
    current_user: User = Depends(get_authenticated_user),
) -> APIResponse[StoreProductResponse]:
    await _verify_store_owner(db, store_id, current_user.id)
    product = await product_definition_service.update_store_product(db, product_id, store_id, data, redis=redis)
    product = await product_definition_service.get_store_product(db, product.id, store_id)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = product.id
        activity["message"] = f"user {current_user.id} update product {product.id} {product.name_en} in store {store_id}"
    return success(_store_product_to_response(product))


@store_router.delete("/{product_id}", response_model=APIResponse[None])
async def delete_product(
    store_id: str,
    product_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
    current_user: User = Depends(get_authenticated_user),
) -> APIResponse[None]:
    await _verify_store_owner(db, store_id, current_user.id)
    await product_definition_service.delete_store_product(db, product_id, store_id, redis=redis)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = product_id
        activity["message"] = f"user {current_user.id} delete product {product_id} from store {store_id}"
    return success(None)


@store_router.put("/images/{image_id}", response_model=APIResponse[None])
async def update_image(
    store_id: str,
    image_id: str,
    data: ProductImageUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
    current_user: User = Depends(get_authenticated_user),
) -> APIResponse[None]:
    await _verify_store_owner(db, store_id, current_user.id)
    kwargs = data.model_dump(exclude_unset=True)
    await product_definition_service.update_product_image(db, image_id, store_id, redis=redis, **kwargs)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = image_id
        activity["message"] = f"user {current_user.id} update image {image_id} in store {store_id}"
    return success(None)


@store_router.delete("/images/{image_id}", response_model=APIResponse[None])
async def delete_image(
    store_id: str,
    image_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
    current_user: User = Depends(get_authenticated_user),
) -> APIResponse[None]:
    await _verify_store_owner(db, store_id, current_user.id)
    await product_definition_service.delete_product_image(db, image_id, store_id, redis=redis)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = image_id
        activity["message"] = f"user {current_user.id} delete image {image_id} from store {store_id}"
    return success(None)


@store_router.post("/{product_id}/images", response_model=APIResponse[ProductImageResponse], status_code=201)
async def create_image(
    store_id: str,
    product_id: str,
    data: ProductImageCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
    current_user: User = Depends(get_authenticated_user),
) -> APIResponse[ProductImageResponse]:
    await _verify_store_owner(db, store_id, current_user.id)
    image = await product_definition_service.add_product_image(
        db,
        product_id,
        store_id,
        data.image_url,
        view_type_id=data.view_type_id,
        variant_id=data.variant_id,
        redis=redis,
    )
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = image.id
        activity["message"] = f"user {current_user.id} create image {image.id} for product {product_id} in store {store_id}"
    return success(ProductImageResponse.model_validate(image))


@store_router.post("/images/reorder", response_model=APIResponse[None])
async def reorder_images(
    store_id: str,
    ordered_ids: list[str],
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
    current_user: User = Depends(get_authenticated_user),
) -> APIResponse[None]:
    await _verify_store_owner(db, store_id, current_user.id)
    await product_definition_service.reorder_product_images(db, store_id, ordered_ids, redis=redis)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = store_id
        activity["action"] = "REORDER_IMAGES"
        activity["message"] = f"user {current_user.id} reorder images in store {store_id}"
    return success(None)


@public_router.post("/generate-variant-combinations", response_model=APIResponse[list[dict[str, object]]])
async def generate_variant_combinations(
    product_type_id: str,
    selected_option_ids: dict[str, list[str]],
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[dict[str, object]]]:
    combinations = await product_definition_service.generate_variant_combinations(db, product_type_id, selected_option_ids)
    return success(combinations)


@store_router.get("/{product_id}/variants", response_model=APIResponse[list[ProductVariantResponse]])
async def list_variants(
    store_id: str,
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> APIResponse[list[ProductVariantResponse]]:
    await _verify_store_owner(db, store_id, current_user.id)
    product = await product_definition_service.get_store_product(db, product_id, store_id)
    return success([ProductVariantResponse.model_validate(v) for v in product.variants])


@store_router.patch("/{product_id}/variants/{variant_id}", response_model=APIResponse[ProductVariantResponse])
async def update_variant(
    store_id: str,
    product_id: str,
    variant_id: str,
    data: ProductVariantUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
    current_user: User = Depends(get_authenticated_user),
) -> APIResponse[ProductVariantResponse]:
    await _verify_store_owner(db, store_id, current_user.id)
    variant = await product_definition_service.update_product_variant(db, product_id, store_id, variant_id, data, redis=redis)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = variant_id
        activity["message"] = f"user {current_user.id} update variant {variant_id} for product {product_id} in store {store_id}"
    return success(ProductVariantResponse.model_validate(variant))


@store_router.delete("/{product_id}/variants/{variant_id}", response_model=APIResponse[None])
async def delete_variant(
    store_id: str,
    product_id: str,
    variant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
    current_user: User = Depends(get_authenticated_user),
) -> APIResponse[None]:
    await _verify_store_owner(db, store_id, current_user.id)
    await product_definition_service.delete_product_variant(db, product_id, store_id, variant_id, redis=redis)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = variant_id
        activity["message"] = f"user {current_user.id} delete variant {variant_id} for product {product_id} from store {store_id}"
    return success(None)


def _resolve_product_attributes(product: StoreProduct) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for pav in product.attribute_values or []:
        if not pav.value:
            continue
        attr_name = pav.attribute.name_en if pav.attribute else pav.value or ""
        raw = pav.value
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                    values = _resolve_object_array(parsed, pav.attribute.options if pav.attribute else [])
                    result.append({"name": attr_name, "value": "; ".join(values)})
                elif isinstance(parsed, list):
                    uuids = set(parsed)
                    resolved = [o.value_en or o.code or "" for o in (pav.attribute.options if pav.attribute else []) if str(o.id) in uuids]
                    result.append({"name": attr_name, "value": ", ".join(resolved) if resolved else raw})
                else:
                    result.append({"name": attr_name, "value": raw})
            except (json.JSONDecodeError, TypeError):
                result.append({"name": attr_name, "value": raw})
        else:
            matched = next((o.value_en or o.code for o in (pav.attribute.options if pav.attribute else []) if str(o.id) == raw), None)
            result.append({"name": attr_name, "value": matched or raw})
    return result


def _resolve_object_array(parsed: list[dict[str, object]], options: list[Any]) -> list[str]:
    values: list[str] = []
    for item in parsed:
        parts: list[str] = []
        for key, val in item.items():
            if isinstance(val, str) and _is_uuid(val):
                matched = next(
                    (getattr(o, "value_en", None) or getattr(o, "code", None) or "" for o in options if str(getattr(o, "id", "")) == val),
                    None,
                )
                parts.append(f"{key}: {matched or val}")
            else:
                parts.append(f"{key}: {val}")
        values.append(", ".join(parts))
    return values


@store_router.post("/{product_id}/generate-descriptions", response_model=APIResponse[GenerateDescriptionResponse])
async def generate_product_descriptions(
    store_id: str,
    product_id: str,
    http_request: Request,
    body: GenerateDescriptionsRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> APIResponse[GenerateDescriptionResponse]:
    await _verify_store_owner(db, store_id, current_user.id)
    product = await product_definition_service.get_store_product(db, product_id, store_id)

    attributes = _resolve_product_attributes(product)

    category_name: str | None = None
    if product.category_id:
        cat_result = await db.execute(select(Category.name_en).where(Category.id == product.category_id))
        category_name = cat_result.scalar_one_or_none()

    image_alt_texts: list[str] = []
    for img in product.images or []:
        alt = img.alt_text_en or img.alt_text_ar
        if alt:
            image_alt_texts.append(alt)

    product_data: dict[str, object] = {
        "name_en": product.name_en,
        "name_ar": product.name_ar,
        "brand": product.brand_obj.name_en if product.brand_obj else product.brand,
        "category_name": category_name,
        "image_alt_texts": image_alt_texts,
        "price": product.price,
        "currency": product.currency,
        "attributes": attributes,
    }

    product_text_lines = [f"Name (EN): {product.name_en or ''}"]
    if product.name_ar:
        product_text_lines.append(f"Name (AR): {product.name_ar}")
    if product_data["brand"]:
        product_text_lines.append(f"Brand: {product_data['brand']}")
    if category_name:
        product_text_lines.append(f"Category: {category_name}")
    if image_alt_texts:
        product_text_lines.append(f"Image descriptions: {'; '.join(image_alt_texts)}")
    if attributes:
        attr_str = ", ".join(f"{a['name']}: {a['value']}" for a in attributes)
        product_text_lines.append(f"Attributes: {attr_str}")
    if product.price is not None:
        product_text_lines.append(f"Price: {product.price} {product.currency}")
    product_text = "\n".join(product_text_lines)

    if body and body.prompt:
        prompt = body.prompt
    else:
        result = await db.execute(
            select(PromptTemplate.content)
            .where(PromptTemplate.type == "pre_prompt", PromptTemplate.is_active == True)  # noqa: E712
            .order_by(PromptTemplate.created_at.desc())
            .limit(1)
        )
        pre_prompt = result.scalar_one_or_none() or prompt_defaults.DEFAULT_PRE_PROMPT

        result = await db.execute(
            select(PromptTemplate.content)
            .where(PromptTemplate.type == "ending_prompt", PromptTemplate.is_active == True)  # noqa: E712
            .order_by(PromptTemplate.created_at.desc())
            .limit(1)
        )
        ending_prompt = result.scalar_one_or_none() or prompt_defaults.DEFAULT_ENDING_PROMPT

        prompt = pre_prompt + product_text + "\n\n" + ending_prompt

    ai_client = getattr(http_request.app.state, "ai_client", None)
    if ai_client is None:
        raise ServiceUnavailableError("AI Engine client not available", translation_key=E.AI_ENGINE_NOT_AVAILABLE)

    result = await ai_client.generate_description(product_data, prompt=prompt, model=body.model if body else None, request_id=http_request.scope.get("request_id", ""))
    if result is None:
        raise ServiceUnavailableError("Description generation failed: AI Engine unavailable", translation_key=E.DESCRIPTION_GENERATION_FAILED)

    descriptions = result.get("descriptions", {})
    model = result.get("model", "")
    prompt = result.get("prompt", "")

    old_en = product.ai_description_en
    old_ar = product.ai_description_ar

    if old_en or old_ar:
        version = AIDescriptionVersion(
            product_id=product_id,
            description_en=old_en,
            description_ar=old_ar,
            model=model,
        )
        db.add(version)

    product.ai_description_en = descriptions.get("en")
    product.ai_description_ar = descriptions.get("ar")

    result_product = await product_definition_service.get_store_product(db, product_id, store_id)
    history = [AIDescriptionVersionResponse.model_validate(v) for v in result_product.ai_description_versions or []]

    activity = http_request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = product_id
        activity["action"] = "GENERATE_DESCRIPTION"
        activity["message"] = f"user {current_user.id} generate description for product {product_id} in store {store_id}"

    return success(
        GenerateDescriptionResponse(
            descriptions=descriptions,
            model=model,
            prompt=prompt,
            history=history,
        ),
    )
