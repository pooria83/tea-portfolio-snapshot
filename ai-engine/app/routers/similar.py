from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger

from app.core.logging import request_id_var, user_id_var
from app.models.similar import SimilarRequest, SimilarResponse
from app.services.rag import RAGService

router = APIRouter(prefix="/similar", tags=["similar"])


async def get_rag(request: Request) -> RAGService:
    return cast(RAGService, request.app.state.rag_service)


@router.post("", response_model=SimilarResponse)
async def similar(
    body: SimilarRequest,
    rag: RAGService = Depends(get_rag),
) -> SimilarResponse:
    logger.info("SIMILAR_REQUEST product_id={} lang={} limit={} categories={}", body.product_id, body.lang, body.limit, body.categories)
    logger.info(
        "TRACE_SIMILAR_START request_id={} user_id={} product_id={} lang={} limit={} categories={}",
        request_id_var.get(),
        user_id_var.get(),
        body.product_id,
        body.lang,
        body.limit,
        body.categories,
    )
    products = await rag.similar(body.product_id, limit=body.limit, categories=body.categories, lang=body.lang)
    if not products:
        logger.info("SIMILAR_EMPTY product_id={}", body.product_id)
        logger.info("TRACE_SIMILAR_END product_id={} count=0", body.product_id)
        raise HTTPException(status_code=404, detail="Product not found in index")
    payload: list[dict[str, Any]] = [
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "currency": p.currency,
            "brand": p.brand,
            "image_url": p.image_url,
            "store_id": p.store_id,
        }
        for p in products
    ]
    logger.info("SIMILAR_RESULTS product_id={} count={}", body.product_id, len(payload))
    logger.info("TRACE_SIMILAR_END product_id={} count={}", body.product_id, len(payload))
    return SimilarResponse(products=payload)
