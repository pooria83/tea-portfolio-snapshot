import asyncio
import uuid

import httpx
from fastapi import APIRouter, Request
from loguru import logger

from app.core.ssrf import is_safe_webhook_url
from app.models.embed_product import EmbedProductRequest
from app.services.embedding_client import EmbeddingClient
from app.services.rag import RAGService

router = APIRouter(prefix="/embed-product", tags=["embed"])

WEBHOOK_MAX_RETRIES = 2
WEBHOOK_BACKOFF = 1.0


def _webhook_payload(
    body: EmbedProductRequest,
    status: str,
    error: str | None = None,
    model: str = "",
) -> dict[str, object]:
    payload: dict[str, object] = {"product_id": body.product_id, "lang": body.lang, "status": status, "model": model}
    if error:
        payload["error"] = error
    return payload


async def _send_webhook(url: str, payload: dict[str, object]) -> bool:
    """Deliver a webhook with retries; returns True on success.

    Refuses unsafe URLs (SSRF guard) and does not retry client 4xx errors,
    which will never succeed.
    """
    if not is_safe_webhook_url(url):
        logger.error("Webhook rejected: unsafe URL {}", url)
        return False
    last_exc: Exception | None = None
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
        for attempt in range(WEBHOOK_MAX_RETRIES + 1):
            try:
                resp = await client.post(url, json=payload, timeout=10.0)
                if resp.status_code >= 500:
                    logger.error("Webhook to {} returned {} (attempt {}/{}): {}", url, resp.status_code, attempt + 1, WEBHOOK_MAX_RETRIES + 1, resp.text)
                    if attempt < WEBHOOK_MAX_RETRIES:
                        backoff = WEBHOOK_BACKOFF * (2**attempt)
                        logger.warning("Retrying webhook to {} in {}s", url, backoff)
                        await asyncio.sleep(backoff)
                        continue
                    return False
                if resp.status_code >= 400:
                    logger.error("Webhook to {} returned {} (attempt {}/{}): {} — not retrying", url, resp.status_code, attempt + 1, WEBHOOK_MAX_RETRIES + 1, resp.text)
                    return False
                logger.info("Webhook sent to {}: {}", url, payload)
                return True
            except Exception as exc:
                last_exc = exc
                if attempt < WEBHOOK_MAX_RETRIES:
                    backoff = WEBHOOK_BACKOFF * (2**attempt)
                    logger.warning("Webhook to {} failed (attempt {}/{}): {} — retrying in {}s", url, attempt + 1, WEBHOOK_MAX_RETRIES + 1, exc, backoff)
                    await asyncio.sleep(backoff)
                else:
                    logger.exception("Webhook to {} failed after {} attempts", url, WEBHOOK_MAX_RETRIES + 1)
    if last_exc is not None:
        logger.exception("Webhook to {} failed permanently: {}", url, last_exc)
    return False


@router.post("")
async def embed_product(request: Request, body: EmbedProductRequest) -> dict[str, str]:
    logger.info("RECEIVED embed request product={} lang={} text_len={} webhook={}", body.product_id, body.lang, len(body.text), bool(body.webhook_url))

    embedding_client: EmbeddingClient | None = getattr(request.app.state, "embedding_client", None)
    rag_service: RAGService | None = getattr(request.app.state, "rag_service", None)

    if embedding_client is None or rag_service is None:
        logger.warning("Embedding service not available for product={}", body.product_id)
        return {"status": "skipped", "reason": "embedding service not available"}

    logger.info("Embedding product {} (lang={})", body.product_id, body.lang)
    embedding = await embedding_client.embed_passage(body.text)

    if embedding is None:
        logger.error("Failed to embed product {}", body.product_id)
        if body.webhook_url:
            await _send_webhook(
                body.webhook_url,
                _webhook_payload(body, "error", error="embedding returned None", model=embedding_client.model_name),
            )
        return {"status": "error", "reason": "embedding failed"}

    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{body.product_id}_{body.lang}"))
    try:
        await rag_service.upsert_embedding(point_id, embedding, body.product_id, body.lang, body.text, body.payload, body.filters)
    except Exception:
        logger.exception("Qdrant upsert failed for product {}", body.product_id)
        if body.webhook_url:
            await _send_webhook(
                body.webhook_url,
                _webhook_payload(body, "error", error="qdrant_upsert_failed", model=embedding_client.model_name),
            )
        return {"status": "error", "reason": "qdrant upsert failed"}

    if body.webhook_url:
        delivered = await _send_webhook(
            body.webhook_url,
            _webhook_payload(body, "done", model=embedding_client.model_name),
        )
        if not delivered:
            return {"status": "error", "reason": "webhook delivery failed"}

    logger.info("Upserted embedding for product {} ({})", body.product_id, body.lang)
    return {"status": "ok"}
