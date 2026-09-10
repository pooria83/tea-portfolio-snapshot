import json
import warnings
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.jwt import create_access_token
from app.main import app

CONVERSATIONS = "conversations"
MESSAGES = "messages"


def _make_ws_client():
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient`")
        from starlette.testclient import TestClient

        return TestClient(app, backend="asyncio")


def _frames(ws) -> list[dict]:
    frames = []
    while True:
        frame = ws.receive_json()
        frames.append(frame)
        if frame.get("type") == "message_saved":
            break
    return frames


async def _create_conversation(client: AsyncClient, auth_headers: dict[str, str]) -> str:
    resp = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _user_token(user_id: str) -> str:
    return create_access_token(user_id, role="user")


@pytest.fixture(autouse=True)
def _no_pg_in_ws_tests(db_session, monkeypatch) -> None:
    monkeypatch.setattr(app.state, "session_factory", None)


async def test_chat_stream_relays_frames_and_persists(client: AsyncClient, auth_headers: dict[str, str], test_user) -> None:
    engine = app.state.ai_client

    async def fake_stream(query, locale, history, summary, request_id, user_id, system_prompt=None, parse_prompt=None):
        frames = [
            {"type": "assistant_start", "search_context": {"query": query, "filters": {}, "tool_used": True, "intent": "search"}},
            {"type": "product_cards", "products": [{"id": "p1", "name": "Dress", "price": 99.0}]},
            {"type": "text_chunk", "delta": "Hello "},
            {"type": "text_chunk", "delta": "world"},
            {"type": "assistant_end"},
        ]
        for f in frames:
            yield json.dumps(f)

    engine.chat_conversational_stream = MagicMock(side_effect=fake_stream)
    conv_id = await _create_conversation(client, auth_headers)
    token = _user_token(test_user.id)

    ws_client = _make_ws_client()
    with ws_client.websocket_connect(f"/api/v1/ws/chat/{conv_id}?token={token}") as ws:
        ws.send_json({"type": "send_message", "content": "Hi", "idempotency_key": "k1", "include_saved_message": True})
        frames = _frames(ws)

    assert [f["type"] for f in frames] == [
        "assistant_start",
        "product_cards",
        "text_chunk",
        "text_chunk",
        "assistant_end",
        "message_saved",
    ]
    assert frames[0]["search_context"]["tool_used"] is True
    assert frames[0]["search_context"]["intent"] == "search"
    assert frames[2]["delta"] == "Hello "
    assert frames[5]["conversation_id"] == conv_id
    assert frames[5]["message"]["search_context"]["intent"] == "search"

    messages = await app.state.mongo_db.db[MESSAGES].find({"conversationId": conv_id}).to_list(length=100)
    by_role = {m["role"]: m for m in messages}
    assert by_role["user"]["content"] == "Hi"
    assert by_role["assistant"]["content"] == "Hello world"
    assert by_role["assistant"]["productSnapshots"][0]["id"] == "p1"
    assert by_role["assistant"]["searchContext"]["query"] == "Hi"
    assert by_role["assistant"]["searchContext"]["intent"] == "search"
    assert by_role["assistant"]["status"] == "completed"

    engine.chat_conversational_stream.assert_called_once()


async def test_chat_stream_product_cards_enriched_with_localized_names(client: AsyncClient, auth_headers: dict[str, str], test_user, monkeypatch) -> None:
    class _FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, statement):
            return _FakeResult([("p1", "توب أزرق", "Blue Top", None, "زارا", "Zara", None)])

    monkeypatch.setattr(app.state, "session_factory", lambda: _FakeSession())
    monkeypatch.setattr(settings, "minio_public_url", "https://portfolio.example.invalid")

    engine = app.state.ai_client

    async def fake_stream(query, locale, history, summary, request_id, user_id, system_prompt=None, parse_prompt=None):
        yield json.dumps({"type": "product_cards", "products": [{"id": "p1", "name": "Blue Top", "brand": "Zara", "image_url": "https://portfolio.example.invalid/product-graph/products/p1/img.jpg"}]})
        yield json.dumps({"type": "text_chunk", "delta": "ok"})
        yield json.dumps({"type": "assistant_end"})

    engine.chat_conversational_stream = MagicMock(side_effect=fake_stream)
    conv_id = await _create_conversation(client, auth_headers)
    token = _user_token(test_user.id)

    ws_client = _make_ws_client()
    with ws_client.websocket_connect(f"/api/v1/ws/chat/{conv_id}?token={token}") as ws:
        ws.send_json({"type": "send_message", "content": "Hi"})
        frames = _frames(ws)

    cards_frame = next(f for f in frames if f["type"] == "product_cards")
    assert cards_frame["products"][0]["name_ar"] == "توب أزرق"
    assert cards_frame["products"][0]["brand_ar"] == "زارا"
    assert "portfolio.example.invalid" not in cards_frame["products"][0]["image_url"]

    messages = await app.state.mongo_db.db[MESSAGES].find({"conversationId": conv_id}).to_list(length=100)
    assistant = {m["role"]: m for m in messages}["assistant"]
    snapshot = assistant["productSnapshots"][0]
    assert snapshot["name_ar"] == "توب أزرق"
    assert snapshot["brand_ar"] == "زارا"
    assert "portfolio.example.invalid" not in snapshot["image_url"]
    assert assistant["locale"] == "en"


async def test_chat_stream_persists_arabic_message_locale(client: AsyncClient, auth_headers: dict[str, str], test_user) -> None:
    engine = app.state.ai_client

    async def fake_stream(query, locale, history, summary, request_id, user_id, system_prompt=None, parse_prompt=None):
        assert locale == "ar"
        yield json.dumps({"type": "product_cards", "products": []})
        yield json.dumps({"type": "text_chunk", "delta": "تمام"})
        yield json.dumps({"type": "assistant_end"})

    engine.chat_conversational_stream = MagicMock(side_effect=fake_stream)
    conv_id = await _create_conversation(client, auth_headers)
    token = _user_token(test_user.id)

    ws_client = _make_ws_client()
    with ws_client.websocket_connect(f"/api/v1/ws/chat/{conv_id}?token={token}") as ws:
        ws.send_json({"type": "send_message", "content": "أريد توب نسائي أنيق"})
        _frames(ws)

    messages = await app.state.mongo_db.db[MESSAGES].find({"conversationId": conv_id}).to_list(length=100)
    assistant = {m["role"]: m for m in messages}["assistant"]
    user_message = {m["role"]: m for m in messages}["user"]
    assert assistant["locale"] == "ar"
    assert user_message.get("locale") is None


async def test_chat_stream_unknown_conversation_error(client: AsyncClient, auth_headers: dict[str, str], test_user) -> None:
    token = _user_token(test_user.id)
    ws_client = _make_ws_client()
    with ws_client.websocket_connect(f"/api/v1/ws/chat/{uuid4()}?token={token}") as ws:
        ws.send_json({"type": "send_message", "content": "Hi"})
        frame = ws.receive_json()
        assert frame == {"type": "error", "code": "conversation_not_found"}


async def test_chat_stream_closed_conversation_error(client: AsyncClient, auth_headers: dict[str, str], test_user) -> None:
    conv_id = await _create_conversation(client, auth_headers)
    await app.state.mongo_db.db[CONVERSATIONS].update_one({"_id": conv_id}, {"$set": {"status": "closed"}})
    token = _user_token(test_user.id)
    ws_client = _make_ws_client()
    with ws_client.websocket_connect(f"/api/v1/ws/chat/{conv_id}?token={token}") as ws:
        ws.send_json({"type": "send_message", "content": "Hi"})
        frame = ws.receive_json()
        assert frame == {"type": "error", "code": "conversation_closed"}


async def test_chat_stream_engine_failure_persists_failed(client: AsyncClient, auth_headers: dict[str, str], test_user) -> None:
    engine = app.state.ai_client
    engine.chat_conversational_stream = MagicMock(side_effect=RuntimeError("boom"))
    conv_id = await _create_conversation(client, auth_headers)
    token = _user_token(test_user.id)

    ws_client = _make_ws_client()
    with ws_client.websocket_connect(f"/api/v1/ws/chat/{conv_id}?token={token}") as ws:
        ws.send_json({"type": "send_message", "content": "Hi"})
        frames = _frames(ws)

    assert frames[0] == {"type": "error", "code": "chat_failed"}
    assert frames[1]["type"] == "message_saved"
    assert frames[1]["conversation_id"] == conv_id
    assert frames[1]["message_id"]
    assert "message" not in frames[1]
    assert "user_message" not in frames[1]
    messages = await app.state.mongo_db.db[MESSAGES].find({"conversationId": conv_id}).to_list(length=100)
    by_role = {m["role"]: m for m in messages}
    assert by_role["user"]["content"] == "Hi"
    assert by_role["assistant"]["status"] == "failed"
    assert by_role["assistant"]["content"] == ""


async def test_chat_stream_unauthenticated(client: AsyncClient) -> None:
    from fastapi import WebSocketDisconnect

    ws_client = _make_ws_client()
    with pytest.raises(WebSocketDisconnect), ws_client.websocket_connect(f"/api/v1/ws/chat/{uuid4()}"):
        pass


async def test_chat_stream_sets_title_on_first_message(client: AsyncClient, auth_headers: dict[str, str], test_user) -> None:
    engine = app.state.ai_client
    engine.title = AsyncMock(return_value={"title": "Red dresses"})

    async def fake_stream(query, locale, history, summary, request_id, user_id, system_prompt=None, parse_prompt=None):
        yield json.dumps({"type": "text_chunk", "delta": "ok"})
        yield json.dumps({"type": "assistant_end"})

    engine.chat_conversational_stream = MagicMock(side_effect=fake_stream)
    conv_id = await _create_conversation(client, auth_headers)
    token = _user_token(test_user.id)

    ws_client = _make_ws_client()
    with ws_client.websocket_connect(f"/api/v1/ws/chat/{conv_id}?token={token}") as ws:
        ws.send_json({"type": "send_message", "content": "i want red ones", "idempotency_key": "k1"})
        _frames(ws)
        ws.send_json({"type": "send_message", "content": "short please", "idempotency_key": "k2"})
        _frames(ws)

    engine.title.assert_awaited_once()
    assert engine.title.await_args.args[0] == "i want red ones"
    conv = await app.state.mongo_db.db[CONVERSATIONS].find_one({"_id": conv_id})
    assert conv["title"] == "Red dresses"


async def test_chat_stream_message_saved_includes_serializable_message(client: AsyncClient, auth_headers: dict[str, str], test_user) -> None:
    engine = app.state.ai_client

    async def fake_stream(query, locale, history, summary, request_id, user_id, system_prompt=None, parse_prompt=None):
        yield json.dumps({"type": "text_chunk", "delta": "ok"})
        yield json.dumps({"type": "assistant_end"})

    engine.chat_conversational_stream = MagicMock(side_effect=fake_stream)
    conv_id = await _create_conversation(client, auth_headers)
    token = _user_token(test_user.id)

    ws_client = _make_ws_client()
    with ws_client.websocket_connect(f"/api/v1/ws/chat/{conv_id}?token={token}") as ws:
        ws.send_json(
            {
                "type": "send_message",
                "content": "i want red ones",
                "idempotency_key": "k-serializable",
                "include_saved_message": True,
            }
        )
        frames = _frames(ws)

    saved = next(f for f in frames if f["type"] == "message_saved")
    assert saved["conversation_id"] == conv_id
    assert isinstance(saved["message"], dict)
    assert saved["message"]["role"] == "assistant"
    assert saved["message"]["content"] == "ok"
    assert saved["message"]["conversation_id"] == conv_id
    assert saved["message"]["status"] == "completed"
    assert saved["user_message"]["role"] == "user"
    assert saved["user_message"]["content"] == "i want red ones"
    assert saved["user_message"]["conversation_id"] == conv_id


async def test_chat_stream_engine_failure_message_saved_carries_failed_message(client: AsyncClient, auth_headers: dict[str, str], test_user) -> None:
    engine = app.state.ai_client
    engine.chat_conversational_stream = MagicMock(side_effect=RuntimeError("boom"))
    conv_id = await _create_conversation(client, auth_headers)
    token = _user_token(test_user.id)

    ws_client = _make_ws_client()
    with ws_client.websocket_connect(f"/api/v1/ws/chat/{conv_id}?token={token}") as ws:
        ws.send_json({"type": "send_message", "content": "Hi", "include_saved_message": True})
        frames = _frames(ws)

    assert [f["type"] for f in frames] == ["error", "message_saved"]
    assert frames[0] == {"type": "error", "code": "chat_failed"}
    assert frames[1]["message"]["status"] == "failed"
    assert frames[1]["user_message"]["content"] == "Hi"
    messages = await app.state.mongo_db.db[MESSAGES].find({"conversationId": conv_id}).to_list(length=100)
    by_role = {m["role"]: m for m in messages}
    assert by_role["user"]["content"] == "Hi"
    assert by_role["assistant"]["status"] == "failed"
    assert by_role["assistant"]["content"] == ""


@pytest.mark.parametrize(
    ("frame", "expected_code"),
    [
        ({"type": "send_message", "content": ""}, "empty_content"),
        ({"type": "send_message"}, "empty_content"),
        ({"type": "bogus_frame"}, "unsupported_frame"),
        ({"type": "send_message", "content": "x" * 20000}, "message_too_large"),
    ],
)
async def test_chat_stream_validation_errors_carry_codes(client: AsyncClient, auth_headers: dict[str, str], test_user, frame: dict, expected_code: str) -> None:
    token = _user_token(test_user.id)
    ws_client = _make_ws_client()
    with ws_client.websocket_connect(f"/api/v1/ws/chat/{uuid4()}?token={token}") as ws:
        ws.send_json(frame)
        response = ws.receive_json()
        assert response["type"] == "error"
        assert response["code"] == expected_code


async def test_chat_stream_persists_debug_frame_and_returns_from_history(client: AsyncClient, auth_headers: dict[str, str], test_user) -> None:
    engine = app.state.ai_client

    async def fake_stream(query, locale, history, summary, request_id, user_id, system_prompt=None, parse_prompt=None):
        frames = [
            {
                "type": "debug",
                "debug": {
                    "prompt": {"model": "m", "messages": [{"role": "user", "content": "Hi"}]},
                    "response": {"choices": [{"message": {"content": "{}"}}]},
                },
            },
            {"type": "assistant_start", "search_context": {"rewritten_query": "Hi", "filters": {}, "tool_used": False}},
            {"type": "text_chunk", "delta": "answer"},
            {"type": "assistant_end"},
        ]
        for f in frames:
            yield json.dumps(f)

    engine.chat_conversational_stream = MagicMock(side_effect=fake_stream)
    conv_id = await _create_conversation(client, auth_headers)
    token = _user_token(test_user.id)

    ws_client = _make_ws_client()
    with ws_client.websocket_connect(f"/api/v1/ws/chat/{conv_id}?token={token}") as ws:
        ws.send_json({"type": "send_message", "content": "Hi"})
        frames = _frames(ws)

    assert frames[0]["type"] == "debug"
    assert frames[0]["debug"]["prompt"]["messages"][0]["content"] == "Hi"

    messages = await app.state.mongo_db.db[MESSAGES].find({"conversationId": conv_id}).to_list(length=100)
    assistant = next(m for m in messages if m["role"] == "assistant")
    assert assistant["debug"]["prompt"]["model"] == "m"
    assert assistant["debug"]["response"]["choices"][0]["message"]["content"] == "{}"

    resp = await client.get(f"/api/v1/chats/{conv_id}/messages", headers=auth_headers)
    assert resp.status_code == 200
    from_history = next(m for m in resp.json() if m["role"] == "assistant")
    assert from_history["debug"]["prompt"]["model"] == "m"
    assert from_history["debug"]["response"] == {"choices": [{"message": {"content": "{}"}}]}
