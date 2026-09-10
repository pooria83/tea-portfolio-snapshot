from loguru import logger

from app.core.health import TTLHealthCache, ping_openai_endpoint, probe_with_cache
from app.core.http_client import create_openai_client
from app.services.embedding.models.base import EmbeddingModel


class OpenRouterModel(EmbeddingModel):
    def __init__(self, api_key: str, base_url: str, model: str, dimensions: int) -> None:
        self._client = create_openai_client(api_key=api_key, base_url=base_url)
        self._model = model
        self._dimensions = dimensions
        self._base_url = base_url
        self._health = TTLHealthCache()

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model_name(self) -> str:
        return self._model

    async def embed_query(self, text: str) -> list[float] | None:
        return await self._embed(f"query: {text}")

    async def embed_passage(self, text: str) -> list[float] | None:
        return await self._embed(f"passage: {text}")

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        prefixed = [f"passage: {t}" for t in texts]
        try:
            resp = await self._client.embeddings.create(model=self._model, input=prefixed, dimensions=self._dimensions)
            results: list[list[float] | None] = [None] * len(texts)
            for item in resp.data:
                results[item.index] = item.embedding
            return results
        except Exception as exc:
            logger.error("OpenRouter batch embedding failed: {}", exc)
            return [None] * len(texts)

    async def _embed(self, text: str) -> list[float] | None:
        try:
            resp = await self._client.embeddings.create(model=self._model, input=[text], dimensions=self._dimensions)
            return resp.data[0].embedding
        except Exception as exc:
            logger.error("OpenRouter embedding failed: {}", exc)
            return None

    async def health(self) -> bool:
        """Reachability probe for the OpenRouter embeddings endpoint (GET /models)."""
        return await probe_with_cache(lambda: ping_openai_endpoint(self._base_url), self._health)
