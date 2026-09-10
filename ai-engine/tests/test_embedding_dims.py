from loguru import logger

from app.services.embedding_dims import (
    DEFAULT_EMBEDDING_DIMS,
    EMBEDDING_MODEL_DIMS,
    embedding_dims_for,
    normalize_model_name,
)


def _capture_loguru() -> tuple[list[str], int]:
    records: list[str] = []
    sink_id = logger.add(records.append, format="{message}", level="WARNING")
    return records, sink_id


def test_normalize_model_name_strips_org_prefix() -> None:
    assert normalize_model_name("Qwen/Qwen3-Embedding-4B") == "Qwen3-Embedding-4B"
    assert normalize_model_name("Qwen3-Embedding-4B") == "Qwen3-Embedding-4B"


def test_mapping_covers_every_seeded_model() -> None:
    seeded = {
        "Qwen3-Embedding-0.6B",
        "Qwen3-Embedding-4B",
        "Qwen3-Embedding-8B",
        "F2LLM-v2-4B",
        "jina-embeddings-v5-text-small",
        "BGE-M3",
        "Nomic Embed v2",
        "multilingual-e5-large-instruct",
        "multilingual-e5-base",
    }
    assert seeded <= set(EMBEDDING_MODEL_DIMS)


def test_known_dims_from_bare_names() -> None:
    expected = {
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
    for model, dims in expected.items():
        assert embedding_dims_for(model) == dims, model


def test_known_dims_from_qualified_names() -> None:
    assert embedding_dims_for("Qwen/Qwen3-Embedding-4B") == 2560
    assert embedding_dims_for("Qwen/Qwen3-Embedding-0.6B") == 1024
    assert embedding_dims_for("Qwen/Qwen3-Embedding-8B") == 4096


def test_unmapped_model_uses_fallback() -> None:
    records, sink_id = _capture_loguru()
    try:
        assert embedding_dims_for("some/unknown-model", fallback=1536) == 1536
    finally:
        logger.remove(sink_id)
    assert any("unknown-model" in r and "fallback dims" in r for r in records)


def test_unmapped_model_uses_default_dims() -> None:
    records, sink_id = _capture_loguru()
    try:
        assert embedding_dims_for("unknown-model") == DEFAULT_EMBEDDING_DIMS
    finally:
        logger.remove(sink_id)
    assert any("unknown-model" in r and "default dims" in r for r in records)
