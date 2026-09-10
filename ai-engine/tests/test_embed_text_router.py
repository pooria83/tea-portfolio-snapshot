from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.routers import embed_text as embed_text_router
from app.services.embedding_client import EmbeddingClient


@pytest_asyncio.fixture
async def embed_text_app() -> AsyncGenerator[FastAPI, None]:
    app = FastAPI()
    app.include_router(embed_text_router.router)
    yield app


def _make_embedder(vector: list[float] | None = None, model_name: str = "Qwen/Qwen3-Embedding-0.6B") -> MagicMock:
    embedder = MagicMock(spec=EmbeddingClient)
    embedder.embed_passage = AsyncMock(return_value=vector)
    model = MagicMock()
    model.model_name = model_name
    model.dimensions = 1024
    embedder.model = model
    return embedder


@pytest.mark.asyncio
async def test_embed_text_error_when_no_client(embed_text_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=embed_text_app), base_url="http://test") as client:
        resp = await client.post("/embed-text", json={"text": "hello world"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "error", "reason": "embedding service not available"}


@pytest.mark.asyncio
async def test_embed_text_success(embed_text_app: FastAPI) -> None:
    vector = [0.1121212, 0.2312312, 0.0000345]
    embedder = _make_embedder(vector=vector)
    embed_text_app.state.embedding_client = embedder

    async with AsyncClient(transport=ASGITransport(app=embed_text_app), base_url="http://test") as client:
        resp = await client.post("/embed-text", json={"text": "silk summer dress"})

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "model": "Qwen/Qwen3-Embedding-0.6B",
        "dimensions": 1024,
        "embedding": vector,
    }
    embedder.embed_passage.assert_awaited_once_with("silk summer dress")


@pytest.mark.asyncio
async def test_embed_text_failure_returns_error(embed_text_app: FastAPI) -> None:
    embedder = _make_embedder(vector=None)
    embed_text_app.state.embedding_client = embedder

    async with AsyncClient(transport=ASGITransport(app=embed_text_app), base_url="http://test") as client:
        resp = await client.post("/embed-text", json={"text": "will fail"})

    assert resp.status_code == 200
    assert resp.json() == {"status": "error", "reason": "embedding failed"}


@pytest.mark.asyncio
async def test_embed_text_rejects_over_1000_chars(embed_text_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=embed_text_app), base_url="http://test") as client:
        resp = await client.post("/embed-text", json={"text": "a" * 1001})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_embed_text_rejects_empty(embed_text_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=embed_text_app), base_url="http://test") as client:
        resp = await client.post("/embed-text", json={"text": ""})
    assert resp.status_code == 422
