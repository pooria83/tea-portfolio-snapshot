from app.core.config import Settings
from app.services.embedding.models.base import EmbeddingModel
from app.services.embedding.models.openrouter import OpenRouterModel
from app.services.embedding.models.sentence_transformer import SentenceTransformerModel
from app.services.embedding.models.tei import TEIModel
from app.services.embedding_dims import embedding_dims_for


def _dims_for(settings: Settings) -> int:
    """Resolve vector dims from the configured model name (mapping-aware)."""
    return embedding_dims_for(settings.embedding_model, settings.embedding_dimensions)


def create_embedding_model(
    settings: Settings,
    api_key: str = "",
    fallback_base_url: str = "",
) -> EmbeddingModel:
    provider = settings.embedding_provider
    dimensions = _dims_for(settings)

    if provider == "sentence_transformer":
        return SentenceTransformerModel(
            model=settings.embedding_model,
            dimensions=dimensions,
        )

    if provider == "tei":
        return TEIModel(
            base_url=settings.tei_base_url,
            model=settings.embedding_model,
            dimensions=dimensions,
        )

    if provider == "openrouter":
        base_url = fallback_base_url or "https://openrouter.ai/api/v1"
        return OpenRouterModel(
            api_key=api_key,
            base_url=base_url,
            model=settings.embedding_model,
            dimensions=dimensions,
        )

    msg = f"Unknown embedding_provider: {provider!r} (expected 'sentence_transformer', 'tei', or 'openrouter')"
    raise ValueError(msg)
