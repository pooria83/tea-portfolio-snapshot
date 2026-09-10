from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.services.config_manager import ConfigManager


@pytest.fixture(autouse=True)
def _strip_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "FTP_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "ftp_proxy",
        "all_proxy",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def config_settings() -> Settings:
    return Settings(
        opencode_zen_api_key="test-zen",
        openrouter_api_key="test-router",
    )


@pytest.fixture
def mock_cm() -> MagicMock:
    cm = MagicMock(spec=ConfigManager)
    cm.get.return_value = None
    cm.has_config.return_value = False
    return cm


@pytest.fixture
def mock_db() -> MagicMock:
    engine = MagicMock()
    conn = AsyncMock()
    engine.connect.return_value.__aenter__ = AsyncMock(return_value=conn)
    return engine


@pytest_asyncio.fixture
async def config_test_app(
    config_settings: Settings,
    mock_cm: MagicMock,
    mock_db: MagicMock,
) -> AsyncGenerator[FastAPI, None]:
    app = FastAPI()
    app.state.settings = config_settings
    app.state.config_manager = mock_cm
    app.state.db_engine = mock_db
    app.state.llm_client = MagicMock()
    app.state.comm_llm_client = MagicMock()
    app.state.embedding_client = MagicMock()

    from app.routers import config as config_router

    with patch("app.core.http_client.AsyncOpenAI"):
        app.include_router(config_router.router)
        yield app


@pytest.mark.asyncio
async def test_create_embedding_tei() -> None:
    from app.routers.config import _create_embedding_model
    from app.services.embedding.models.tei import TEIModel

    with patch("app.core.http_client.AsyncOpenAI"):
        model = _create_embedding_model("tei", Settings(), base_url="http://tei:8080/v1")
    assert isinstance(model, TEIModel)


@pytest.mark.asyncio
async def test_create_embedding_tei_model_override() -> None:
    from app.routers.config import _create_embedding_model
    from app.services.embedding.models.tei import TEIModel

    with patch("app.core.http_client.AsyncOpenAI"):
        model = _create_embedding_model(
            "tei",
            Settings(),
            base_url="http://tei:8080/v1",
            model="Qwen3-Embedding-8B",
        )
    assert isinstance(model, TEIModel)
    assert model.model_name == "Qwen3-Embedding-8B"


@pytest.mark.asyncio
async def test_create_embedding_tei_api_key() -> None:
    from app.routers.config import _create_embedding_model
    from app.services.embedding.models.tei import TEIModel

    with patch("app.core.http_client.AsyncOpenAI") as mock_openai:
        model = _create_embedding_model(
            "tei",
            Settings(),
            api_key="sk-secret",
            base_url="http://tei:8080/v1",
            model="BGE-M3",
        )
        assert isinstance(model, TEIModel)
        assert model._api_key == "sk-secret"
        mock_openai.assert_called_once()
        assert mock_openai.call_args.kwargs["api_key"] == "sk-secret"


@pytest.mark.asyncio
async def test_create_embedding_openrouter() -> None:
    from app.routers.config import _create_embedding_model
    from app.services.embedding.models.openrouter import OpenRouterModel

    model = _create_embedding_model("openrouter", Settings(), api_key="router-key")
    assert isinstance(model, OpenRouterModel)


@pytest.mark.asyncio
async def test_create_embedding_unknown_provider() -> None:
    from app.routers.config import _create_embedding_model

    with pytest.raises(ValueError, match="Unknown embedding_provider"):
        _create_embedding_model("invalid", Settings())


