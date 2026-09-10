from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.requests import Request as StarletteRequest

from app.schemas.product import DescriptionResponse, GenerateDescriptionRequest, ProductData
from app.services.key_service import resolve_model_info
from app.services.llm_client import LLMClient

router = APIRouter(tags=["descriptions"])


def _get_settings(req: StarletteRequest) -> object:
    return getattr(req.app.state, "settings", None)


async def get_default_llm(request: Request) -> LLMClient:
    return cast(LLMClient, request.app.state.llm_client)


async def resolve_llm_for_model(
    req: StarletteRequest,
    model: str,
) -> tuple[LLMClient, str]:
    default_llm: LLMClient = cast(LLMClient, req.app.state.llm_client)

    if model == default_llm.model:
        return default_llm, default_llm.model

    db_engine = getattr(req.app.state, "db_engine", None)
    if db_engine is None:
        raise HTTPException(status_code=502, detail=f"Cannot resolve API key for model '{model}': no database connection")

    encryption_key: str = ""
    has_settings = _get_settings(req)
    if has_settings:
        encryption_key = getattr(has_settings, "llm_encryption_key", "")

    model_info = await resolve_model_info(db_engine, model, encryption_key)
    if model_info is None:
        raise HTTPException(status_code=502, detail=f"Could not resolve active API key for model '{model}'")

    client = LLMClient(
        api_key=model_info["api_key"],
        base_url=model_info["base_url"],
        model=model,
        provider=model_info.get("provider", ""),
    )
    return client, model


def _build_product_text(product: ProductData) -> str:
    lines = [f"Name (EN): {product.name_en or ''}"]
    if product.name_ar:
        lines.append(f"Name (AR): {product.name_ar}")
    if product.brand:
        lines.append(f"Brand: {product.brand}")
    if product.category_name:
        lines.append(f"Category: {product.category_name}")
    if product.image_alt_texts:
        lines.append(f"Image descriptions: {'; '.join(product.image_alt_texts)}")
    if product.attributes:
        attr_str = ", ".join(f"{a.name}: {a.value}" for a in product.attributes)
        lines.append(f"Attributes: {attr_str}")
    if product.price is not None:
        lines.append(f"Price: {product.price} {product.currency}")
    return "\n".join(lines)


@router.post("/generate-description", response_model=DescriptionResponse)
async def generate_description(
    request: Request,
    body: GenerateDescriptionRequest,
    llm: LLMClient = Depends(get_default_llm),
) -> DescriptionResponse:
    if body.model:
        llm, model_name = await resolve_llm_for_model(request, body.model)
    else:
        model_name = llm.model

    if body.prompt:
        result, tokens_used = await llm.generate_with_raw_prompt(body.prompt)
        prompt = body.prompt
    else:
        product_text = _build_product_text(body.product)
        result, tokens_used, prompt = await llm.generate_descriptions(product_text)

    if result is None:
        raise HTTPException(status_code=502, detail="Description generation failed")

    return DescriptionResponse(
        descriptions=result,
        model=model_name,
        tokens_used=tokens_used,
        prompt=prompt,
    )
