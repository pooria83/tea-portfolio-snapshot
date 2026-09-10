from fastapi import APIRouter, Request
from loguru import logger

from app.models.embed_text import EmbedTextRequest
from app.services.embedding_client import EmbeddingClient

router = APIRouter(prefix="/embed-text", tags=["embed"])


@router.post("")
async def embed_text(request: Request, body: EmbedTextRequest) -> dict[str, object]:
    logger.info("RECEIVED embed-text request text_len={}", len(body.text))

    embedding_client: EmbeddingClient | None = getattr(request.app.state, "embedding_client", None)

    if embedding_client is None:
        logger.warning("Embedding service not available for embed-text request")
        return {"status": "error", "reason": "embedding service not available"}

    logger.info("Embedding text (len={})", len(body.text))
    embedding = await embedding_client.embed_passage(body.text)

    if embedding is None:
        logger.error("Failed to embed text (len={})", len(body.text))
        return {"status": "error", "reason": "embedding failed"}

    model_name = getattr(embedding_client.model, "model_name", "")
    dimensions = getattr(embedding_client.model, "dimensions", len(embedding))
    logger.info("Embedding result dim={} model={}", dimensions, model_name)
    return {"status": "ok", "model": model_name, "dimensions": dimensions, "embedding": embedding}
