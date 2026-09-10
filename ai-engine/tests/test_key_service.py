from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.services.key_service import build_llm_client, resolve_active_api_key, resolve_model_info


@pytest.fixture
def mock_engine() -> MagicMock:
    engine = MagicMock(spec=AsyncEngine)
    conn = AsyncMock()
    engine.connect.return_value.__aenter__ = AsyncMock(return_value=conn)
    return engine


@pytest.fixture
def mock_conn(mock_engine: MagicMock) -> AsyncMock:
    return mock_engine.connect.return_value.__aenter__.return_value


class TestResolveActiveApiKey:
    async def test_returns_decrypted_key_when_found(
        self,
        mock_engine: MagicMock,
        mock_conn: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("encrypted_value",)
        mock_conn.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.key_service.decrypt_api_key", return_value="decrypted"):
            result = await resolve_active_api_key(mock_engine, "gpt-4", "secret-key")

        assert result == "decrypted"

    async def test_returns_fallback_when_decrypt_fails(
        self,
        mock_engine: MagicMock,
        mock_conn: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("encrypted_value",)
        mock_conn.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.key_service.decrypt_api_key", side_effect=Exception("bad key")):
            result = await resolve_active_api_key(mock_engine, "gpt-4", "secret-key", fallback_key="fallback-key")

        assert result == "fallback-key"

    async def test_returns_fallback_when_not_in_db(
        self,
        mock_engine: MagicMock,
        mock_conn: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_conn.execute = AsyncMock(return_value=mock_result)

        result = await resolve_active_api_key(mock_engine, "gpt-4", "secret-key", fallback_key="fallback-key")

        assert result == "fallback-key"

    async def test_returns_none_when_not_found_no_fallback(
        self,
        mock_engine: MagicMock,
        mock_conn: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_conn.execute = AsyncMock(return_value=mock_result)

        result = await resolve_active_api_key(mock_engine, "gpt-4", None)

        assert result is None

    async def test_verifies_query_executed(
        self,
        mock_engine: MagicMock,
        mock_conn: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_conn.execute = AsyncMock(return_value=mock_result)

        await resolve_active_api_key(mock_engine, "test-model", "key")

        mock_conn.execute.assert_awaited_once()
        args, _ = mock_conn.execute.call_args
        sql = str(args[0])
        assert "llm_api_keys" in sql
        assert "llm_models" in sql


class TestResolveModelInfo:
    async def test_returns_info_when_found(
        self,
        mock_engine: MagicMock,
        mock_conn: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("encrypted_value", "opencode_zen")
        mock_conn.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.key_service.decrypt_api_key", return_value="decrypted-key"):
            result = await resolve_model_info(mock_engine, "deepseek-v4", "secret-key")

        assert result == {"api_key": "decrypted-key", "base_url": "https://opencode.ai/zen/v1", "provider": "opencode_zen"}

    async def test_returns_openrouter_url(
        self,
        mock_engine: MagicMock,
        mock_conn: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("encrypted_value", "openrouter")
        mock_conn.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.key_service.decrypt_api_key", return_value="router-key"):
            result = await resolve_model_info(mock_engine, "nemotron", "secret-key")

        assert result == {"api_key": "router-key", "base_url": "https://openrouter.ai/api/v1", "provider": "openrouter"}

    async def test_returns_none_when_not_in_db(
        self,
        mock_engine: MagicMock,
        mock_conn: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_conn.execute = AsyncMock(return_value=mock_result)

        result = await resolve_model_info(mock_engine, "unknown-model", "secret-key")

        assert result is None

    async def test_returns_none_when_decrypt_fails(
        self,
        mock_engine: MagicMock,
        mock_conn: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("encrypted_value", "opencode_zen")
        mock_conn.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.key_service.decrypt_api_key", side_effect=Exception("bad key")):
            result = await resolve_model_info(mock_engine, "deepseek-v4", "secret-key")

        assert result is None

    async def test_returns_none_when_unknown_provider(
        self,
        mock_engine: MagicMock,
        mock_conn: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("encrypted_value", "custom_provider")
        mock_conn.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.key_service.decrypt_api_key", return_value="decrypted-key"):
            result = await resolve_model_info(mock_engine, "custom-model", "secret-key")

        assert result is None

    async def test_verifies_query_has_provider(
        self,
        mock_engine: MagicMock,
        mock_conn: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_conn.execute = AsyncMock(return_value=mock_result)

        await resolve_model_info(mock_engine, "test-model", "key")

        mock_conn.execute.assert_awaited_once()
        args, _ = mock_conn.execute.call_args
        sql = str(args[0])
        assert "m.provider" in sql


class TestBuildLlmClient:
    async def test_uses_resolved_key(self, settings, mock_engine: MagicMock) -> None:
        with (
            patch("app.services.key_service.resolve_active_api_key", return_value="db-key"),
            patch("app.services.key_service.LLMClient") as llm_cls,
        ):
            await build_llm_client(mock_engine, "model-x", settings)
        llm_cls.assert_called_once_with(
            api_key="db-key",
            base_url=settings.opencode_zen_base_url,
            model="model-x",
            provider="opencode_zen",
        )

    async def test_falls_back_to_env_key(self, settings, mock_engine: MagicMock) -> None:
        with (
            patch("app.services.key_service.resolve_active_api_key", return_value=None),
            patch("app.services.key_service.LLMClient") as llm_cls,
        ):
            await build_llm_client(mock_engine, "model-y", settings)
        llm_cls.assert_called_once_with(
            api_key="test-zen-key",
            base_url=settings.opencode_zen_base_url,
            model="model-y",
            provider="opencode_zen",
        )
