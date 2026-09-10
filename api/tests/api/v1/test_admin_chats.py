from unittest.mock import AsyncMock
from uuid import uuid4

from httpx import AsyncClient

from app.main import app

CONVERSATIONS = "conversations"
MESSAGES = "messages"


async def test_admin_list_conversations(client: AsyncClient, auth_headers: dict[str, str], admin_headers: dict[str, str]) -> None:
    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "ok", "products": []})
    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "Hi"}, headers=auth_headers)
    await app.state.mongo_db.db[CONVERSATIONS].update_one({"_id": conv_id}, {"$set": {"summary": "rolling summary"}})

    resp = await client.get("/api/v1/admin/chats", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["meta"]["total"] >= 1
    items = body["data"]
    assert len(items) >= 1
    item = next(c for c in items if c["id"] == conv_id)
    assert item["user_message_count"] == 1
    assert item["summary"] == "rolling summary"
    assert item["status"] == "active"
    assert item["user_id"]


async def test_admin_list_conversations_requires_admin(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    resp = await client.get("/api/v1/admin/chats", headers=auth_headers)
    assert resp.status_code in (401, 403)


async def test_admin_conversation_messages(client: AsyncClient, auth_headers: dict[str, str], admin_headers: dict[str, str]) -> None:
    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "Hello there", "products": [{"id": "p1", "name": "Dress"}]})
    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    turn = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "Hi"}, headers=auth_headers)
    assistant_id = turn.json()["assistant_message"]["id"]
    await client.post(
        f"/api/v1/chats/{conv_id}/messages/{assistant_id}/feedback",
        json={"rating": 4},
        headers=auth_headers,
    )

    resp = await client.get(f"/api/v1/admin/chats/{conv_id}/messages", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    messages = body["data"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assistant = messages[1]
    assert assistant["content"] == "Hello there"
    assert assistant["product_snapshots"][0]["id"] == "p1"
    assert assistant["feedback"]["rating"] == 4


async def test_admin_conversation_messages_404(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    resp = await client.get(f"/api/v1/admin/chats/{uuid4()}/messages", headers=admin_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["translation_key"] == "conversation_not_found"


async def test_admin_conversation_item_has_title(client: AsyncClient, auth_headers: dict[str, str], admin_headers: dict[str, str]) -> None:
    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "ok", "products": []})
    engine.title = AsyncMock(return_value={"title": "Short dresses"})

    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "i want short dress"}, headers=auth_headers)

    resp = await client.get("/api/v1/admin/chats", headers=admin_headers)
    assert resp.status_code == 200
    item = next(c for c in resp.json()["data"] if c["id"] == conv_id)
    assert item["title"] == "Short dresses"
