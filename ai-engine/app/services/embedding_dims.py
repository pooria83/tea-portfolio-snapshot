from loguru import logger

# Known embedding models mapped to their output vector dimensions.
# Keys may be either the fully-qualified name ("Qwen/Qwen3-Embedding-4B") or
# the bare model name ("Qwen3-Embedding-4B"); lookups normalize both forms so
# runtime configs that omit the org prefix still resolve correctly.
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

DEFAULT_EMBEDDING_DIMS: int = 1024


def normalize_model_name(model_name: str) -> str:
    """Strip any org prefix (e.g. ``Qwen/...``) from a model name."""
    return model_name.rsplit("/", 1)[-1]


def embedding_dims_for(
    model_name: str,
    fallback: int | None = None,
) -> int:
    """Resolve the expected output dimensions for *model_name*.

    Matches the bare model name first; falls back to *fallback* (or
    ``DEFAULT_EMBEDDING_DIMS``) when the model is not mapped, logging a
    warning so an unmapped model never silently uses arbitrary dimensions.
    """
    bare = normalize_model_name(model_name)
    dims = EMBEDDING_MODEL_DIMS.get(bare)
    if dims is not None:
        return dims

    if fallback is not None:
        logger.warning(
            "Embedding model '{}' is not in EMBEDDING_MODEL_DIMS; using fallback dims {}",
            model_name,
            fallback,
        )
        return fallback

    logger.warning(
        "Embedding model '{}' is not in EMBEDDING_MODEL_DIMS; using default dims {}",
        model_name,
        DEFAULT_EMBEDDING_DIMS,
    )
    return DEFAULT_EMBEDDING_DIMS
