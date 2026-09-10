"""Ephemeral anonymous chat sessions for public visitors.

The home-page chat box has no user account, so we mint a short-lived,
random per-visitor identity that is valid for the WebSocket chat only. We
deliberately do NOT create a Postgres user: every authenticated REST
endpoint calls ``get_authenticated_user`` which looks up the ``sub`` in the
user table, so a random UUID fails with USER_NOT_FOUND there. The token
carries ``type="anon"`` and a 10-minute expiry, and ``get_jwt_user`` /
``_decode_access_token`` reject any non-``access`` token — so it is useless
outside the WebSocket (whose ``_authenticate_ws`` only decodes the JWT),
which keeps anonymous conversations fully isolated from authenticated REST
data.
"""

import uuid
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.api.v1.chat_deps import get_chat_service, get_mongo_db_dep
from app.core.deps import RateLimit
from app.core.jwt import create_access_token
from app.schemas.chat import ConversationCreate, ConversationResponse, conversation_from_doc
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])

ANON_TOKEN_TTL = timedelta(minutes=10)


class AnonymousSessionResponse(BaseModel):
    token: str = Field(description="Short-lived WebSocket-only access token")
    conversation: ConversationResponse


@router.post(
    "/anonymous-session",
    status_code=201,
    dependencies=[Depends(RateLimit(max_requests=20, window_seconds=60))],
)
async def create_anonymous_session(
    body: ConversationCreate,
    request: Request,
    db: AsyncIOMotorDatabase[dict[str, Any]] = Depends(get_mongo_db_dep),
) -> AnonymousSessionResponse:
    service: ChatService = get_chat_service(request.app)
    user_id = str(uuid.uuid4())
    conversation = await service.conversations.create(user_id, body.locale, body.app_version, need_title=False)
    token = create_access_token(user_id, role="user", token_type="anon", expires_delta=ANON_TOKEN_TTL)
    return AnonymousSessionResponse(
        token=token,
        conversation=conversation_from_doc(conversation),
    )
