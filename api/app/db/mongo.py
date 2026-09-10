"""MongoDB (Atlas) connection for chat history.

The API owns chat persistence in MongoDB; product/transaction data stays in
Postgres. The connection is optional: when ``MONGO_URL`` is empty the chat
features degrade gracefully (503 with a translation key) and the rest of the
API is unaffected.
"""

import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Request
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorClientSession, AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.core.config import settings

CONVERSATIONS_COLLECTION = "conversations"
MESSAGES_COLLECTION = "messages"


class MongoDatabase:
    def __init__(self) -> None:
        self.client: AsyncIOMotorClient[dict[str, Any]] | None = None
        self.db: AsyncIOMotorDatabase[dict[str, Any]] | None = None
        self._sessions: set[AsyncIOMotorClientSession] = set()

    @property
    def enabled(self) -> bool:
        return self.db is not None

    async def connect(self) -> None:
        if not settings.mongo_url:
            logger.warning("mongo_url is not set — chat history is disabled")
            return
        self.client = AsyncIOMotorClient(settings.mongo_url, maxPoolSize=10, serverSelectionTimeoutMS=5000)
        assert self.client is not None
        self.db = self.client[settings.mongo_db_name]
        try:
            await self.client.admin.command("ping")
            logger.info("MongoDB connected db={}", settings.mongo_db_name)
        except Exception:
            logger.exception("MongoDB ping failed — chat history is disabled")
            await self.close()
            self.client = None
            self.db = None

    async def close(self) -> None:
        if self._sessions:
            for session in list(self._sessions):
                with contextlib.suppress(Exception):
                    await session.end_session()
            self._sessions.clear()
        if self.client:
            self.client.close()
            self.client = None
            self.db = None

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncIOMotorClientSession]:
        if self.client is None:
            raise RuntimeError("MongoDB is not connected")
        session = await self.client.start_session()
        self._sessions.add(session)
        try:
            yield session
        finally:
            self._sessions.discard(session)
            await session.end_session()

    async def ensure_indexes(self) -> None:
        if not self.enabled:
            return
        conversations = self.collection(CONVERSATIONS_COLLECTION)
        await conversations.create_index([("userId", 1), ("lastActivityAt", -1)])
        await conversations.create_index([("userId", 1), ("status", 1)])
        messages = self.collection(MESSAGES_COLLECTION)
        await messages.create_index([("conversationId", 1), ("createdAt", 1)])
        await messages.create_index([("conversationId", 1), ("createdAt", -1)])
        await messages.create_index([("idempotencyKey", 1)], unique=True, sparse=True)
        logger.info("MongoDB indexes ensured")

    def collection(self, name: str) -> AsyncIOMotorCollection[dict[str, Any]]:
        if not self.enabled or self.db is None:
            raise RuntimeError("MongoDB is not connected")
        return self.db[name]


mongo_db = MongoDatabase()


def get_mongo_db(request: Request) -> AsyncIOMotorDatabase[dict[str, Any]] | None:
    """FastAPI dependency: returns the Mongo DB or None when disabled."""
    mongo: MongoDatabase = request.app.state.mongo_db
    return mongo.db
