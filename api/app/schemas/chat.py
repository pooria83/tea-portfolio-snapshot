from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.images import normalize_image_url

ConversationStatus = Literal["active", "closed"]
MessageRole = Literal["user", "assistant"]
MessageStatus = Literal["streaming", "completed", "failed"]
ChatIntent = Literal["greeting", "search", "general", "error"]


class ProductSnapshot(BaseModel):
    id: str
    name: str | None = None
    name_ar: str | None = None
    name_en: str | None = None
    name_fa: str | None = None
    price: float | None = None
    currency: str = "SAR"
    brand: str | None = None
    brand_ar: str | None = None
    brand_en: str | None = None
    brand_fa: str | None = None
    image_url: str | None = None
    buy_url: str | None = None
    store_id: str | None = None


class SearchContext(BaseModel):
    rewritten_query: str | None = None
    filters: dict[str, list[str]] | None = None
    intent: ChatIntent | None = None


class ChatDebugInfo(BaseModel):
    prompt: dict[str, Any]
    response: dict[str, Any]


class ConversationCreate(BaseModel):
    locale: str = Field(default="en", max_length=10)
    app_version: str = Field(default="", max_length=50)
    create_new: bool = Field(default=False, description="Start a fresh active conversation")
    need_title: bool = Field(default=True, description="Whether the conversation should get an LLM-generated title")


class ConversationResponse(BaseModel):
    id: str
    title: str | None = None
    status: ConversationStatus
    user_message_count: int
    last_activity_at: datetime
    locale: str
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(default="", max_length=128)


class MessageFeedback(BaseModel):
    rating: int
    comment: str | None = None
    created_at: datetime


class ChatMessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: MessageRole
    content: str
    status: MessageStatus
    token_count: int | None = None
    product_snapshots: list[ProductSnapshot] = Field(default_factory=list)
    search_context: SearchContext | None = None
    debug: ChatDebugInfo | None = None
    feedback: MessageFeedback | None = None
    created_at: datetime
    error: str | None = None
    locale: str | None = None


class FeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5, description="1-5 star rating of the assistant answer")


class MessageFeedbackResponse(BaseModel):
    id: str
    rating: int


class ChatTurnResponse(BaseModel):
    conversation: ConversationResponse
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse | None = None


class AdminConversationItem(BaseModel):
    id: str
    title: str | None = None
    user_id: str
    user_identifier: str | None = None
    status: ConversationStatus
    user_message_count: int
    summary: str | None = None
    summary_token_count: int | None = None
    last_activity_at: datetime
    locale: str
    created_at: datetime
    updated_at: datetime


def conversation_from_doc(doc: dict[str, Any]) -> ConversationResponse:
    return ConversationResponse(
        id=doc["_id"],
        title=doc.get("title"),
        status=doc["status"],
        user_message_count=doc["userMessageCount"],
        last_activity_at=doc["lastActivityAt"],
        locale=doc["locale"],
        created_at=doc["createdAt"],
        updated_at=doc["updatedAt"],
    )


def message_from_doc(doc: dict[str, Any]) -> ChatMessageResponse:
    feedback = doc.get("feedback")
    debug = doc.get("debug")
    snapshots = [ProductSnapshot(**{**s, "image_url": normalize_image_url(s.get("image_url"))}) for s in doc.get("productSnapshots", [])]
    return ChatMessageResponse(
        id=doc["_id"],
        conversation_id=doc["conversationId"],
        role=doc["role"],
        content=doc["content"],
        status=doc["status"],
        token_count=doc.get("tokenCount"),
        product_snapshots=snapshots,
        search_context=SearchContext(**doc["searchContext"]) if doc.get("searchContext") else None,
        debug=ChatDebugInfo(**debug) if isinstance(debug, dict) else None,
        feedback=MessageFeedback(
            rating=feedback["rating"],
            comment=feedback.get("comment"),
            created_at=feedback["createdAt"],
        )
        if isinstance(feedback, dict) and "rating" in feedback and "createdAt" in feedback
        else None,
        created_at=doc["createdAt"],
        error=doc.get("error"),
        locale=doc.get("locale"),
    )
