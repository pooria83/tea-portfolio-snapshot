from loguru import logger

from app.core.health import TTLHealthCache, ping_openai_endpoint, probe_with_cache
from app.core.http_client import create_openai_client
from app.services.embedding.models.base import EmbeddingModel

QWEN3_QUERY_INSTRUCT = "Instruct: Given a web search query, retrieve relevant passages\nQuery: {}"


class TEIModel(EmbeddingModel):
    def __init__(self, base_url: str, model: str, dimensions: int, api_key: str = "") -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._client = create_openai_client(api_key=api_key or "unused", base_url=base_url)
        self._model = model
        self._dimensions = dimensions
        self._health = TTLHealthCache()

    def set_base_url(self, base_url: str) -> None:
        self._base_url = base_url
        self._client = create_openai_client(api_key=self._api_key or "unused", base_url=base_url)
        self._health = TTLHealthCache()

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model_name(self) -> str:
        return self._model

    async def embed_query(self, text: str) -> list[float] | None:
        return await self._embed(QWEN3_QUERY_INSTRUCT.format(text))

    async def embed_passage(self, text: str) -> list[float] | None:
        return await self._embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        try:
            resp = await self._client.embeddings.create(model=self._model, input=texts, dimensions=self._dimensions)
            results: list[list[float] | None] = [None] * len(texts)
            for item in resp.data:
                results[item.index] = item.embedding
            return results
        except Exception as exc:
            logger.error("TEI batch embedding failed: {}", exc)
            return [None] * len(texts)

    async def _embed(self, text: str) -> list[float] | None:
        try:
            resp = await self._client.embeddings.create(model=self._model, input=[text], dimensions=self._dimensions)
            return resp.data[0].embedding
        except Exception as exc:
            logger.error("TEI embedding failed: {}", exc)
            return None

    async def health(self) -> bool:
        """Reachability probe for the TEI container/tunnel (GET /models)."""
        return await probe_with_cache(lambda: ping_openai_endpoint(self._base_url), self._health)
