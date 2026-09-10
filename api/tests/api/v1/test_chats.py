from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from httpx import AsyncClient

from app.core.config import settings
from app.main import app

CONVERSATIONS = "conversations"
MESSAGES = "messages"


async def _collection(client: AsyncClient, name: str):
    return app.state.mongo_db.db[name]


async def test_create_conversation_returns_same_active(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    resp1 = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    assert resp1.status_code == 201
    conv1 = resp1.json()
    assert conv1["status"] == "active"
    assert conv1["user_message_count"] == 0

    resp2 = await client.post("/api/v1/chats", json={"locale": "ar"}, headers=auth_headers)
    assert resp2.status_code == 201
    assert resp2.json()["id"] == conv1["id"]


async def test_list_conversations_paginated(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    resp = await client.get("/api/v1/chats", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) == 1
    assert items[0]["id"]


async def test_send_message_persists_both_roles(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "Hello there", "products": [{"id": "p1", "name": "Dress", "price": 99.0}]})

    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]

    resp = await client.post(
        f"/api/v1/chats/{conv_id}/messages",
        json={"content": "Hi", "idempotency_key": "key-1"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    turn = resp.json()
    assert turn["user_message"]["role"] == "user"
    assert turn["user_message"]["content"] == "Hi"
    assert turn["assistant_message"]["role"] == "assistant"
    assert turn["assistant_message"]["content"] == "Hello there"
    assert turn["assistant_message"]["product_snapshots"][0]["id"] == "p1"

    engine.chat_conversational.assert_awaited_once()
    assert engine.chat_conversational.await_args is not None
    kwargs = engine.chat_conversational.await_args.kwargs
    assert kwargs["query"] == "Hi"
    assert kwargs["summary"] == ""
    assert kwargs["history"] == []


async def test_send_message_persists_debug(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(
        return_value={
            "answer": "ok",
            "products": [],
            "debug": {
                "prompt": {"model": "m", "messages": [{"role": "user", "content": "Hi"}]},
                "response": {"choices": [{"message": {"content": "{}"}}]},
            },
        }
    )

    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]

    resp = await client.post(
        f"/api/v1/chats/{conv_id}/messages",
        json={"content": "Hi"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assistant = resp.json()["assistant_message"]
    assert assistant["debug"]["prompt"]["model"] == "m"
    assert assistant["debug"]["response"] == {"choices": [{"message": {"content": "{}"}}]}


async def test_send_message_includes_history_and_summary(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "first answer", "products": []})

    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "first"}, headers=auth_headers)

    conv = await app.state.mongo_db.db[CONVERSATIONS].find_one({"_id": conv_id})
    await app.state.mongo_db.db[CONVERSATIONS].update_one({"_id": conv_id}, {"$set": {"summary": "summary-so-far"}})

    resp = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "second"}, headers=auth_headers)
    assert resp.status_code == 201
    assert engine.chat_conversational.await_args is not None
    kwargs = engine.chat_conversational.await_args.kwargs
    assert kwargs["summary"] == "summary-so-far"
    assert kwargs["history"] == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "first answer"},
    ]
    assert conv["userMessageCount"] == 1


async def test_message_limit_reached(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    await app.state.mongo_db.db[CONVERSATIONS].update_one({"_id": conv_id}, {"$set": {"userMessageCount": settings.chat_max_messages}})

    resp = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "one more"}, headers=auth_headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["translation_key"] == "chat_limit_reached"


async def test_conversation_auto_closes_at_cap(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "ok", "products": []})
    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    await app.state.mongo_db.db[CONVERSATIONS].update_one({"_id": conv_id}, {"$set": {"userMessageCount": settings.chat_max_messages - 1}})

    resp = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "last"}, headers=auth_headers)
    assert resp.status_code == 201
    conv = await app.state.mongo_db.db[CONVERSATIONS].find_one({"_id": conv_id})
    assert conv["status"] == "closed"
    assert conv["userMessageCount"] == settings.chat_max_messages


async def test_new_conversation_after_close(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    await app.state.mongo_db.db[CONVERSATIONS].update_one(
        {"_id": conv_id},
        {"$set": {"status": "closed", "userMessageCount": settings.chat_max_messages}},
    )
    resp = await client.post("/api/v1/chats", json={"locale": "ar"}, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["id"] != conv_id
    assert resp.json()["status"] == "active"


async def test_rate_message_sets_feedback(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "Great", "products": []})
    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    turn = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "Hi"}, headers=auth_headers)
    assistant_id = turn.json()["assistant_message"]["id"]

    resp = await client.post(
        f"/api/v1/chats/{conv_id}/messages/{assistant_id}/feedback",
        json={"rating": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["rating"] == 5

    doc = await app.state.mongo_db.db[MESSAGES].find_one({"_id": assistant_id})
    assert doc["feedback"]["rating"] == 5
    assert doc["feedback"]["createdAt"] is not None

    listing = await client.get(f"/api/v1/chats/{conv_id}/messages", headers=auth_headers)
    assistant_listed = next(m for m in listing.json() if m["role"] == "assistant")
    assert assistant_listed["feedback"]["rating"] == 5


async def test_rate_message_invalid_rating(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "Great", "products": []})
    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    turn = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "Hi"}, headers=auth_headers)
    assistant_id = turn.json()["assistant_message"]["id"]

    for bad in (0, 6):
        resp = await client.post(
            f"/api/v1/chats/{conv_id}/messages/{assistant_id}/feedback",
            json={"rating": bad},
            headers=auth_headers,
        )
        assert resp.status_code == 422


