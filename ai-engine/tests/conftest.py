from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.routers.chat import get_embedder, get_rag
from app.routers.chat import get_llm as get_chat_llm
from app.routers.description import get_default_llm as get_desc_llm
from app.schemas.chat import ProductRef
from app.services.embedding.models.base import EmbeddingModel
from app.services.embedding_client import EmbeddingClient
from app.services.llm_client import LLMClient
from app.services.rag import RAGService


@pytest.fixture
def settings() -> Settings:
    return Settings(
        opencode_zen_api_key="test-zen-key",
        openrouter_api_key="test-router-key",
        qdrant_url="http://localhost:6333",
        database_url="sqlite+aiosqlite://",
        embedding_model="Qwen/Qwen3-Embedding-0.6B",
        embedding_dimensions=1024,
    )


@pytest.fixture
def mock_openai_chat() -> AsyncMock:
    mock = AsyncMock()
    mock.usage.total_tokens = 50
    return mock


@pytest.fixture
def mock_openai_embedding() -> AsyncMock:
    mock = AsyncMock()
    mock.data = [MagicMock(index=0, embedding=[0.1, 0.2, 0.3])]
    return mock


@pytest.fixture
def mock_openai_client(
    mock_openai_chat: AsyncMock,
    mock_openai_embedding: AsyncMock,
) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=mock_openai_chat)
    client.embeddings.create = AsyncMock(return_value=mock_openai_embedding)

    with (
        patch("app.core.http_client.AsyncOpenAI", return_value=client),
        patch("app.services.embedding_client.AsyncOpenAI", return_value=client, create=True),
    ):
        yield client


@pytest.fixture
def mock_qdrant_client() -> MagicMock:
    client = MagicMock()
    client.get_collections = AsyncMock()
    client.create_collection = AsyncMock()
    client.get_collection = AsyncMock()
    client.upsert = AsyncMock()
    client.query_points = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def llm_client(settings: Settings, mock_openai_client: MagicMock) -> LLMClient:
    return LLMClient(
        api_key=settings.opencode_zen_api_key,
        base_url=settings.opencode_zen_base_url,
        model=settings.llm_model,
        provider="opencode_zen",
    )


@pytest.fixture
def embedding_client(settings: Settings, mock_openai_client: MagicMock) -> EmbeddingClient:
    mock_model = MagicMock(spec=EmbeddingModel)
    mock_model.dimensions = settings.embedding_dimensions
    mock_model.model_name = settings.embedding_model
    mock_model.embed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock_model.embed_passage = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock_model.embed_batch = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])
    mock_model.health = AsyncMock(return_value=True)
    return EmbeddingClient(model=mock_model)


@pytest.fixture
def rag_service(settings: Settings, mock_qdrant_client: MagicMock) -> RAGService:
    return RAGService(settings, client=mock_qdrant_client)


@pytest.fixture
def mock_llm_client() -> MagicMock:
    async def _empty_stream(*_args: object, **_kwargs: object):
        for _ in ():
            yield ""

    m = MagicMock(spec=LLMClient)
    m.model = "test-model"
    m.generate_descriptions = AsyncMock(return_value=({"en": "Desc EN", "ar": "Desc AR"}, 50, "full prompt"))
    m.generate_with_raw_prompt = AsyncMock(return_value=({"en": "Raw EN", "ar": "Raw AR"}, 30))
    m.parse_search_query = AsyncMock(return_value={"rewritten_query": "", "filters": {}})
    m.chat = AsyncMock(return_value="Test answer")
    m.chat_with_tools = AsyncMock(return_value=None)
    m.chat_with_context = AsyncMock(return_value="Test answer")
    m.chat_stream = MagicMock(side_effect=_empty_stream)
    m.classify_intent = AsyncMock(return_value="search")
    m.chat_plain = AsyncMock(return_value="Test answer")
    m.chat_plain_stream = MagicMock(side_effect=_empty_stream)
    m.summarize = AsyncMock(return_value=("conversation summary", 10))
    m.generate_title = AsyncMock(return_value="Test title")
    m.health = AsyncMock(return_value=True)
    return m


@pytest.fixture
def mock_embedder() -> MagicMock:
    m = MagicMock(spec=EmbeddingClient)
    m.embed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
    m.health = AsyncMock(return_value=True)
    return m


@pytest.fixture
def mock_rag() -> MagicMock:
    m = MagicMock(spec=RAGService)
    products = [
        ProductRef(id="p1", name="Product 1", price=10.0, currency="SAR", brand="Brand A"),
        ProductRef(id="p2", name="Product 2", price=20.0, currency="SAR", brand="Brand B"),
    ]
    m.search = AsyncMock(return_value=products)
    m.search_scored = AsyncMock(return_value=[(products[0], 0.9), (products[1], 0.8)])
    m.format_products_for_prompt = MagicMock(return_value="1. Product 1 - 10.0 SAR - Brand A\n2. Product 2 - 20.0 SAR - Brand B")
    return m


@pytest.fixture
async def test_app(
    mock_llm_client: MagicMock,
    mock_embedder: MagicMock,
    mock_rag: MagicMock,
) -> AsyncGenerator[FastAPI, None]:
    app = FastAPI()
    app.state.llm_client = mock_llm_client
    app.state.comm_llm_client = mock_llm_client
    app.state.embedding_client = mock_embedder
    app.state.rag_service = mock_rag

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    from app.routers import chat as chat_router
    from app.routers import description as description_router
    from app.routers import eval as eval_router
    from app.routers import similar as similar_router
    from app.routers import summarize as summarize_router
    from app.routers import title as title_router

    app.include_router(description_router.router)
    app.include_router(chat_router.router)
    app.include_router(similar_router.router)
    app.include_router(summarize_router.router)
    app.include_router(title_router.router)
    app.include_router(eval_router.router)

    app.dependency_overrides[get_desc_llm] = lambda: mock_llm_client
    app.dependency_overrides[get_chat_llm] = lambda: mock_llm_client
    app.dependency_overrides[get_embedder] = lambda: mock_embedder
    app.dependency_overrides[get_rag] = lambda: mock_rag
    app.dependency_overrides[similar_router.get_rag] = lambda: mock_rag
    app.dependency_overrides[summarize_router.get_comm_llm] = lambda: mock_llm_client
    app.dependency_overrides[title_router.get_comm_llm] = lambda: mock_llm_client

    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def test_client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        yield client


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
