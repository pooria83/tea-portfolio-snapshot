from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.deps import PaginationParams, get_admin_user
from app.core.error_codes import E
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.core.response import APIResponse, paginated, success
from app.models.user import User
from app.repositories.conversation_repo import ConversationRepo
from app.repositories.message_repo import MessageRepo
from app.repositories.user import UserRepository
from app.schemas.chat import AdminConversationItem, ChatMessageResponse, message_from_doc

router = APIRouter(prefix="/admin/chats", tags=["admin-chats"])


async def _get_chat_db(request: Request) -> AsyncIOMotorDatabase[dict[str, Any]]:
    mongo = getattr(request.app.state, "mongo_db", None)
    db: AsyncIOMotorDatabase[dict[str, Any]] | None = getattr(mongo, "db", None) if mongo else None
    if db is None:
        raise ServiceUnavailableError("Chat history is not available", translation_key=E.CHAT_NOT_AVAILABLE)
    return db


def _admin_service(request: Request, db: AsyncIOMotorDatabase[dict[str, Any]]) -> tuple[ConversationRepo, MessageRepo, async_sessionmaker[AsyncSession] | None]:
    return ConversationRepo(db), MessageRepo(db), getattr(request.app.state, "session_factory", None)


def _user_identifier(u: User) -> str | None:
    if u.email:
        return u.email
    if u.phone:
        return u.phone
    if u.full_name:
        return u.full_name
    return None


async def _resolve_user_identifiers(
    user_ids: list[str],
    session_factory: async_sessionmaker[AsyncSession] | None,
) -> dict[str, str | None]:
    if not user_ids or session_factory is None:
        return {}
    try:
        async with session_factory() as session:
            users = await UserRepository(session).list_by_ids(user_ids)
            return {u.id: _user_identifier(u) for u in users}
    except Exception:
        return {}


def _admin_conversation_item(doc: dict[str, Any], identifiers: dict[str, str | None]) -> AdminConversationItem:
    user_id = doc["userId"]
    return AdminConversationItem(
        id=doc["_id"],
        title=doc.get("title"),
        user_id=user_id,
        user_identifier=identifiers.get(user_id),
        status=doc["status"],
        user_message_count=doc["userMessageCount"],
        summary=doc.get("summary"),
        summary_token_count=doc.get("summaryTokenCount"),
        last_activity_at=doc["lastActivityAt"],
        locale=doc["locale"],
        created_at=doc["createdAt"],
        updated_at=doc["updatedAt"],
    )


@router.get("")
async def list_conversations(
    request: Request,
    params: PaginationParams = Depends(),
    db: AsyncIOMotorDatabase[dict[str, Any]] = Depends(_get_chat_db),
    _admin: User = Depends(get_admin_user),
) -> APIResponse[list[AdminConversationItem]]:
    service = _admin_service(request, db)
    docs, total = await service[0].list_all(params.skip, params.limit)
    identifiers = await _resolve_user_identifiers([d["userId"] for d in docs if d.get("userId")], service[2])
    items = [_admin_conversation_item(d, identifiers) for d in docs]
    return paginated(items, total, params.skip, params.limit)


@router.get("/{conversation_id}/messages")
async def list_conversation_messages(
    conversation_id: str,
    request: Request,
    cursor: str | None = Query(None, max_length=64),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncIOMotorDatabase[dict[str, Any]] = Depends(_get_chat_db),
    _admin: User = Depends(get_admin_user),
) -> APIResponse[list[ChatMessageResponse]]:
    service = _admin_service(request, db)
    conversation = await service[0].find_by_id(conversation_id)
    if conversation is None:
        raise NotFoundError("Conversation not found", translation_key=E.CONVERSATION_NOT_FOUND)
    docs = await service[1].list_by_conversation(conversation_id, cursor=cursor or None, limit=limit)
    return success([message_from_doc(d) for d in docs])
