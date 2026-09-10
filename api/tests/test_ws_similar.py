from typing import Any

import pytest

from app.core.exceptions import NotFoundError
from app.core.jwt import create_access_token
from app.main import app
from app.services.ws_manager import ConnectionManager


def _make_client():
    import warnings

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient`")
        from starlette.testclient import TestClient

        return TestClient(app, backend="asyncio")


class _FakeSimilarService:
    def __init__(
        self,
        result: dict[str, Any] | None = None,
        error: Exception | None = None,
        saved_doc: dict[str, Any] | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.saved_doc = saved_doc
        self.calls: list[dict[str, str]] = []

    async def find_similar(self, conversation_id: str, user_id: str, product_id: str, request_id: str = "", product_name: str = "") -> dict[str, Any]:
        self.calls.append({"conversation_id": conversation_id, "user_id": user_id, "product_id": product_id, "request_id": request_id, "product_name": product_name})
        if self.error is not None:
            raise self.error
        return self.result or {}

    @property
    def messages(self) -> "_FakeMessages":
        return _FakeMessages(self.saved_doc)


class _FakeMessages:
    def __init__(self, saved_doc: dict[str, Any] | None) -> None:
        self.saved_doc = saved_doc

    async def find_by_id(self, message_id: str, conversation_id: str) -> dict[str, Any] | None:
        return self.saved_doc


def _saved_doc() -> dict[str, Any]:
    return {
        "_id": "m1",
        "conversationId": "conv-1",
        "role": "assistant",
        "content": "Similar products",
        "status": "completed",
        "tokenCount": 2,
        "productSnapshots": [{"id": "p2", "name": "Similar", "price": 5.0, "currency": "SAR", "brand": "B"}],
        "searchContext": None,
        "debug": None,
        "feedback": None,
        "locale": "en",
        "createdAt": "2026-01-01T00:00:00",
    }


@pytest.fixture
def fake_service(monkeypatch: pytest.MonkeyPatch) -> _FakeSimilarService:
    fake = _FakeSimilarService(result=_saved_doc(), saved_doc=_saved_doc())
    monkeypatch.setattr("app.api.v1.ws.get_chat_service", lambda _app: fake)
    return fake


def test_similar_request_success(monkeypatch: pytest.MonkeyPatch):
    fake = _FakeSimilarService(result=_saved_doc(), saved_doc=_saved_doc())
    monkeypatch.setattr("app.api.v1.ws.get_chat_service", lambda _app: fake)
    token = create_access_token("test-user", role="user")
    app.state.ws_manager = ConnectionManager()
    client = _make_client()
    with client.websocket_connect(f"/api/v1/ws/chat/conv-1?token={token}") as ws:
        ws.send_text('{"type": "similar_request", "product_id": "p1", "product_name": "Dress", "include_saved_message": true}')

        cards = ws.receive_json()
        assert cards["type"] == "product_cards"
        assert cards["products"] == [{"id": "p2", "name": "Similar", "price": 5.0, "currency": "SAR", "brand": "B"}]
        assert cards["locale"] == "en"

        end = ws.receive_json()
        assert end == {"type": "assistant_end"}

        saved = ws.receive_json()
        assert saved["type"] == "message_saved"
        assert saved["conversation_id"] == "conv-1"
        assert saved["message"]["id"] == "m1"
        assert saved["user_message"] is None

    assert fake.calls == [{"conversation_id": "conv-1", "user_id": "test-user", "product_id": "p1", "request_id": "ws_test-user", "product_name": "Dress"}]


def test_similar_request_without_saved_message(monkeypatch: pytest.MonkeyPatch):
    fake = _FakeSimilarService(result=_saved_doc())
    monkeypatch.setattr("app.api.v1.ws.get_chat_service", lambda _app: fake)
    token = create_access_token("test-user", role="user")
    app.state.ws_manager = ConnectionManager()
    client = _make_client()
    with client.websocket_connect(f"/api/v1/ws/chat/conv-1?token={token}") as ws:
        ws.send_text('{"type": "similar_request", "product_id": "p1"}')
        ws.receive_json()  # product_cards
        ws.receive_json()  # assistant_end
        saved = ws.receive_json()
        assert saved == {"type": "message_saved", "conversation_id": "conv-1"}
        assert "message" not in saved


def test_similar_request_product_not_found(monkeypatch: pytest.MonkeyPatch):
    fake = _FakeSimilarService(error=NotFoundError("Product not found"))
    monkeypatch.setattr("app.api.v1.ws.get_chat_service", lambda _app: fake)
    token = create_access_token("test-user", role="user")
    app.state.ws_manager = ConnectionManager()
    client = _make_client()
    with client.websocket_connect(f"/api/v1/ws/chat/conv-1?token={token}") as ws:
        ws.send_text('{"type": "similar_request", "product_id": "p1"}')
        response = ws.receive_json()
        assert response == {"type": "error", "code": "product_not_found"}


def test_similar_request_missing_product_id(monkeypatch: pytest.MonkeyPatch):
    fake = _FakeSimilarService(result=_saved_doc())
    monkeypatch.setattr("app.api.v1.ws.get_chat_service", lambda _app: fake)
    token = create_access_token("test-user", role="user")
    app.state.ws_manager = ConnectionManager()
    client = _make_client()
    with client.websocket_connect(f"/api/v1/ws/chat/conv-1?token={token}") as ws:
        ws.send_text('{"type": "similar_request"}')
        response = ws.receive_json()
        assert response == {"type": "error", "code": "missing_product_id", "message": "Missing product_id"}
    assert fake.calls == []


def test_similar_request_generic_failure(monkeypatch: pytest.MonkeyPatch):
    fake = _FakeSimilarService(error=RuntimeError("boom"))
    monkeypatch.setattr("app.api.v1.ws.get_chat_service", lambda _app: fake)
    token = create_access_token("test-user", role="user")
    app.state.ws_manager = ConnectionManager()
    client = _make_client()
    with client.websocket_connect(f"/api/v1/ws/chat/conv-1?token={token}") as ws:
        ws.send_text('{"type": "similar_request", "product_id": "p1"}')
        response = ws.receive_json()
        assert response == {"type": "error", "code": "chat_failed"}
