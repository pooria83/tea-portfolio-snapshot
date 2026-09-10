from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.embedding.models.openrouter import OpenRouterModel


@pytest.fixture
def openrouter_model() -> OpenRouterModel:
    return OpenRouterModel(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        model="nvidia/nemotron-3-8b",
        dimensions=2048,
    )


def _make_embeddings(return_value: object | None = None, side_effect: object | None = None) -> MagicMock:
    m = MagicMock()
    m.create = AsyncMock(return_value=return_value, side_effect=side_effect)
    return m


class TestOpenRouterModel:
    def test_properties(self, openrouter_model: OpenRouterModel) -> None:
        assert openrouter_model.dimensions == 2048
        assert openrouter_model.model_name == "nvidia/nemotron-3-8b"

    async def test_embed_query_prepends_prefix(self, openrouter_model: OpenRouterModel) -> None:
        mock_resp = MagicMock()
        mock_resp.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        mock_emb = _make_embeddings(return_value=mock_resp)

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(openrouter_model._client, "embeddings", mock_emb)
            result = await openrouter_model.embed_query("red dress")

        assert result == [0.1, 0.2, 0.3]
        assert mock_emb.create.call_args.kwargs["input"] == ["query: red dress"]
        assert mock_emb.create.call_args.kwargs["model"] == "nvidia/nemotron-3-8b"
        assert mock_emb.create.call_args.kwargs["dimensions"] == 2048

    async def test_embed_passage_prepends_prefix(self, openrouter_model: OpenRouterModel) -> None:
        mock_resp = MagicMock()
        mock_resp.data = [MagicMock(embedding=[0.4, 0.5])]
        mock_emb = _make_embeddings(return_value=mock_resp)

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(openrouter_model._client, "embeddings", mock_emb)
            result = await openrouter_model.embed_passage("silk dress")

        assert result == [0.4, 0.5]
        assert mock_emb.create.call_args.kwargs["input"] == ["passage: silk dress"]

    async def test_embed_query_failure_returns_none(self, openrouter_model: OpenRouterModel) -> None:
        mock_emb = _make_embeddings(side_effect=Exception("API error"))

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(openrouter_model._client, "embeddings", mock_emb)
            result = await openrouter_model.embed_query("test")

        assert result is None

    async def test_embed_passage_failure_returns_none(self, openrouter_model: OpenRouterModel) -> None:
        mock_emb = _make_embeddings(side_effect=Exception("API error"))

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(openrouter_model._client, "embeddings", mock_emb)
            result = await openrouter_model.embed_passage("test")

        assert result is None

    async def test_embed_batch_success(self, openrouter_model: OpenRouterModel) -> None:
        mock_resp = MagicMock()
        mock_resp.data = [
            MagicMock(index=0, embedding=[0.1, 0.2]),
            MagicMock(index=1, embedding=[0.3, 0.4]),
        ]
        mock_emb = _make_embeddings(return_value=mock_resp)

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(openrouter_model._client, "embeddings", mock_emb)
            results = await openrouter_model.embed_batch(["dress", "shirt"])

        assert results == [[0.1, 0.2], [0.3, 0.4]]
        assert mock_emb.create.call_args.kwargs["input"] == ["passage: dress", "passage: shirt"]

    async def test_embed_batch_partial_failure(self, openrouter_model: OpenRouterModel) -> None:
        mock_resp = MagicMock()
        mock_resp.data = [MagicMock(index=0, embedding=[0.1, 0.2])]
        mock_emb = _make_embeddings(return_value=mock_resp)

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(openrouter_model._client, "embeddings", mock_emb)
            results = await openrouter_model.embed_batch(["dress", "shirt"])

        assert results == [[0.1, 0.2], None]

    async def test_embed_batch_exception_returns_all_none(self, openrouter_model: OpenRouterModel) -> None:
        mock_emb = _make_embeddings(side_effect=Exception("API error"))

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(openrouter_model._client, "embeddings", mock_emb)
            results = await openrouter_model.embed_batch(["dress", "shirt"])

        assert results == [None, None]

    async def test_health_reachable(self, openrouter_model: OpenRouterModel) -> None:
        mock_get = AsyncMock(return_value=MagicMock())
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("app.core.health.create_http_client", lambda **kwargs: _FakeClient(mock_get))
            assert await openrouter_model.health() is True
        assert mock_get.call_args.args[0] == "https://openrouter.ai/api/v1/models"

    async def test_health_unreachable(self, openrouter_model: OpenRouterModel) -> None:
        async def _boom(_url: str) -> None:
            raise TimeoutError("tunnel down")

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("app.core.health.create_http_client", lambda **kwargs: _FakeClient(AsyncMock(side_effect=_boom)))
            assert await openrouter_model.health() is False


class _FakeClient:
    def __init__(self, get: AsyncMock) -> None:
        self._get = get

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, url: str) -> MagicMock:
        return await self._get(url)
