import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.routers import embed as embed_router
from app.services.embedding_client import EmbeddingClient
from app.services.rag import RAGService


@pytest_asyncio.fixture
async def embed_test_app() -> AsyncGenerator[FastAPI, None]:
    app = FastAPI()
    app.include_router(embed_router.router)
    yield app


WEBHOOK_URL = "https://api.example.com/webhook/embedding-result"
BASE_BODY = {"product_id": "p1", "lang": "en", "text": "test passage", "webhook_url": WEBHOOK_URL}
BASE_BODY_NO_TEXT = {"product_id": "p1", "lang": "en", "text": "test", "webhook_url": WEBHOOK_URL}


@pytest.mark.asyncio
async def test_embed_skipped_when_no_client(embed_test_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=embed_test_app), base_url="http://test") as client:
        resp = await client.post("/embed-product", json=BASE_BODY)
    assert resp.status_code == 200
    assert resp.json() == {"status": "skipped", "reason": "embedding service not available"}


@pytest.mark.asyncio
async def test_embed_success(embed_test_app: FastAPI) -> None:
    embedder = MagicMock(spec=EmbeddingClient)
    embedder.model_name = "Qwen/Qwen3-Embedding-0.6B"
    embedder.embed_passage = AsyncMock(return_value=[0.1, 0.2, 0.3])
    rag = MagicMock(spec=RAGService)
    rag.upsert_embedding = AsyncMock()
    embed_test_app.state.embedding_client = embedder
    embed_test_app.state.rag_service = rag

    with patch("app.routers.embed._send_webhook") as mock_webhook:
        async with AsyncClient(transport=ASGITransport(app=embed_test_app), base_url="http://test") as client:
            resp = await client.post("/embed-product", json=BASE_BODY)

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    embedder.embed_passage.assert_awaited_once_with("test passage")
    expected_point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "p1_en"))
    rag.upsert_embedding.assert_awaited_once_with(expected_point_id, [0.1, 0.2, 0.3], "p1", "en", "test passage", None, None)
    mock_webhook.assert_called_once_with(
        WEBHOOK_URL,
        {
            "product_id": "p1",
            "lang": "en",
            "status": "done",
            "model": "Qwen/Qwen3-Embedding-0.6B",
        },
    )


@pytest.mark.asyncio
async def test_embed_failure_returns_error(embed_test_app: FastAPI) -> None:
    embedder = MagicMock(spec=EmbeddingClient)
    embedder.model_name = "Qwen/Qwen3-Embedding-0.6B"
    embedder.embed_passage = AsyncMock(return_value=None)
    embed_test_app.state.embedding_client = embedder
    embed_test_app.state.rag_service = MagicMock(spec=RAGService)

    with patch("app.routers.embed._send_webhook") as mock_webhook:
        async with AsyncClient(transport=ASGITransport(app=embed_test_app), base_url="http://test") as client:
            resp = await client.post("/embed-product", json=BASE_BODY_NO_TEXT)

    assert resp.status_code == 200
    assert resp.json() == {"status": "error", "reason": "embedding failed"}
    mock_webhook.assert_called_once_with(
        WEBHOOK_URL,
        {
            "product_id": "p1",
            "lang": "en",
            "status": "error",
            "error": "embedding returned None",
            "model": "Qwen/Qwen3-Embedding-0.6B",
        },
    )


@pytest.mark.asyncio
async def test_embed_qdrant_failure_returns_error(embed_test_app: FastAPI) -> None:
    embedder = MagicMock(spec=EmbeddingClient)
    embedder.model_name = "Qwen/Qwen3-Embedding-0.6B"
    embedder.embed_passage = AsyncMock(return_value=[0.1, 0.2, 0.3])
    rag = MagicMock(spec=RAGService)
    rag.upsert_embedding = AsyncMock(side_effect=Exception("Qdrant connection refused"))
    embed_test_app.state.embedding_client = embedder
    embed_test_app.state.rag_service = rag

    with patch("app.routers.embed._send_webhook") as mock_webhook:
        async with AsyncClient(transport=ASGITransport(app=embed_test_app), base_url="http://test") as client:
            resp = await client.post("/embed-product", json=BASE_BODY_NO_TEXT)

    assert resp.status_code == 200
    assert resp.json() == {"status": "error", "reason": "qdrant upsert failed"}
    mock_webhook.assert_called_once_with(
        WEBHOOK_URL,
        {
            "product_id": "p1",
            "lang": "en",
            "status": "error",
            "error": "qdrant_upsert_failed",
            "model": "Qwen/Qwen3-Embedding-0.6B",
        },
    )


