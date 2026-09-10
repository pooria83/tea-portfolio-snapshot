"""MongoDB repository for chat messages."""

import base64
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.db.mongo import MESSAGES_COLLECTION


def _now() -> datetime:
    return datetime.now(UTC)


def _encode_cursor(doc: dict[str, Any]) -> str:
    created = doc["createdAt"]
    created_iso = created.isoformat() if isinstance(created, datetime) else str(created)
    raw = f"{created_iso}|{doc['_id']}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, str] | None:
    """Decode a compound (createdAt, _id) cursor token.

    Returns None when the token is not in the expected format so callers can
    fall back to treating it as a legacy plain message _id cursor.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        created_iso, message_id = raw.rsplit("|", 1)
        return datetime.fromisoformat(created_iso), message_id
    except Exception:
        return None


class MessageRepo:
    def __init__(self, db: AsyncIOMotorDatabase[dict[str, Any]]) -> None:
        self.collection: AsyncIOMotorCollection[dict[str, Any]] = db[MESSAGES_COLLECTION]

    async def create(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        status: str = "completed",
        token_count: int | None = None,
        product_snapshots: list[dict[str, Any]] | None = None,
        search_context: dict[str, Any] | None = None,
        debug: dict[str, Any] | None = None,
        idempotency_key: str = "",
        error: str | None = None,
        locale: str | None = None,
    ) -> dict[str, Any]:
        doc = {
            "_id": str(uuid4()),
            "conversationId": conversation_id,
            "role": role,
            "content": content,
            "status": status,
            "tokenCount": token_count,
            "productSnapshots": product_snapshots or [],
            "searchContext": search_context,
            "debug": debug,
            "error": error,
            "locale": locale,
            "createdAt": _now(),
        }
        if idempotency_key:
            doc["idempotencyKey"] = idempotency_key
        try:
            await self.collection.insert_one(doc)
        except DuplicateKeyError:
            existing = await self.collection.find_one({"idempotencyKey": idempotency_key}) if idempotency_key else None
            if existing:
                return existing
            raise
        return doc

    async def find_by_id(self, message_id: str, conversation_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"_id": message_id, "conversationId": conversation_id})

    async def find_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"idempotencyKey": idempotency_key})

    async def list_by_conversation(
        self,
        conversation_id: str,
        *,
        cursor: str | None = None,
        limit: int = 50,
        before: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Cursor-paginated messages ordered by (createdAt, _id).

        Uses a compound cursor so pagination stays deterministic even when
        multiple messages share the same createdAt.
        """
        query: dict[str, Any] = {"conversationId": conversation_id}
        if before is not None:
            query["createdAt"] = {"$lt": before}
        elif cursor:
            decoded = _decode_cursor(cursor)
            if decoded is not None:
                created, message_id = decoded
                query["$or"] = [
                    {"createdAt": {"$gt": created}},
                    {"createdAt": created, "_id": {"$gt": message_id}},
                ]
            else:
                query["_id"] = {"$gt": cursor}
        cursor_docs = self.collection.find(query).sort([("createdAt", 1), ("_id", 1)]).limit(limit)
        return await cursor_docs.to_list(length=limit)

    async def list_all_before(self, conversation_id: str, before: datetime | None = None) -> list[dict[str, Any]]:
        """All messages ascending — used for compaction and history build."""
        query: dict[str, Any] = {"conversationId": conversation_id}
        if before is not None:
            query["createdAt"] = {"$lt": before}
        cursor_docs = self.collection.find(query).sort("createdAt", 1)
        return await cursor_docs.to_list(length=None)

    async def find_first_user_message(self, conversation_id: str) -> dict[str, Any] | None:
        """The oldest non-empty user message — used for auto-titling."""
        query: dict[str, Any] = {
            "conversationId": conversation_id,
            "role": "user",
            "content": {"$ne": ""},
        }
        return await self.collection.find_one(query, sort=[("createdAt", 1)])

    async def set_feedback(
        self,
        message_id: str,
        conversation_id: str,
        rating: int,
        comment: str | None = None,
    ) -> dict[str, Any] | None:
        feedback: dict[str, Any] = {"rating": rating, "createdAt": _now()}
        if comment:
            feedback["comment"] = comment
        await self.collection.update_one(
            {"_id": message_id, "conversationId": conversation_id, "role": "assistant"},
            {"$set": {"feedback": feedback}},
        )
        return await self.find_by_id(message_id, conversation_id)


def cursor_from_docs(docs: list[dict[str, Any]]) -> str | None:
    """Compound (createdAt, _id) cursor for forward pagination."""
    if not docs:
        return None
    return _encode_cursor(docs[-1])
