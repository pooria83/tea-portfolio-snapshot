from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.v1.chat_deps import get_chat_service, get_mongo_db_dep
from app.core.deps import PaginationParams, get_authenticated_user
from app.core.error_codes import E
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.schemas.chat import (
    ChatMessageResponse,
    ChatTurnResponse,
    ConversationCreate,
    ConversationResponse,
    FeedbackCreate,
    MessageCreate,
    MessageFeedbackResponse,
    conversation_from_doc,
    message_from_doc,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chats", tags=["chats"])


def _service(request: Request, db: AsyncIOMotorDatabase[dict[str, Any]]) -> ChatService:
    return get_chat_service(request.app)


@router.post("", status_code=201)
async def create_or_get_conversation(
    body: ConversationCreate,
    request: Request,
    db: AsyncIOMotorDatabase[dict[str, Any]] = Depends(get_mongo_db_dep),
    user: User = Depends(get_authenticated_user),
) -> ConversationResponse:
    service = _service(request, db)
    if body.create_new:
        conversation = await service.conversations.create(user.id, body.locale, body.app_version, need_title=body.need_title)
    else:
        conversation = await service.ensure_active_conversation(user.id, body.locale, body.app_version, need_title=body.need_title)
    return conversation_from_doc(conversation)


@router.get("")
async def list_conversations(
    request: Request,
    params: PaginationParams = Depends(),
    db: AsyncIOMotorDatabase[dict[str, Any]] = Depends(get_mongo_db_dep),
    user: User = Depends(get_authenticated_user),
) -> list[ConversationResponse]:
    service = _service(request, db)
    docs, _total = await service.conversations.list_by_user(user.id, params.skip, params.limit)
    return [conversation_from_doc(d) for d in docs]


@router.get("/{conversation_id}/messages")
async def list_messages(
    conversation_id: str,
    request: Request,
    cursor: str | None = Query(None, max_length=64),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncIOMotorDatabase[dict[str, Any]] = Depends(get_mongo_db_dep),
    user: User = Depends(get_authenticated_user),
) -> list[ChatMessageResponse]:
    service = _service(request, db)
    conversation = await service.conversations.find_by_id_and_user(conversation_id, user.id)
    if conversation is None:
        raise NotFoundError("Conversation not found", translation_key=E.CONVERSATION_NOT_FOUND)
    docs = await service.messages.list_by_conversation(conversation_id, cursor=cursor or None, limit=limit)
    return [message_from_doc(d) for d in docs]


@router.post("/{conversation_id}/messages", status_code=201)
async def send_message(
    conversation_id: str,
    body: MessageCreate,
    request: Request,
    db: AsyncIOMotorDatabase[dict[str, Any]] = Depends(get_mongo_db_dep),
    user: User = Depends(get_authenticated_user),
) -> ChatTurnResponse:
    service = _service(request, db)
    conversation, user_message, assistant_message = await service.send_message(
        user_id=user.id,
        conversation_id=conversation_id,
        content=body.content,
        idempotency_key=body.idempotency_key,
        request_id=request.scope.get("request_id", ""),
    )
    return ChatTurnResponse(
        conversation=conversation_from_doc(conversation),
        user_message=message_from_doc(user_message),
        assistant_message=message_from_doc(assistant_message),
    )


@router.post("/{conversation_id}/messages/{message_id}/feedback", status_code=200)
async def rate_message(
    conversation_id: str,
    message_id: str,
    body: FeedbackCreate,
    request: Request,
    db: AsyncIOMotorDatabase[dict[str, Any]] = Depends(get_mongo_db_dep),
    user: User = Depends(get_authenticated_user),
) -> MessageFeedbackResponse:
    service = _service(request, db)
    conversation = await service.conversations.find_by_id_and_user(conversation_id, user.id)
    if conversation is None:
        raise NotFoundError("Conversation not found", translation_key=E.CONVERSATION_NOT_FOUND)
    updated = await service.messages.set_feedback(message_id, conversation_id, body.rating)
    if updated is None:
        raise NotFoundError("Message not found", translation_key=E.MESSAGE_NOT_FOUND)
    feedback = updated.get("feedback")
    if not isinstance(feedback, dict) or "rating" not in feedback:
        raise NotFoundError("Message not found", translation_key=E.MESSAGE_NOT_FOUND)
    return MessageFeedbackResponse(id=message_id, rating=int(feedback["rating"]))


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    request: Request,
    db: AsyncIOMotorDatabase[dict[str, Any]] = Depends(get_mongo_db_dep),
    user: User = Depends(get_authenticated_user),
) -> None:
    service = _service(request, db)
    deleted = await service.conversations.soft_delete(conversation_id, user.id)
    if not deleted:
        raise NotFoundError("Conversation not found", translation_key=E.CONVERSATION_NOT_FOUND)
