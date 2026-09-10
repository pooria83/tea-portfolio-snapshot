"""Tests for the anonymous chat session endpoint.

Verifies the security invariant: the minted token works for the WebSocket
(which only decodes the JWT) but is useless for authenticated REST
endpoints — it carries ``type="anon"`` and a 10-minute expiry, and the
REST auth dependencies reject any non-``access`` token with 401, so
anonymous conversations stay fully isolated from authenticated REST data.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.core.config import settings
from app.core.jwt import decode_token
from app.db.mongo import CONVERSATIONS_COLLECTION
from app.main import app
from app.services.ws_manager import ConnectionManager


async def test_anonymous_session_creates_ephemeral_user(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        "/api/v1/chat/anonymous-session",
        json={"locale": "ar", "app_version": "web-ui"},
    )
    assert resp.status_code == 201
    body = resp.json()

    token = body["token"]
    payload = decode_token(token)
    assert payload.role == "user"

    conversation = body["conversation"]
    assert conversation["status"] == "active"
    assert conversation["locale"] == "ar"
    assert conversation["id"]

    coll = client._transport.app.state.mongo_db.db[CONVERSATIONS_COLLECTION]  # type: ignore[attr-defined]
    doc = await coll.find_one({"_id": conversation["id"]})
    assert doc is not None
    assert doc["userId"] == payload.sub
    assert doc["appVersion"] == "web-ui"
    assert doc["needTitle"] is False


async def test_anonymous_sessions_have_unique_users(client: AsyncClient) -> None:
    r1 = await client.post("/api/v1/chat/anonymous-session", json={"locale": "en"})
    r2 = await client.post("/api/v1/chat/anonymous-session", json={"locale": "en"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    u1 = decode_token(r1.json()["token"]).sub
    u2 = decode_token(r2.json()["token"]).sub
    assert u1 != u2


async def test_anonymous_token_blocked_on_authenticated_rest(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/chat/anonymous-session", json={"locale": "en"})
    token = resp.json()["token"]

    chats = await client.get("/api/v1/chats", headers={"Authorization": f"Bearer {token}"})
    assert chats.status_code == 401
    assert chats.json()["error"]["translation_key"] == "not_authenticated"


async def test_anonymous_token_has_anon_type_and_short_ttl(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/chat/anonymous-session", json={"locale": "en"})
    assert resp.status_code == 201
    payload = decode_token(resp.json()["token"])
    assert payload.type == "anon"
    assert payload.exp - datetime.now(UTC) <= timedelta(minutes=10)


async def test_anonymous_session_rate_limited(client: AsyncClient) -> None:
    for _ in range(20):
        await client.post("/api/v1/chat/anonymous-session", json={"locale": "en"})
    resp = await client.post("/api/v1/chat/anonymous-session", json={"locale": "en"})
    assert resp.status_code == 429


class _FakeAnonymousService:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.calls: list[dict[str, str]] = []

    async def find_similar(self, conversation_id: str, user_id: str, product_id: str, request_id: str = "", product_name: str = "") -> dict[str, Any]:
        self.calls.append({"conversation_id": conversation_id, "user_id": user_id, "product_id": product_id, "product_name": product_name})
        return self.result

    @property
    def messages(self) -> "_FakeAnonymousMessages":
        return _FakeAnonymousMessages()


class _FakeAnonymousMessages:
    async def find_by_id(self, message_id: str, conversation_id: str) -> dict[str, Any] | None:
        return None


def _make_client():
    import warnings

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient`")
        from starlette.testclient import TestClient

        return TestClient(app, backend="asyncio")


def test_anonymous_token_works_on_websocket(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeAnonymousService(
        result={
            "productSnapshots": [{"id": "p2", "name": "Similar", "price": 5.0, "currency": "SAR"}],
            "locale": "en",
        }
    )
    monkeypatch.setattr("app.api.v1.ws.get_chat_service", lambda _app: fake)
    app.state.ws_manager = ConnectionManager()
    app.state.mongo_db = SimpleNamespace(db=AsyncMongoMockClient()[settings.mongo_db_name])
    app.state.ai_client = AsyncMock()
    app.state.session_factory = None
    _redis_store: dict[str, str] = {}
    mock_redis = AsyncMock()
    mock_redis.incr = AsyncMock(side_effect=lambda key: _redis_store.update({key: str(int(_redis_store.get(key, "0")) + 1)}) or int(_redis_store[key]))
    mock_redis.expire = AsyncMock(return_value=True)
    app.state.redis = mock_redis
    client = _make_client()

    resp = client.post(
        "/api/v1/chat/anonymous-session",
        json={"locale": "en"},
    )
    assert resp.status_code == 201
    body = resp.json()
    token = body["token"]
    conversation_id = body["conversation"]["id"]

    with client.websocket_connect(f"/api/v1/ws/chat/{conversation_id}?token={token}") as ws:
        ws.send_text('{"type": "similar_request", "product_id": "p1"}')
        cards = ws.receive_json()
        assert cards["type"] == "product_cards"
        assert cards["products"] == [{"id": "p2", "name": "Similar", "price": 5.0, "currency": "SAR"}]

    assert fake.calls == [{"conversation_id": conversation_id, "user_id": decode_token(token).sub, "product_id": "p1", "product_name": ""}]
    del app.state.mongo_db
