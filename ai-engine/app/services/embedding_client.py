import math

from loguru import logger

from app.services.embedding.models.base import EmbeddingModel


def _embed_stats(vector: list[float] | None) -> tuple[int, float, list[float]]:
    """Compact trace stats for a vector: dim, L2 norm, first few values."""
    if not vector:
        return (0, 0.0, [])
    norm = math.sqrt(sum(float(v) * float(v) for v in vector)) or 0.0
    return (len(vector), round(norm, 4), vector[:5])


class EmbeddingClient:
    def __init__(self, model: EmbeddingModel) -> None:
        self._model = model

    @property
    def model(self) -> EmbeddingModel:
        return self._model

    @property
    def model_name(self) -> str:
        return self._model.model_name

    @property
    def dimensions(self) -> int:
        return self._model.dimensions

    async def embed_query(self, text: str) -> list[float] | None:
        vector = await self._model.embed_query(text)
        dim, norm, head = _embed_stats(vector)
        logger.info(
            "TRACE_EMBED mode=query model={} text_len={} text={} dim={} norm={} head={}",
            self.model_name,
            len(text),
            text,
            dim,
            norm,
            head,
        )
        return vector

    async def embed_passage(self, text: str) -> list[float] | None:
        vector = await self._model.embed_passage(text)
        dim, norm, head = _embed_stats(vector)
        logger.info(
            "TRACE_EMBED mode=passage model={} text_len={} text={} dim={} norm={} head={}",
            self.model_name,
            len(text),
            text,
            dim,
            norm,
            head,
        )
        return vector

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        vectors = await self._model.embed_batch(texts)
        stats = [_embed_stats(v) for v in vectors]
        dims = [d for d, _, _ in stats]
        norms = [n for _, n, _ in stats]
        logger.info(
            "TRACE_EMBED mode=batch model={} count={} text_lens={} dims={} norms={}",
            self.model_name,
            len(texts),
            [len(t) for t in texts],
            dims,
            norms,
        )
        return vectors

    async def health(self) -> bool:
        """Reachability of the active embedding backend (cached per model)."""
        return await self._model.health()
