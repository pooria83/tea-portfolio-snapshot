import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.exceptions import NotFoundError
from app.services.chat_service import ChatService


class _FakeConversations:
    def __init__(self, doc: dict[str, Any] | None) -> None:
        self.doc = doc

    async def claim_message_slot(self, conversation_id: str, user_id: str) -> dict[str, Any] | None:
        return self.doc

    async def find_by_id_and_user(self, conversation_id: str, user_id: str) -> dict[str, Any] | None:
        return self.doc

    async def find_by_id(self, conversation_id: str) -> dict[str, Any] | None:
        return self.doc

    async def update_locale(self, conversation_id: str, locale: str) -> None:
        return None


class _FakeMessages:
    def __init__(self) -> None:
        self.created: list[tuple[object, ...]] = []
        self.created_kwargs: list[dict[str, Any]] = []

    async def find_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        return None

    async def list_all_before(self, conversation_id: str) -> list[dict[str, Any]]:
        return []

    async def create(self, *args: object, **kwargs: object) -> dict[str, Any]:
        self.created.append(args)
        self.created_kwargs.append(dict(kwargs))
        conversation_id = str(args[0]) if args else "c1"
        role = str(args[1]) if len(args) > 1 else "user"
        content = str(args[2]) if len(args) > 2 else ""
        return {
            "_id": "m1",
            "conversationId": conversation_id,
            "role": role,
            "content": content,
            "status": str(kwargs.get("status") or "completed"),
            "tokenCount": kwargs.get("token_count"),
            "productSnapshots": kwargs.get("product_snapshots") or [],
            "searchContext": kwargs.get("search_context"),
            "debug": kwargs.get("debug"),
            "error": kwargs.get("error"),
            "locale": kwargs.get("locale"),
            "createdAt": datetime.now(UTC),
        }

    async def find_first_user_message(self, conversation_id: str) -> dict[str, Any] | None:
        return None


class _FakeAI:
    def __init__(self, frames: list[dict[str, Any]] | None = None, error: Exception | None = None) -> None:
        self.frames = frames or []
        self.error = error
        self.last: dict[str, Any] | None = None

    async def chat_conversational_stream(self, **kwargs: Any) -> AsyncIterator[str]:
        self.last = kwargs
        if self.error is not None:
            raise self.error
        for f in self.frames:
            yield json.dumps(f)

    async def title(self, *args: object, **kwargs: object) -> dict[str, Any]:
        return {"title": ""}


def _service(ai: _FakeAI) -> tuple[ChatService, _FakeMessages]:
    svc = ChatService.__new__(ChatService)
    svc.conversations = _FakeConversations(  # type: ignore[assignment]
        {"_id": "c1", "userId": "u1", "status": "active", "locale": "en", "summary": "", "title": None}
    )
    messages = _FakeMessages()
    svc.messages = messages  # type: ignore[assignment]
    svc.ai_client = ai  # type: ignore[assignment]
    svc.session_factory = None
    return svc, messages


async def test_send_message_stream_yields_frames_and_final_saved():
    ai = _FakeAI(
        frames=[
            {"type": "assistant_start", "search_context": {"query": "Hi", "filters": {}, "tool_used": True, "intent": "search"}},
            {"type": "product_cards", "products": [{"id": "p1", "name": "Dress", "price": 99.0}]},
            {"type": "text_chunk", "delta": "Hello "},
            {"type": "text_chunk", "delta": "world"},
            {"type": "assistant_end"},
        ]
    )
    svc, messages = _service(ai)

    frames = [frame async for frame in svc.send_message_stream("u1", "c1", "Hi", idempotency_key="k1", request_id="r1")]

    assert [f["type"] for f in frames] == [
        "assistant_start",
        "product_cards",
        "text_chunk",
        "text_chunk",
        "assistant_end",
        "message_saved",
    ]
    assert frames[-1]["message_id"] == "m1"
    assert frames[-1]["conversation_id"] == "c1"
    assert ai.last is not None
    assert ai.last["request_id"] == "r1"
    assert ai.last["user_id"] == "u1"
    assert len(messages.created) == 2  # user + assistant
    assistant_args = messages.created[1]
    assistant_kwargs = messages.created_kwargs[1]
    assert assistant_args[1] == "assistant"
    assert assistant_args[2] == "Hello world"
    assert assistant_kwargs["product_snapshots"][0]["id"] == "p1"
    assert assistant_kwargs["search_context"]["intent"] == "search"


async def test_send_message_stream_message_saved_carries_saved_messages():
    ai = _FakeAI(frames=[{"type": "text_chunk", "delta": "ok"}, {"type": "assistant_end"}])
    svc, _ = _service(ai)

    frames = [frame async for frame in svc.send_message_stream("u1", "c1", "Hi", include_saved_message=True)]

    saved = frames[-1]
    assert saved["type"] == "message_saved"
    assert saved["message"]["role"] == "assistant"
    assert saved["message"]["content"] == "ok"
    assert saved["message"]["status"] == "completed"
    assert saved["user_message"]["role"] == "user"
    assert saved["user_message"]["content"] == "Hi"
    assert saved["user_message"]["conversation_id"] == "c1"


async def test_send_message_stream_engine_failure_persists_failed_and_yields_error():
    ai = _FakeAI(error=RuntimeError("boom"))
    svc, messages = _service(ai)

    frames = [frame async for frame in svc.send_message_stream("u1", "c1", "Hi", include_saved_message=True)]

    assert [f["type"] for f in frames] == ["error", "message_saved"]
    assert frames[0] == {"type": "error", "code": "chat_failed"}
    saved = frames[1]
    assert saved["message"]["status"] == "failed"
    assert saved["message"]["content"] == ""
    assert saved["message"]["error"] == "chat_failed"
    assert saved["message"]["search_context"]["intent"] == "error"
    assert saved["user_message"]["content"] == "Hi"
    assistant_args = messages.created[-1]
    assistant_kwargs = messages.created_kwargs[-1]
    assert assistant_args[1] == "assistant"
    assert assistant_args[2] == ""
    assert assistant_kwargs["status"] == "failed"
    assert assistant_kwargs["error"] == "chat_failed"
    assert assistant_kwargs["search_context"] == {"intent": "error"}


async def test_send_message_stream_error_frame_persists_error_code_and_intent():
    ai = _FakeAI(frames=[{"type": "error", "code": "embedding_failed"}])
    svc, messages = _service(ai)

    frames = [frame async for frame in svc.send_message_stream("u1", "c1", "Hi", include_saved_message=True)]

    assert [f["type"] for f in frames] == ["error", "message_saved"]
    assert frames[0] == {"type": "error", "code": "embedding_failed"}
    saved = frames[1]
    assert saved["message"]["status"] == "failed"
    assert saved["message"]["content"] == ""
    assert saved["message"]["error"] == "embedding_failed"
    assert saved["message"]["search_context"]["intent"] == "error"
    assistant_kwargs = messages.created_kwargs[-1]
    assert assistant_kwargs["status"] == "failed"
    assert assistant_kwargs["error"] == "embedding_failed"
    assert assistant_kwargs["search_context"] == {"intent": "error"}


async def test_send_message_stream_missing_conversation_raises_not_found():
    svc, _ = _service(_FakeAI())
    svc.conversations = _FakeConversations(None)  # type: ignore[assignment]

    with pytest.raises(NotFoundError):
        async for _ in svc.send_message_stream("u1", "c1", "Hi"):
            pass