async def test_rate_message_not_found(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    resp = await client.post(
        f"/api/v1/chats/{conv_id}/messages/{uuid4()}/feedback",
        json={"rating": 4},
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["translation_key"] == "message_not_found"


async def test_rate_message_user_message_rejected(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "Great", "products": []})
    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    turn = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "Hi"}, headers=auth_headers)
    user_message_id = turn.json()["user_message"]["id"]

    resp = await client.post(
        f"/api/v1/chats/{conv_id}/messages/{user_message_id}/feedback",
        json={"rating": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 404


async def test_closed_conversation_rejected(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    await app.state.mongo_db.db[CONVERSATIONS].update_one({"_id": conv_id}, {"$set": {"status": "closed"}})

    resp = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "hello"}, headers=auth_headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["translation_key"] == "conversation_closed"


async def test_messages_paginated_with_cursor(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    for i in range(5):
        await app.state.mongo_db.db[MESSAGES].insert_one(
            {
                "_id": str(uuid4()),
                "conversationId": conv_id,
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"msg {i}",
                "status": "completed",
                "tokenCount": 1,
                "productSnapshots": [],
                "createdAt": datetime.now(UTC),
            }
        )

    resp = await client.get(f"/api/v1/chats/{conv_id}/messages?limit=3", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3


async def test_unknown_conversation_404(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    resp = await client.get(f"/api/v1/chats/{uuid4()}/messages", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["translation_key"] == "conversation_not_found"


async def test_delete_conversation_soft(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]

    resp = await client.delete(f"/api/v1/chats/{conv_id}", headers=auth_headers)
    assert resp.status_code == 204

    doc = await app.state.mongo_db.db[CONVERSATIONS].find_one({"_id": conv_id})
    assert doc["deletedAt"] is not None
    assert doc["status"] == "closed"

    resp = await client.get(f"/api/v1/chats/{conv_id}/messages", headers=auth_headers)
    assert resp.status_code == 404


async def test_chat_unavailable_without_mongo(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    original = app.state.mongo_db
    app.state.mongo_db = SimpleNamespace(db=None)
    try:
        resp = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
        assert resp.status_code == 503
        assert resp.json()["error"]["translation_key"] == "chat_not_available"
    finally:
        app.state.mongo_db = original


async def test_send_message_triggers_compaction(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "ok", "products": []})
    engine.summarize = AsyncMock(return_value={"summary": "rolled-up", "tokens_used": 42})

    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    await app.state.mongo_db.db[CONVERSATIONS].update_one({"_id": conv_id}, {"$set": {"summary": "old-summary"}})
    for i in range(settings.chat_compact_threshold_tokens // 100 + 10):
        await app.state.mongo_db.db[MESSAGES].insert_one(
            {
                "_id": str(uuid4()),
                "conversationId": conv_id,
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"bulk {i}",
                "status": "completed",
                "tokenCount": 100,
                "productSnapshots": [],
                "createdAt": datetime.now(UTC),
            }
        )

    resp = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "Hi"}, headers=auth_headers)
    assert resp.status_code == 201
    assert engine.summarize.await_count == 1

    conv = await app.state.mongo_db.db[CONVERSATIONS].find_one({"_id": conv_id})
    assert conv["summary"] == "rolled-up"
    assert conv["summarizedMessageCount"] > 0
    assert conv["summaryTokenCount"] == 42


async def test_send_message_skips_compaction_below_threshold(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "ok", "products": []})
    engine.summarize = AsyncMock()

    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    resp = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "Hi"}, headers=auth_headers)
    assert resp.status_code == 201
    engine.summarize.assert_not_awaited()


async def test_compaction_failure_does_not_fail_turn(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "ok", "products": []})
    engine.summarize = AsyncMock(side_effect=RuntimeError("boom"))

    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    await app.state.mongo_db.db[CONVERSATIONS].update_one({"_id": conv_id}, {"$set": {"summary": "s"}})
    for i in range(settings.chat_compact_threshold_tokens // 100 + 10):
        await app.state.mongo_db.db[MESSAGES].insert_one(
            {
                "_id": str(uuid4()),
                "conversationId": conv_id,
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"bulk {i}",
                "status": "completed",
                "tokenCount": 100,
                "productSnapshots": [],
                "createdAt": datetime.now(UTC),
            }
        )

    resp = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "Hi"}, headers=auth_headers)
    assert resp.status_code == 201


