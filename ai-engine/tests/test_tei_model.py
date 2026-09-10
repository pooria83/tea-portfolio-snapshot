from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.embedding.models.tei import QWEN3_QUERY_INSTRUCT, TEIModel


@pytest.fixture
def tei_model() -> TEIModel:
    return TEIModel(
        base_url="http://localhost:8080/v1",
        model="Qwen/Qwen3-Embedding-0.6B",
        dimensions=1024,
    )


def _make_embeddings(return_value: object | None = None, side_effect: object | None = None) -> MagicMock:
    m = MagicMock()
    m.create = AsyncMock(return_value=return_value, side_effect=side_effect)
    return m


class TestTEIModel:
    def test_properties(self, tei_model: TEIModel) -> None:
        assert tei_model.dimensions == 1024
        assert tei_model.model_name == "Qwen/Qwen3-Embedding-0.6B"

    def test_set_base_url_recreates_client(self, tei_model: TEIModel) -> None:
        original_client = tei_model._client
        tei_model.set_base_url("https://tunnel.example.com/v1")
        assert tei_model._client is not original_client
        assert str(tei_model._client._base_url) == "https://tunnel.example.com/v1/"

    async def test_embed_query_applies_qwen3_instruct(self, tei_model: TEIModel) -> None:
        mock_resp = MagicMock()
        mock_resp.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        mock_emb = _make_embeddings(return_value=mock_resp)

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(tei_model._client, "embeddings", mock_emb)
            result = await tei_model.embed_query("red dress")

        assert result == [0.1, 0.2, 0.3]
        expected_input = QWEN3_QUERY_INSTRUCT.format("red dress")
        assert mock_emb.create.call_args.kwargs["input"] == [expected_input]
        assert mock_emb.create.call_args.kwargs["model"] == "Qwen/Qwen3-Embedding-0.6B"
        assert mock_emb.create.call_args.kwargs["dimensions"] == 1024

    async def test_embed_passage_uses_bare_text(self, tei_model: TEIModel) -> None:
        mock_resp = MagicMock()
        mock_resp.data = [MagicMock(embedding=[0.4, 0.5])]
        mock_emb = _make_embeddings(return_value=mock_resp)

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(tei_model._client, "embeddings", mock_emb)
            result = await tei_model.embed_passage("silk dress")

        assert result == [0.4, 0.5]
        assert mock_emb.create.call_args.kwargs["input"] == ["silk dress"]

    async def test_embed_query_failure_returns_none(self, tei_model: TEIModel) -> None:
        mock_emb = _make_embeddings(side_effect=Exception("API error"))

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(tei_model._client, "embeddings", mock_emb)
            result = await tei_model.embed_query("test")

        assert result is None

    async def test_embed_passage_failure_returns_none(self, tei_model: TEIModel) -> None:
        mock_emb = _make_embeddings(side_effect=Exception("API error"))

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(tei_model._client, "embeddings", mock_emb)
            result = await tei_model.embed_passage("test")

        assert result is None

    async def test_embed_batch_success(self, tei_model: TEIModel) -> None:
        mock_resp = MagicMock()
        mock_resp.data = [
            MagicMock(index=0, embedding=[0.1, 0.2]),
            MagicMock(index=1, embedding=[0.3, 0.4]),
        ]
        mock_emb = _make_embeddings(return_value=mock_resp)

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(tei_model._client, "embeddings", mock_emb)
            results = await tei_model.embed_batch(["dress", "shirt"])

        assert results == [[0.1, 0.2], [0.3, 0.4]]
        assert mock_emb.create.call_args.kwargs["input"] == ["dress", "shirt"]

    async def test_embed_batch_partial_failure(self, tei_model: TEIModel) -> None:
        mock_resp = MagicMock()
        mock_resp.data = [MagicMock(index=0, embedding=[0.1, 0.2])]
        mock_emb = _make_embeddings(return_value=mock_resp)

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(tei_model._client, "embeddings", mock_emb)
            results = await tei_model.embed_batch(["dress", "shirt"])

        assert results == [[0.1, 0.2], None]

    async def test_embed_batch_exception_returns_all_none(self, tei_model: TEIModel) -> None:
        mock_emb = _make_embeddings(side_effect=Exception("API error"))

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(tei_model._client, "embeddings", mock_emb)
            results = await tei_model.embed_batch(["dress", "shirt"])

        assert results == [None, None]

    async def test_health_reachable(self, tei_model: TEIModel) -> None:
        mock_get = AsyncMock(return_value=MagicMock())

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("app.core.health.create_http_client", lambda **kwargs: _FakeClient(mock_get))
            assert await tei_model.health() is True

        assert mock_get.call_args.args[0] == "http://localhost:8080/v1/models"

    async def test_health_unreachable(self, tei_model: TEIModel) -> None:
        async def _boom(_url: str) -> None:
            raise TimeoutError("tunnel down")

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("app.core.health.create_http_client", lambda **kwargs: _FakeClient(AsyncMock(side_effect=_boom)))
            assert await tei_model.health() is False

    async def test_health_cached_within_ttl(self, tei_model: TEIModel) -> None:
        mock_get = AsyncMock(return_value=MagicMock())
        mp = pytest.MonkeyPatch()
        mp.setattr("app.core.health.create_http_client", lambda **kwargs: _FakeClient(mock_get))

        assert await tei_model.health() is True
        assert await tei_model.health() is True

        mp.undo()
        assert mock_get.call_count == 1

    async def test_health_unhealthy_ttl_shorter_than_healthy(self, tei_model: TEIModel) -> None:
        mock_get = AsyncMock(side_effect=TimeoutError("down"))
        mp = pytest.MonkeyPatch()
        mp.setattr("app.core.health.create_http_client", lambda **kwargs: _FakeClient(mock_get))

        assert await tei_model.health() is False
        assert await tei_model.health() is False

        mp.undo()
        assert mock_get.call_count == 2


class _FakeClient:
    def __init__(self, get: AsyncMock) -> None:
        self._get = get

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, url: str) -> MagicMock:
        return await self._get(url)
