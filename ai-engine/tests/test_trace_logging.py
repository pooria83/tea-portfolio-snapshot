from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from loguru import logger

from app.core.logging import request_id_var, user_id_var
from app.routers import chat as chat_router
from app.routers import similar as similar_router
from app.services.embedding_client import EmbeddingClient
from app.services.rag import RAGService


@pytest.fixture
def loguru_messages() -> Iterator[list[str]]:
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}", level="INFO")
    yield messages
    logger.remove(sink_id)


def _hit(
    point_id: str,
    score: float,
    product_id: str | None = None,
    name: str | None = None,
    brand: str | None = None,
    price: float | None = None,
    family: list[str] | None = None,
    category: list[str] | None = None,
) -> MagicMock:
    hit = MagicMock()
    hit.id = point_id
    hit.score = score
    hit.payload = {
        "product_id": product_id or point_id,
        "product_data": {
            "en": {
                "name": name or f"Product {point_id}",
                "brand": brand or "Brand",
                "price": price if price is not None else 99.0,
            }
        },
        "_color_family": family or ["reds-pinks"],
        "_category": category or [],
    }
    return hit


@pytest.fixture
async def trace_app(
    mock_llm_client: MagicMock,
    embedding_client: EmbeddingClient,
    rag_service: RAGService,
) -> AsyncGenerator[FastAPI, None]:
    app = FastAPI()
    app.state.llm_client = mock_llm_client
    app.state.comm_llm_client = mock_llm_client
    app.state.embedding_client = embedding_client
    app.state.rag_service = rag_service

    app.include_router(chat_router.router)
    app.include_router(similar_router.router)

    app.dependency_overrides[chat_router.get_llm] = lambda: mock_llm_client
    app.dependency_overrides[chat_router.get_comm_llm] = lambda: mock_llm_client
    app.dependency_overrides[chat_router.get_embedder] = lambda: embedding_client
    app.dependency_overrides[chat_router.get_rag] = lambda: rag_service
    app.dependency_overrides[similar_router.get_rag] = lambda: rag_service
    return app


@pytest.mark.asyncio
async def test_chat_search_emits_full_trace_chain(
    trace_app: FastAPI,
    mock_qdrant_client: MagicMock,
    loguru_messages: list[str],
) -> None:
    mock_qdrant_client.query_points.return_value = MagicMock(points=[_hit("a", 0.8, product_id="p1", name="Red Dress", brand="Zara", price=120.0)])
    request_id_var.set("tr-req-1")
    user_id_var.set("tr-user-1")

    async with AsyncClient(transport=ASGITransport(app=trace_app), base_url="http://t") as client:
        resp = await client.post("/chat", json={"query": "red dress"})

    assert resp.status_code == 200
    joined = "\n".join(loguru_messages)
    assert "TRACE_CHAT_START request_id=tr-req-1 user_id=tr-user-1" in joined
    assert "TRACE_CHAT intent=search" in joined
    assert "TRACE_CHAT type=search" in joined
    assert "TRACE_EMBED mode=query" in joined
    assert "TRACE_QDRANT_HITS" in joined
    assert "id=p1" in joined and "score=0.8" in joined
    assert "TRACE_CHAT_END type=search products=1" in joined


@pytest.mark.asyncio
async def test_chat_greeting_emits_trace_chain(
    trace_app: FastAPI,
    mock_llm_client: MagicMock,
    loguru_messages: list[str],
) -> None:
    mock_llm_client.classify_intent.return_value = "greeting"
    request_id_var.set("tr-req-2")
    user_id_var.set("tr-user-2")

    async with AsyncClient(transport=ASGITransport(app=trace_app), base_url="http://t") as client:
        resp = await client.post("/chat", json={"query": "hi"})

    assert resp.status_code == 200
    joined = "\n".join(loguru_messages)
    assert "TRACE_CHAT_START request_id=tr-req-2 user_id=tr-user-2" in joined
    assert "TRACE_CHAT intent=greeting" in joined
    assert "TRACE_CHAT type=greeting" in joined
    assert "TRACE_CHAT_END type=greeting products=0" in joined
    assert "TRACE_QDRANT_HITS" not in joined


@pytest.mark.asyncio
async def test_chat_general_emits_trace_chain(
    trace_app: FastAPI,
    mock_llm_client: MagicMock,
    loguru_messages: list[str],
) -> None:
    mock_llm_client.classify_intent.return_value = "general"

    async with AsyncClient(transport=ASGITransport(app=trace_app), base_url="http://t") as client:
        resp = await client.post("/chat", json={"query": "what is fashion"})

    assert resp.status_code == 200
    joined = "\n".join(loguru_messages)
    assert "TRACE_CHAT intent=general" in joined
    assert "TRACE_CHAT type=general" in joined
    assert "TRACE_CHAT_END type=general products=0" in joined


@pytest.mark.asyncio
async def test_similar_emits_full_trace_chain(
    trace_app: FastAPI,
    mock_qdrant_client: MagicMock,
    loguru_messages: list[str],
) -> None:
    mock_qdrant_client.scroll = AsyncMock(return_value=([_hit("ref", 0.0, product_id="P1", name="Ref", price=50.0)], None))
    mock_qdrant_client.query_points.return_value = MagicMock(points=[_hit("c1", 0.75, product_id="P2", name="Cousin Dress", brand="Mango", price=80.0)])
    request_id_var.set("tr-req-3")
    user_id_var.set("tr-user-3")

    async with AsyncClient(transport=ASGITransport(app=trace_app), base_url="http://t") as client:
        resp = await client.post("/similar", json={"product_id": "P1", "lang": "en", "limit": 5})

    assert resp.status_code == 200
    joined = "\n".join(loguru_messages)
    assert "TRACE_SIMILAR_START request_id=tr-req-3 user_id=tr-user-3" in joined
    assert "TRACE_SIMILAR_SCROLL" in joined
    assert "TRACE_QDRANT_HITS" in joined
    assert "TRACE_SIMILAR_RESULTS" in joined
    assert "TRACE_SIMILAR_END product_id=P1 count=1" in joined


@pytest.mark.asyncio
async def test_llm_request_and_response_logged_at_info(
    llm_client: MagicMock,
    loguru_messages: list[str],
) -> None:
    await llm_client.chat("hello", "products_context")
    joined = "\n".join(loguru_messages)
    assert "LLM_REQUEST model=" in joined
    assert "LLM_RESPONSE model=" in joined
