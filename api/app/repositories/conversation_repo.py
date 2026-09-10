"""MongoDB repository for chat conversations (no SQLAlchemy)."""

from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.core.config import settings
from app.db.mongo import CONVERSATIONS_COLLECTION

MAX_USER_MESSAGES = settings.chat_max_messages


def _now() -> datetime:
    return datetime.now(UTC)


class ConversationRepo:
    def __init__(self, db: AsyncIOMotorDatabase[dict[str, Any]]) -> None:
        self.collection: AsyncIOMotorCollection[dict[str, Any]] = db[CONVERSATIONS_COLLECTION]

    async def create(self, user_id: str, locale: str, app_version: str = "", need_title: bool = True) -> dict[str, Any]:
        now = _now()
        doc = {
            "_id": str(uuid4()),
            "userId": user_id,
            "status": "active",
            "userMessageCount": 0,
            "summary": "",
            "summaryTokenCount": 0,
            "summarizedMessageCount": 0,
            "locale": locale,
            "appVersion": app_version,
            "needTitle": need_title,
            "lastActivityAt": now,
            "createdAt": now,
            "updatedAt": now,
            "deletedAt": None,
        }
        await self.collection.insert_one(doc)
        return doc

    async def find_active_by_user(self, user_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {"userId": user_id, "status": "active", "deletedAt": None},
            sort=[("lastActivityAt", -1)],
        )

    async def find_by_id_and_user(self, conversation_id: str, user_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"_id": conversation_id, "userId": user_id, "deletedAt": None})

    async def find_by_id(self, conversation_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"_id": conversation_id, "deletedAt": None})

    async def list_by_user(self, user_id: str, skip: int, limit: int) -> tuple[list[dict[str, Any]], int]:
        query = {"userId": user_id, "deletedAt": None}
        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort("lastActivityAt", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return docs, total

    async def list_all(self, skip: int, limit: int) -> tuple[list[dict[str, Any]], int]:
        query = {"deletedAt": None}
        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort("lastActivityAt", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return docs, total

    async def soft_delete(self, conversation_id: str, user_id: str) -> bool:
        result = await self.collection.update_one(
            {"_id": conversation_id, "userId": user_id, "deletedAt": None},
            {"$set": {"deletedAt": _now(), "status": "closed", "updatedAt": _now()}},
        )
        return result.modified_count > 0

    async def update_locale(self, conversation_id: str, locale: str) -> bool:
        result = await self.collection.update_one(
            {"_id": conversation_id, "deletedAt": None},
            {"$set": {"locale": locale, "updatedAt": _now()}},
        )
        return result.modified_count > 0

    async def set_title(self, conversation_id: str, title: str) -> bool:
        result = await self.collection.update_one(
            {"_id": conversation_id, "deletedAt": None},
            {"$set": {"title": title, "updatedAt": _now()}},
        )
        return result.modified_count > 0

    async def touch(self, conversation_id: str) -> None:
        await self.collection.update_one(
            {"_id": conversation_id},
            {"$set": {"lastActivityAt": _now(), "updatedAt": _now()}},
        )

    async def claim_message_slot(self, conversation_id: str, user_id: str) -> dict[str, Any] | None:
        """Atomically increment userMessageCount if the conversation is active
        and below the cap. Returns the updated conversation or None when the
        conversation is missing, closed, or at the cap."""
        now = _now()
        pipeline = [
            {
                "$set": {
                    "userMessageCount": {"$add": ["$userMessageCount", 1]},
                    "lastActivityAt": now,
                    "updatedAt": now,
                    "status": {
                        "$cond": [
                            {"$gte": [{"$add": ["$userMessageCount", 1]}, MAX_USER_MESSAGES]},
                            "closed",
                            "active",
                        ]
                    },
                }
            }
        ]
        return cast(
            "dict[str, Any] | None",
            await self.collection.find_one_and_update(
                {
                    "_id": conversation_id,
                    "userId": user_id,
                    "status": "active",
                    "deletedAt": None,
                    "userMessageCount": {"$lt": MAX_USER_MESSAGES},
                },
                pipeline,
                return_document=ReturnDocument.AFTER,
            ),
        )

    async def record_summary(
        self,
        conversation_id: str,
        summary: str,
        summary_token_count: int,
        summarized_message_count: int,
    ) -> None:
        await self.collection.update_one(
            {"_id": conversation_id},
            {"$set": {"summary": summary, "summaryTokenCount": summary_token_count, "summarizedMessageCount": summarized_message_count, "updatedAt": _now()}},
        )
