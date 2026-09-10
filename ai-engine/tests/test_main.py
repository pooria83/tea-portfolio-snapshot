from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.rag import RAGService


@pytest.fixture(autouse=True)
def _patch_all_deps() -> None:
    rag_mock = MagicMock(spec=RAGService)
    rag_mock.close = AsyncMock()
    rag_mock.ensure_collection = AsyncMock()

    db_mock = MagicMock()
    db_mock.dispose = AsyncMock()

    qdrant_mock = MagicMock()
    qdrant_mock.close = AsyncMock()

    embedding_model_mock = MagicMock()
    embedding_model_mock.model_name = "Qwen/Qwen3-Embedding-0.6B"
    embedding_model_mock.dimensions = 1024

    patches = [
        patch("app.main.setup_logging"),
        patch("app.main.create_async_engine", return_value=db_mock),
        patch("app.main.resolve_active_api_key", return_value="mock-key"),
        patch("app.services.key_service.resolve_active_api_key", return_value="mock-key"),
        patch("app.main.create_embedding_model", return_value=embedding_model_mock),
        patch("app.main.AsyncQdrantClient", return_value=qdrant_mock),
        patch("app.main.RAGService", return_value=rag_mock),
        patch("app.main.ConfigManager"),
        patch("app.core.http_client.AsyncOpenAI"),
    ]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


def test_app_created() -> None:
    from app.main import app

    assert app.title == "Product Graph AI Engine"
    assert app.version == "0.1.0"


def test_health_endpoint() -> None:
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async def _test() -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    import asyncio

    asyncio.run(_test())


def test_routes_registered() -> None:
    from app.main import app

    schema = app.openapi()
    paths = schema["paths"]
    assert "/health" in paths
    assert "/config" in paths
    assert "/generate-description" in paths
    assert "/chat" in paths
    assert "/embed-product" in paths


@pytest.mark.asyncio
async def test_lifespan_configures_app_state() -> None:
    from fastapi import FastAPI

    from app.main import lifespan

    app = FastAPI()

    async with lifespan(app):
        assert hasattr(app.state, "llm_client")
        assert hasattr(app.state, "comm_llm_client")
        assert hasattr(app.state, "embedding_client")
        assert hasattr(app.state, "rag_service")
        assert hasattr(app.state, "config_manager")
        assert hasattr(app.state, "settings")
        assert hasattr(app.state, "db_engine")
