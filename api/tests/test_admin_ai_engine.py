from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient

from app.main import app

VECTOR = [0.1121212, 0.2312312, 0.0000345]
OK_BODY = {"status": "ok", "model": "Qwen/Qwen3-Embedding-0.6B", "dimensions": 1024, "embedding": VECTOR}


def _mock_ai_client(return_value: dict | None = OK_BODY) -> MagicMock:
    mock = MagicMock()
    mock.embed_text = AsyncMock(return_value=return_value)
    return mock


class TestEmbedText:
    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.post("/api/v1/admin/ai-engine/embed-text", json={"text": "hello"})
        assert resp.status_code == 401

    async def test_forbidden(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/v1/admin/ai-engine/embed-text", json={"text": "hello"}, headers=auth_headers)
        assert resp.status_code == 403

    async def test_success(self, client: AsyncClient, admin_headers):
        mock = _mock_ai_client()
        original = app.state.ai_client
        app.state.ai_client = mock
        try:
            resp = await client.post(
                "/api/v1/admin/ai-engine/embed-text",
                json={"text": "silk summer dress"},
                headers=admin_headers,
            )
        finally:
            app.state.ai_client = original

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"] == {"model": "Qwen/Qwen3-Embedding-0.6B", "dimensions": 1024, "embedding": VECTOR}
        mock.embed_text.assert_awaited_once()
        assert mock.embed_text.await_args.args[0] == "silk summer dress"

    async def test_engine_error_status(self, client: AsyncClient, admin_headers):
        mock = _mock_ai_client(return_value={"status": "error", "reason": "embedding failed"})
        original = app.state.ai_client
        app.state.ai_client = mock
        try:
            resp = await client.post(
                "/api/v1/admin/ai-engine/embed-text",
                json={"text": "boom"},
                headers=admin_headers,
            )
        finally:
            app.state.ai_client = original

        assert resp.status_code == 503
        assert resp.json()["success"] is False

    async def test_engine_unreachable(self, client: AsyncClient, admin_headers):
        mock = _mock_ai_client(return_value=None)
        original = app.state.ai_client
        app.state.ai_client = mock
        try:
            resp = await client.post(
                "/api/v1/admin/ai-engine/embed-text",
                json={"text": "boom"},
                headers=admin_headers,
            )
        finally:
            app.state.ai_client = original

        assert resp.status_code == 503

    async def test_validation_max_1000_chars(self, client: AsyncClient, admin_headers):
        resp = await client.post(
            "/api/v1/admin/ai-engine/embed-text",
            json={"text": "a" * 1001},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    async def test_validation_empty(self, client: AsyncClient, admin_headers):
        resp = await client.post(
            "/api/v1/admin/ai-engine/embed-text",
            json={"text": ""},
            headers=admin_headers,
        )
        assert resp.status_code == 422