class TestSendWebhook:
    @staticmethod
    def _make_mock_client(response: httpx.Response | type[Exception]) -> MagicMock:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        if isinstance(response, type) and issubclass(response, Exception):
            mock_client.post = AsyncMock(side_effect=response("connection error"))
        else:
            mock_client.post = AsyncMock(return_value=response)
        return mock_client

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        mock_client = self._make_mock_client(httpx.Response(200))
        with (
            patch("app.routers.embed.httpx.AsyncClient", return_value=mock_client),
            patch("app.routers.embed.is_safe_webhook_url", return_value=True),
        ):
            from app.routers.embed import _send_webhook

            await _send_webhook("https://example.com/webhook", {"status": "done"})

        mock_client.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_retries_on_500(self) -> None:
        mock_client = self._make_mock_client(httpx.Response(500, text="server error"))
        with (
            patch("app.routers.embed.httpx.AsyncClient", return_value=mock_client),
            patch("app.routers.embed.is_safe_webhook_url", return_value=True),
        ):
            from app.routers.embed import _send_webhook

            await _send_webhook("https://example.com/webhook", {"status": "test"})

        assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_retries_on_exception(self) -> None:
        mock_client = self._make_mock_client(httpx.RequestError)
        with (
            patch("app.routers.embed.httpx.AsyncClient", return_value=mock_client),
            patch("app.routers.embed.is_safe_webhook_url", return_value=True),
        ):
            from app.routers.embed import _send_webhook

            await _send_webhook("https://example.com/webhook", {"status": "test"})

        assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_400(self) -> None:
        mock_client = self._make_mock_client(httpx.Response(400, text="bad request"))
        with (
            patch("app.routers.embed.httpx.AsyncClient", return_value=mock_client),
            patch("app.routers.embed.is_safe_webhook_url", return_value=True),
        ):
            from app.routers.embed import _send_webhook

            result = await _send_webhook("https://example.com/webhook", {"status": "test"})

        assert mock_client.post.call_count == 1
        assert result is False

    @pytest.mark.asyncio
    async def test_rejects_unsafe_url(self) -> None:
        with patch("app.routers.embed.httpx.AsyncClient") as mock_async:
            from app.routers.embed import _send_webhook

            result = await _send_webhook("http://127.0.0.1:6333/webhook", {"status": "done"})

        assert result is False
        mock_async.assert_not_called()


class TestEmbedMissingWebhook:
    @pytest.mark.asyncio
    async def test_success_no_webhook(self, embed_test_app: FastAPI) -> None:
        embedder = MagicMock(spec=EmbeddingClient)
        embedder.embed_passage = AsyncMock(return_value=[0.1, 0.2])
        rag = MagicMock(spec=RAGService)
        rag.upsert_embedding = AsyncMock()
        embed_test_app.state.embedding_client = embedder
        embed_test_app.state.rag_service = rag

        async with AsyncClient(transport=ASGITransport(app=embed_test_app), base_url="http://test") as client:
            resp = await client.post(
                "/embed-product",
                json={
                    "product_id": "p1",
                    "lang": "en",
                    "text": "test",
                },
            )

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_embedding_failure_no_webhook(self, embed_test_app: FastAPI) -> None:
        embedder = MagicMock(spec=EmbeddingClient)
        embedder.embed_passage = AsyncMock(return_value=None)
        embed_test_app.state.embedding_client = embedder
        embed_test_app.state.rag_service = MagicMock(spec=RAGService)

        async with AsyncClient(transport=ASGITransport(app=embed_test_app), base_url="http://test") as client:
            resp = await client.post(
                "/embed-product",
                json={
                    "product_id": "p1",
                    "lang": "en",
                    "text": "test",
                },
            )

        assert resp.status_code == 200
        assert resp.json() == {"status": "error", "reason": "embedding failed"}

    @pytest.mark.asyncio
    async def test_rag_service_only(self, embed_test_app: FastAPI) -> None:
        embedder = MagicMock(spec=EmbeddingClient)
        embedder.embed_passage = AsyncMock(return_value=[0.1, 0.2])
        embed_test_app.state.embedding_client = embedder

        async with AsyncClient(transport=ASGITransport(app=embed_test_app), base_url="http://test") as client:
            resp = await client.post(
                "/embed-product",
                json={
                    "product_id": "p1",
                    "lang": "en",
                    "text": "test",
                },
            )

        assert resp.status_code == 200
        assert resp.json() == {"status": "skipped", "reason": "embedding service not available"}