class TestApplyConfig:
    @pytest.mark.asyncio
    async def test_tei_base_url_change(self, config_test_app: FastAPI, mock_db: MagicMock) -> None:
        mock_db.connect.return_value.__aenter__.return_value.execute.return_value.fetchone = MagicMock(return_value=None)
        async with AsyncClient(transport=ASGITransport(app=config_test_app), base_url="http://test") as client:
            resp = await client.post("/config", json={"tei_base_url": "https://tunnel.url/v1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["changes"]["tei_base_url"] == "https://tunnel.url/v1"

    @pytest.mark.asyncio
    async def test_tei_base_url_ignored_when_not_str(self, config_test_app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=config_test_app), base_url="http://test") as client:
            resp = await client.post("/config", json={"tei_base_url": 123})
        assert resp.json()["changes"] == {}

    @pytest.mark.asyncio
    async def test_embedding_provider_switches_rag_collection(self, config_test_app: FastAPI) -> None:
        from app.services.rag import RAGService

        rag = MagicMock(spec=RAGService)
        rag.set_collection = MagicMock()
        rag.ensure_collection = AsyncMock()
        config_test_app.state.rag_service = rag

        async with AsyncClient(transport=ASGITransport(app=config_test_app), base_url="http://test") as client:
            resp = await client.post(
                "/config",
                json={
                    "embedding_provider": {
                        "provider": "tei",
                        "model": "Qwen/Qwen3-Embedding-0.6B",
                        "base_url": "https://tunnel.url/v1",
                    },
                },
            )
        assert resp.status_code == 200
        changes = resp.json()["changes"]
        assert changes["collection"] == "products-qwen-qwen3-embedding-0-6b"
        assert changes["embedding_model"] == "Qwen/Qwen3-Embedding-0.6B"
        rag.set_collection.assert_called_once_with("products-qwen-qwen3-embedding-0-6b", 1024)
        rag.ensure_collection.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_embedding_provider_collection_ensure_failure_reported(self, config_test_app: FastAPI) -> None:
        from app.services.rag import RAGService

        rag = MagicMock(spec=RAGService)
        rag.set_collection = MagicMock()
        rag.ensure_collection = AsyncMock(side_effect=RuntimeError("dims mismatch"))
        config_test_app.state.rag_service = rag

        async with AsyncClient(transport=ASGITransport(app=config_test_app), base_url="http://test") as client:
            resp = await client.post(
                "/config",
                json={
                    "embedding_provider": {
                        "provider": "tei",
                        "model": "Qwen/Qwen3-Embedding-0.6B",
                        "base_url": "https://tunnel.url/v1",
                    },
                },
            )
        assert resp.status_code == 200
        changes = resp.json()["changes"]
        assert "collection_error" in changes
        assert "collection" not in changes

    @pytest.mark.asyncio
    async def test_embedding_provider_tei_model_and_encrypted_key(self, config_test_app: FastAPI, config_settings: Settings) -> None:
        from cryptography.fernet import Fernet

        fernet_key = Fernet.generate_key().decode()
        config_settings.llm_encryption_key = fernet_key
        encrypted = Fernet(fernet_key.encode()).encrypt(b"sk-secret-123").decode()

        async with AsyncClient(transport=ASGITransport(app=config_test_app), base_url="http://test") as client:
            resp = await client.post(
                "/config",
                json={
                    "embedding_provider": {
                        "provider": "tei",
                        "model": "BGE-M3",
                        "base_url": "https://tunnel.url/v1",
                        "api_key": encrypted,
                        "api_key_encrypted": True,
                    },
                },
            )
        assert resp.status_code == 200
        assert resp.json()["changes"]["embedding_provider"] == "tei"
        from app.services.embedding.models.tei import TEIModel

        model = config_test_app.state.embedding_client.model
        assert isinstance(model, TEIModel)
        assert model._api_key == "sk-secret-123"
        assert model.model_name == "BGE-M3"

    @pytest.mark.asyncio
    async def test_embedding_provider_tei_plain_api_key(self, config_test_app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=config_test_app), base_url="http://test") as client:
            resp = await client.post(
                "/config",
                json={
                    "embedding_provider": {
                        "provider": "tei",
                        "model": "Qwen3-Embedding-0.6B",
                        "base_url": "https://tunnel.url/v1",
                        "api_key": "sk-plain",
                    },
                },
            )
        assert resp.status_code == 200
        from app.services.embedding.models.tei import TEIModel

        model = config_test_app.state.embedding_client.model
        assert isinstance(model, TEIModel)
        assert model._api_key == "sk-plain"

    @pytest.mark.asyncio
    async def test_embedding_provider_unknown_ignored(self, config_test_app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=config_test_app), base_url="http://test") as client:
            resp = await client.post(
                "/config",
                json={
                    "embedding_provider": {"provider": "unknown_provider"},
                },
            )
        assert resp.json()["changes"] == {}

    @pytest.mark.asyncio
    async def test_embedding_provider_ignored_when_not_dict(self, config_test_app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=config_test_app), base_url="http://test") as client:
            resp = await client.post("/config", json={"embedding_provider": "tei"})
        assert resp.json()["changes"] == {}

    @pytest.mark.asyncio
    async def test_default_llm_model_change(self, config_test_app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=config_test_app), base_url="http://test") as client:
            resp = await client.post(
                "/config",
                json={
                    "default_llm_model": {"model": "gpt-4"},
                },
            )
        assert resp.json()["changes"]["default_llm_model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_user_comm_model_change(self, config_test_app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=config_test_app), base_url="http://test") as client:
            resp = await client.post(
                "/config",
                json={
                    "user_comm_model": {"model": "claude-3"},
                },
            )
        assert resp.json()["changes"]["user_comm_model"] == "claude-3"

    @pytest.mark.asyncio
    async def test_refresh_llm(self, config_test_app: FastAPI, mock_db: MagicMock) -> None:
        conn = mock_db.connect.return_value.__aenter__.return_value
        conn.execute = AsyncMock()
        conn.execute.return_value.fetchone = MagicMock(return_value=None)

        async with AsyncClient(transport=ASGITransport(app=config_test_app), base_url="http://test") as client:
            resp = await client.post("/config", json={"refresh_llm": True})
        assert resp.json()["changes"]["refresh_llm"] == "ok"

    @pytest.mark.asyncio
    async def test_empty_body(self, config_test_app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=config_test_app), base_url="http://test") as client:
            resp = await client.post("/config", json={})
        assert resp.json()["changes"] == {}

    @pytest.mark.asyncio
    async def test_multiple_changes(self, config_test_app: FastAPI) -> None:
        async with AsyncClient(transport=ASGITransport(app=config_test_app), base_url="http://test") as client:
            resp = await client.post(
                "/config",
                json={
                    "tei_base_url": "https://tei.url/v1",
                    "embedding_provider": {"provider": "tei", "base_url": "https://tei.url/v1"},
                    "default_llm_model": {"model": "gpt-4", "api_key": "sk-xxx"},
                },
            )
        data = resp.json()
        assert data["changes"]["tei_base_url"] == "https://tei.url/v1"
        assert data["changes"]["embedding_provider"] == "tei"
        assert data["changes"]["default_llm_model"] == "gpt-4"
