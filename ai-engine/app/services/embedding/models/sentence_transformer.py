import asyncio
from functools import partial

from loguru import logger
from sentence_transformers import SentenceTransformer

from app.services.embedding.models.base import EmbeddingModel

QWEN3_QUERY_INSTRUCT = "Instruct: Given a web search query, retrieve relevant passages\nQuery: {}"


class SentenceTransformerModel(EmbeddingModel):
    def __init__(self, model: str, dimensions: int) -> None:
        logger.info("Loading SentenceTransformer model: {}", model)
        try:
            self._model = SentenceTransformer(model, device="cpu")
        except Exception:
            logger.exception("Failed to load SentenceTransformer model: {}", model)
            raise
        self._model_name = model
        self._dimensions = dimensions
        logger.info("SentenceTransformer model loaded: {} (dim={})", model, dimensions)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model_name(self) -> str:
        return self._model_name

    async def embed_query(self, text: str) -> list[float] | None:
        try:
            loop = asyncio.get_running_loop()
            emb = await loop.run_in_executor(
                None,
                partial(self._model.encode, QWEN3_QUERY_INSTRUCT.format(text), normalize_embeddings=True),
            )
            return emb.tolist()  # type: ignore[no-any-return]
        except Exception as exc:
            logger.error("Query embedding failed: {}", exc)
            return None

    async def embed_passage(self, text: str) -> list[float] | None:
        try:
            loop = asyncio.get_running_loop()
            emb = await loop.run_in_executor(
                None,
                partial(self._model.encode, text, normalize_embeddings=True),
            )
            return emb.tolist()  # type: ignore[no-any-return]
        except Exception as exc:
            logger.error("Passage embedding failed: {}", exc)
            return None

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        try:
            loop = asyncio.get_running_loop()
            embs = await loop.run_in_executor(
                None,
                partial(self._model.encode, texts, normalize_embeddings=True, show_progress_bar=False),
            )
            return [e.tolist() for e in embs]
        except Exception as exc:
            logger.error("Batch embedding failed: {}", exc)
            return [None] * len(texts)

    async def health(self) -> bool:
        """In-process model — always available once loaded."""
        return True
