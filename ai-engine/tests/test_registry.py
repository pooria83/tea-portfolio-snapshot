from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.embedding.registry import create_embedding_model


@pytest.fixture
def base_settings() -> Settings:
    return Settings(
        opencode_zen_api_key="",
        openrouter_api_key="",
    )


class TestCreateEmbeddingModel:
    def test_sentence_transformer(self, base_settings: Settings) -> None:
        settings = base_settings.model_copy(update={"embedding_provider": "sentence_transformer"})
        with patch("app.services.embedding.registry.SentenceTransformerModel") as m:
            instance = MagicMock()
            m.return_value = instance

            result = create_embedding_model(settings=settings)

            m.assert_called_once_with(model=settings.embedding_model, dimensions=settings.embedding_dimensions)
            assert result is instance

    def test_tei(self, base_settings: Settings) -> None:
        settings = base_settings.model_copy(update={"embedding_provider": "tei"})
        with patch("app.services.embedding.registry.TEIModel") as m:
            instance = MagicMock()
            m.return_value = instance

            result = create_embedding_model(settings=settings)

            m.assert_called_once_with(
                base_url=settings.tei_base_url,
                model=settings.embedding_model,
                dimensions=settings.embedding_dimensions,
            )
            assert result is instance

    def test_openrouter(self, base_settings: Settings) -> None:
        settings = base_settings.model_copy(update={"embedding_provider": "openrouter"})
        with patch("app.services.embedding.registry.OpenRouterModel") as m:
            instance = MagicMock()
            m.return_value = instance

            result = create_embedding_model(settings=settings, api_key="sk-test", fallback_base_url="https://test.com/v1")

            m.assert_called_once_with(
                api_key="sk-test",
                base_url="https://test.com/v1",
                model=settings.embedding_model,
                dimensions=settings.embedding_dimensions,
            )
            assert result is instance

    def test_openrouter_default_base_url(self, base_settings: Settings) -> None:
        settings = base_settings.model_copy(update={"embedding_provider": "openrouter"})
        with patch("app.services.embedding.registry.OpenRouterModel") as m:
            instance = MagicMock()
            m.return_value = instance

            result = create_embedding_model(settings=settings, api_key="sk-test")

            m.assert_called_once_with(
                api_key="sk-test",
                base_url="https://openrouter.ai/api/v1",
                model=settings.embedding_model,
                dimensions=settings.embedding_dimensions,
            )
            assert result is instance

    def test_unknown_provider(self, base_settings: Settings) -> None:
        settings = base_settings.model_copy(update={"embedding_provider": "unknown"})
        with pytest.raises(ValueError, match="Unknown embedding_provider: 'unknown'"):
            create_embedding_model(settings=settings)
