from __future__ import annotations

from unittest.mock import AsyncMock

from app.services.embedding_client import EmbeddingClient


class TestEmbedQuery:
    async def test_success(self, embedding_client: EmbeddingClient) -> None:
        result = await embedding_client.embed_query("red dress")
        assert result == [0.1, 0.2, 0.3]

    async def test_delegates_to_model(self, embedding_client: EmbeddingClient) -> None:
        embedded_model = embedding_client._model
        embedded_model.embed_query = AsyncMock(return_value=[0.9, 0.8, 0.7])

        result = await embedding_client.embed_query("blue shirt")
        embedded_model.embed_query.assert_awaited_once_with("blue shirt")
        assert result == [0.9, 0.8, 0.7]

    async def test_api_exception(self, embedding_client: EmbeddingClient) -> None:
        embedded_model = embedding_client._model
        embedded_model.embed_query = AsyncMock(return_value=None)

        result = await embedding_client.embed_query("test")
        assert result is None


class TestEmbedPassage:
    async def test_success(self, embedding_client: EmbeddingClient) -> None:
        result = await embedding_client.embed_passage("Silk dress")
        assert result == [0.1, 0.2, 0.3]

    async def test_delegates_to_model(self, embedding_client: EmbeddingClient) -> None:
        embedded_model = embedding_client._model
        embedded_model.embed_passage = AsyncMock(return_value=[0.7, 0.8])

        result = await embedding_client.embed_passage("Cotton t-shirt")
        embedded_model.embed_passage.assert_awaited_once_with("Cotton t-shirt")
        assert result == [0.7, 0.8]

    async def test_api_exception(self, embedding_client: EmbeddingClient) -> None:
        embedded_model = embedding_client._model
        embedded_model.embed_passage = AsyncMock(return_value=None)

        result = await embedding_client.embed_passage("test")
        assert result is None


class TestEmbedBatch:
    async def test_success(self, embedding_client: EmbeddingClient) -> None:
        results = await embedding_client.embed_batch(["text a", "text b"])
        assert results == [[0.1, 0.2], [0.3, 0.4]]

    async def test_delegates_to_model(self, embedding_client: EmbeddingClient) -> None:
        embedded_model = embedding_client._model
        embedded_model.embed_batch = AsyncMock(return_value=[[0.5, 0.6], [0.7, 0.8]])

        results = await embedding_client.embed_batch(["a", "b"])
        embedded_model.embed_batch.assert_awaited_once_with(["a", "b"])
        assert results == [[0.5, 0.6], [0.7, 0.8]]

    async def test_empty_input(self, embedding_client: EmbeddingClient) -> None:
        embedded_model = embedding_client._model
        embedded_model.embed_batch = AsyncMock(return_value=[])

        results = await embedding_client.embed_batch([])
        embedded_model.embed_batch.assert_awaited_once_with([])
        assert results == []

    async def test_api_exception_returns_none_list(self, embedding_client: EmbeddingClient) -> None:
        embedded_model = embedding_client._model
        embedded_model.embed_batch = AsyncMock(return_value=[None, None, None])

        results = await embedding_client.embed_batch(["a", "b", "c"])
        assert results == [None, None, None]


class TestHealth:
    async def test_delegates_to_model(self, embedding_client: EmbeddingClient) -> None:
        embedded_model = embedding_client._model
        embedded_model.health = AsyncMock(return_value=False)

        assert await embedding_client.health() is False
        embedded_model.health.assert_awaited_once_with()

    async def test_healthy(self, embedding_client: EmbeddingClient) -> None:
        assert await embedding_client.health() is True
