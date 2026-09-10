import json
from typing import Any

from loguru import logger
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CacheKeys, cache_or_fetch
from app.repositories.settings import SystemSettingRepository

DEFAULT_EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"
DEFAULT_EMBEDDING_DIMS: int = 1024


def normalize_model_name(model_name: str) -> str:
    """Strip any org prefix (e.g. ``Qwen/...``) from a model name.

    The ``embed_models`` catalog stores bare model names (``Qwen3-Embedding-4B``),
    so lookups must tolerate both the bare name and the fully-qualified path
    used in configs (``Qwen/Qwen3-Embedding-4B``).
    """
    return model_name.rsplit("/", 1)[-1]


# Map of known embedding models to their vector dimensions.
# Keys are bare model names (no org prefix) matching the ``embed_models``
# catalog. Add new models here as they are integrated. Missing models will
# fall back to DEFAULT_EMBEDDING_DIMS (1024) and may cause dimension
# mismatches in Qdrant until the collection is recreated with the correct size.
EMBEDDING_MODEL_DIMS: dict[str, int] = {
    "Qwen3-Embedding-0.6B": 1024,
    "Qwen3-Embedding-4B": 2560,
    "Qwen3-Embedding-8B": 4096,
    "F2LLM-v2-4B": 2560,
    "jina-embeddings-v5-text-small": 1024,
    "BGE-M3": 1024,
    "Nomic Embed v2": 768,
    "multilingual-e5-base": 768,
    "multilingual-e5-large-instruct": 1024,
}


async def get_embedding_dims(model_name: str) -> int:
    """Return the expected vector dimensions for *model_name*.

    Normalizes org prefixes before looking up the model in the
    ``EMBEDDING_MODEL_DIMS`` mapping; returns ``DEFAULT_EMBEDDING_DIMS`` (1024)
    when the model is not found.  This is useful for callers that only need the
    dimension and do not need the full model‑name resolution logic of
    :func:`get_active_embedding_model`.
    """
    dims = EMBEDDING_MODEL_DIMS.get(normalize_model_name(model_name))
    if dims is None:
        logger.warning(
            "Embedding model '{}' is not in EMBEDDING_MODEL_DIMS; falling back to default dims {}",
            model_name,
            DEFAULT_EMBEDDING_DIMS,
        )
        return DEFAULT_EMBEDDING_DIMS
    return dims


async def get_active_embedding_model(db: AsyncSession, redis: AsyncRedis | None = None) -> tuple[str, int]:
    """Return the admin-configured embedding model name and its vector dimensions.

    Reads the ``embedding_provider`` system setting (either a JSON dict with a
    ``model`` key or a legacy plain provider name) and falls back to
    ``DEFAULT_EMBEDDING_MODEL`` / ``DEFAULT_EMBEDDING_DIMS`` when unset or
    unparsable. When *redis* is given, the resolved ``(model, dims)`` pair is
    cached (short TTL, stampede-locked) and invalidated on any
    ``system_settings``/``embed_models`` write.

    Returns:
        ``(model_name, dimensions)`` tuple.  The caller should use
        :func:`get_embedding_dims` for a simple look‑up if they do not need the
        full model‑name resolution logic.
    """

    async def _resolve() -> dict[str, str | int]:
        setting = await SystemSettingRepository(db, redis).get_by_key("embedding_provider")
        value = setting["value"] if setting else None
        if not value:
            return {"model": DEFAULT_EMBEDDING_MODEL, "dims": DEFAULT_EMBEDDING_DIMS}
        try:
            parsed: Any = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {"model": DEFAULT_EMBEDDING_MODEL, "dims": DEFAULT_EMBEDDING_DIMS}
        if isinstance(parsed, dict):
            model = str(parsed.get("model") or "").strip()
            if model:
                dims = await get_embedding_dims(model)
                return {"model": model, "dims": dims}
        return {"model": DEFAULT_EMBEDDING_MODEL, "dims": DEFAULT_EMBEDDING_DIMS}

    if redis is None:
        resolved = await _resolve()
    else:
        resolved = await cache_or_fetch(redis, CacheKeys.EMBED_MODEL.prefix, CacheKeys.EMBED_MODEL.ttl, _resolve, lock=True)
    return str(resolved["model"]), int(resolved["dims"])
