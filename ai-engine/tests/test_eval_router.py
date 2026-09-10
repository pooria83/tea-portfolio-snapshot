from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.routers import eval as eval_router
from app.routers.chat import get_comm_llm, get_embedder, get_llm, get_rag
from app.schemas.chat import ProductRef
from app.services.embedding_client import EmbeddingClient
from app.services.rag import RAGService


@pytest_asyncio.fixture
async def eval_app(
    mock_llm_client: MagicMock,
    mock_embedder: MagicMock,
    mock_rag: MagicMock,
) -> AsyncGenerator[FastAPI, None]:
    app = FastAPI()
    app.include_router(eval_router.router)

    app.dependency_overrides[get_llm] = lambda: mock_llm_client
    app.dependency_overrides[get_comm_llm] = lambda: mock_llm_client
    app.dependency_overrides[get_embedder] = lambda: mock_embedder
    app.dependency_overrides[get_rag] = lambda: mock_rag

    yield app
    app.dependency_overrides.clear()


def _make_rag(search_scored: list[tuple[ProductRef, float]]) -> MagicMock:
    rag = MagicMock(spec=RAGService)
    rag.search_scored = AsyncMock(return_value=search_scored)
    return rag


@pytest.mark.asyncio
async def test_eval_queries_success(eval_app: FastAPI, mock_llm_client: AsyncMock) -> None:
    mock_llm_client.generate_eval_queries = AsyncMock(
        return_value=[
            {"text": "red lace dress", "locale": "en"},
            {"text": "فستان دانتيل أحمر", "locale": "ar"},
        ]
    )
    async with AsyncClient(transport=ASGITransport(app=eval_app), base_url="http://test") as client:
        resp = await client.post(
            "/eval/queries",
            json={"count": 10, "locales": ["en", "ar"], "catalog_context": "Dresses, Watches, Perfumes"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["queries"] == [
        {"text": "red lace dress", "locale": "en"},
        {"text": "فستان دانتيل أحمر", "locale": "ar"},
    ]
    mock_llm_client.generate_eval_queries.assert_awaited_once()


@pytest.mark.asyncio
async def test_eval_queries_failure_returns_502(eval_app: FastAPI, mock_llm_client: AsyncMock) -> None:
    mock_llm_client.generate_eval_queries = AsyncMock(return_value=None)
    async with AsyncClient(transport=ASGITransport(app=eval_app), base_url="http://test") as client:
        resp = await client.post("/eval/queries", json={"count": 10, "locales": ["en"]})
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_eval_queries_rejects_invalid_count(eval_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=eval_app), base_url="http://test") as client:
        resp = await client.post("/eval/queries", json={"count": 0, "locales": ["en"]})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_eval_search_success(eval_app: FastAPI, mock_llm_client: AsyncMock) -> None:
    mock_llm_client.parse_search_query = AsyncMock(
        return_value={
            "rewritten_query": "red lace dress",
            "filters": {"color": ["Red"], "category": ["Dresses"]},
        }
    )
    rag = _make_rag(
        [
            (ProductRef(id="p1", name="Red Dress", price=10.0, currency="SAR", brand="Zara"), 0.91),
            (ProductRef(id="p2", name="Lace Dress", price=20.0, currency="SAR", brand="H&M"), 0.87),
        ]
    )
    eval_app.dependency_overrides[get_rag] = lambda: rag

    async with AsyncClient(transport=ASGITransport(app=eval_app), base_url="http://test") as client:
        resp = await client.post("/eval/search", json={"query": "red lace dress", "locale": "en", "limit": 10})

    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "red lace dress"
    assert body["rewritten_query"] == "red lace dress"
    assert body["filters"]["color_family"] == ["reds-pinks"]
    assert "Dresses" in body["filters"]["category"]
    assert len(body["results"]) == 2
    assert body["results"][0]["rank"] == 1
    assert body["results"][0]["score"] == 0.91
    assert body["results"][0]["product"]["id"] == "p1"
    assert body["results"][1]["rank"] == 2
    assert body["results"][1]["score"] == 0.87
    rag.search_scored.assert_awaited_once()


@pytest.mark.asyncio
async def test_eval_search_passes_query_text_to_rag(eval_app: FastAPI, mock_llm_client: AsyncMock) -> None:
    mock_llm_client.parse_search_query = AsyncMock(
        return_value={
            "rewritten_query": "red lace dress",
            "filters": {"color": ["Red"], "category": ["Dresses"]},
        }
    )
    rag = _make_rag(
        [
            (ProductRef(id="p1", name="Red Dress", price=10.0, currency="SAR", brand="Zara"), 0.91),
        ]
    )
    eval_app.dependency_overrides[get_rag] = lambda: rag

    async with AsyncClient(transport=ASGITransport(app=eval_app), base_url="http://test") as client:
        resp = await client.post("/eval/search", json={"query": "red lace dress", "locale": "en", "limit": 10})

    assert resp.status_code == 200
    rag.search_scored.assert_awaited_once()
    kwargs = rag.search_scored.call_args.kwargs
    assert kwargs["query_text"] == "red lace dress pink"


@pytest.mark.asyncio
async def test_eval_search_dual_spec_merged(eval_app: FastAPI, mock_llm_client: AsyncMock) -> None:
    mock_llm_client.parse_search_query = AsyncMock(return_value={"rewritten_query": "lace dress", "filters": {"category": ["Dresses"]}})
    rag = _make_rag(
        [
            (ProductRef(id="p1", name="Lace Dress", price=10.0), 0.9),
            (ProductRef(id="p3", name="Other", price=30.0), 0.7),
        ]
    )
    eval_app.dependency_overrides[get_rag] = lambda: rag

    async with AsyncClient(transport=ASGITransport(app=eval_app), base_url="http://test") as client:
        resp = await client.post("/eval/search", json={"query": "lace dress with chiffon", "locale": "en"})

    assert resp.status_code == 200
    body = resp.json()
    # raw-query dual spec adds a second spec
    assert len(body["specs"]) == 2
    assert body["specs"][0]["query"] == "lace dress"
    assert body["specs"][1]["query"] == "lace dress with chiffon"
    assert rag.search_scored.await_count == 2


@pytest.mark.asyncio
async def test_eval_search_empty_results(eval_app: FastAPI, mock_llm_client: AsyncMock) -> None:
    mock_llm_client.parse_search_query = AsyncMock(return_value={"rewritten_query": "", "filters": {}})
    rag = _make_rag([])
    eval_app.dependency_overrides[get_rag] = lambda: rag

    async with AsyncClient(transport=ASGITransport(app=eval_app), base_url="http://test") as client:
        resp = await client.post("/eval/search", json={"query": "zzzz not found", "locale": "en"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] == []
    assert body["rewritten_query"] == "zzzz not found"


@pytest.mark.asyncio
async def test_eval_search_embedding_failure_returns_502(eval_app: FastAPI, mock_llm_client: AsyncMock) -> None:
    mock_llm_client.parse_search_query = AsyncMock(return_value={"rewritten_query": "dress", "filters": {}})
    embedder = MagicMock(spec=EmbeddingClient)
    embedder.embed_query = AsyncMock(return_value=None)
    eval_app.dependency_overrides[get_embedder] = lambda: embedder

    async with AsyncClient(transport=ASGITransport(app=eval_app), base_url="http://test") as client:
        resp = await client.post("/eval/search", json={"query": "dress", "locale": "en"})
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_eval_search_rejects_empty_query(eval_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=eval_app), base_url="http://test") as client:
        resp = await client.post("/eval/search", json={"query": "", "locale": "en"})
    assert resp.status_code == 422