async def test_send_message_sets_title_on_first_message_only(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "ok", "products": []})
    engine.title = AsyncMock(return_value={"title": "Short dresses"})

    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]

    resp = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "i want short dress"}, headers=auth_headers)
    assert resp.status_code == 201
    engine.title.assert_awaited_once()
    assert engine.title.await_args.args[0] == "i want short dress"
    assert engine.title.await_args.kwargs["locale"] == "en"

    conv = await app.state.mongo_db.db[CONVERSATIONS].find_one({"_id": conv_id})
    assert conv["title"] == "Short dresses"

    resp = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "red ones"}, headers=auth_headers)
    assert resp.status_code == 201
    assert engine.title.await_count == 1


async def test_title_failure_does_not_fail_turn(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "ok", "products": []})
    engine.title = AsyncMock(side_effect=RuntimeError("boom"))

    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]

    resp = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "Hi"}, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["assistant_message"]["content"] == "ok"


async def test_create_new_keeps_previous_active(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    old_id = created.json()["id"]

    resp = await client.post("/api/v1/chats", json={"locale": "en", "create_new": True}, headers=auth_headers)
    assert resp.status_code == 201
    new_id = resp.json()["id"]
    assert new_id != old_id
    assert resp.json()["status"] == "active"

    old = await app.state.mongo_db.db[CONVERSATIONS].find_one({"_id": old_id})
    assert old["status"] == "active"
    assert old["deletedAt"] is None

    listed = await client.get("/api/v1/chats", headers=auth_headers)
    assert {c["id"] for c in listed.json()} == {old_id, new_id}


async def test_create_new_false_reuses_most_recent_active(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    first = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    assert first.status_code == 201
    second = await client.post("/api/v1/chats", json={"locale": "en", "create_new": True}, headers=auth_headers)
    second_id = second.json()["id"]

    resumed = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    assert resumed.status_code == 201
    assert resumed.json()["id"] == second_id


async def test_send_message_forwards_active_chat_prompts(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    from app.models.prompt_template import PromptTemplate

    async with app.state.session_factory() as seed_session:
        seed_session.add(PromptTemplate(id=str(uuid4()), type="chat_assistant", content="Custom assistant instructions", is_active=True))
        seed_session.add(PromptTemplate(id=str(uuid4()), type="parse_query", content="Custom parser. Query: {raw_query}", is_active=True))
        await seed_session.commit()

    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "ok", "products": []})

    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    resp = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "Hi"}, headers=auth_headers)
    assert resp.status_code == 201

    kwargs = engine.chat_conversational.await_args.kwargs
    assert kwargs["system_prompt"] == "Custom assistant instructions"
    assert kwargs["parse_prompt"] == "Custom parser. Query: {raw_query}"


async def test_send_message_forwards_none_prompts_without_rows(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    from sqlalchemy import delete

    from app.models.prompt_template import PromptTemplate

    async with app.state.session_factory() as cleanup:
        await cleanup.execute(delete(PromptTemplate))
        await cleanup.commit()

    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "ok", "products": []})

    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    resp = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "Hi"}, headers=auth_headers)
    assert resp.status_code == 201

    kwargs = engine.chat_conversational.await_args.kwargs
    assert kwargs["system_prompt"] is None
    assert kwargs["parse_prompt"] is None


async def test_compaction_forwards_summarize_prompt(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    from app.models.prompt_template import PromptTemplate

    async with app.state.session_factory() as seed_session:
        seed_session.add(PromptTemplate(id=str(uuid4()), type="summarize", content="Custom summary instructions", is_active=True))
        await seed_session.commit()

    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "ok", "products": []})
    engine.summarize = AsyncMock(return_value={"summary": "rolled-up", "tokens_used": 42})

    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    await app.state.mongo_db.db[CONVERSATIONS].update_one({"_id": conv_id}, {"$set": {"summary": "old-summary"}})
    for i in range(settings.chat_compact_threshold_tokens // 100 + 10):
        await app.state.mongo_db.db[MESSAGES].insert_one(
            {
                "_id": str(uuid4()),
                "conversationId": conv_id,
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"bulk {i}",
                "status": "completed",
                "tokenCount": 100,
                "productSnapshots": [],
                "createdAt": datetime.now(UTC),
            }
        )

    resp = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "Hi"}, headers=auth_headers)
    assert resp.status_code == 201
    assert engine.summarize.await_count == 1
    assert engine.summarize.await_args.kwargs["prompt"] == "Custom summary instructions"


async def test_title_forwards_title_prompt(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    from app.models.prompt_template import PromptTemplate

    async with app.state.session_factory() as seed_session:
        seed_session.add(PromptTemplate(id=str(uuid4()), type="title", content="Custom title instructions", is_active=True))
        await seed_session.commit()

    engine = app.state.ai_client
    engine.chat_conversational = AsyncMock(return_value={"answer": "ok", "products": []})
    engine.title = AsyncMock(return_value={"title": "Short dresses"})

    created = await client.post("/api/v1/chats", json={"locale": "en"}, headers=auth_headers)
    conv_id = created.json()["id"]
    resp = await client.post(f"/api/v1/chats/{conv_id}/messages", json={"content": "i want short dress"}, headers=auth_headers)
    assert resp.status_code == 201
    assert engine.title.await_args.kwargs["prompt"] == "Custom title instructions"
