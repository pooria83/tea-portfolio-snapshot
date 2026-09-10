"""Shared dependencies for chat endpoints and WebSocket handlers."""

from typing import Any, cast

from fastapi import FastAPI, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.error_codes import E
from app.core.exceptions import ServiceUnavailableError
from app.services.chat_service import ChatService


def get_mongo_db(app: FastAPI) -> AsyncIOMotorDatabase[dict[str, Any]]:
    """Resolve the chat history database from app state, or raise."""
    mongo = getattr(app.state, "mongo_db", None)
    db: AsyncIOMotorDatabase[dict[str, Any]] | None = getattr(mongo, "db", None) if mongo else None
    if db is None:
        raise ServiceUnavailableError("Chat history is not available", translation_key=E.CHAT_NOT_AVAILABLE)
    return db


def get_chat_service(app: FastAPI) -> ChatService:
    """Build a ChatService bound to app state, always wired with the DB session
    factory so product-name enrichment and context budgets work on every path
    (REST and WebSocket)."""
    return ChatService(
        get_mongo_db(app),
        cast(Any, app.state.ai_client),
        getattr(app.state, "session_factory", None),
        getattr(app.state, "redis", None),
    )


async def get_mongo_db_dep(request: Request) -> AsyncIOMotorDatabase[dict[str, Any]]:
    """FastAPI dependency wrapper for REST routes."""
    return get_mongo_db(request.app)
