from typing import Any, Literal

from pydantic import BaseModel, Field

MessageRole = Literal["user", "assistant"]


class ChatMessage(BaseModel):
    role: MessageRole = "user"
    content: str = Field(default="", max_length=8000)


class ChatRequest(BaseModel):
    query: str
    locale: str = "en"
    limit: int = 10
    history: list[ChatMessage] = Field(default_factory=list)
    summary: str = ""
    stream: bool = False
    parse_prompt: str | None = None
    system_prompt: str | None = None


class ProductRef(BaseModel):
    id: str
    name: str | None = None
    price: float | None = None
    currency: str = "SAR"
    brand: str | None = None
    image_url: str | None = None
    store_id: str | None = None
    product_data: dict[str, Any] | None = None


class SearchSpec(BaseModel):
    query: str
    filters: dict[str, list[str]] | None = None


class SearchContext(BaseModel):
    rewritten_query: str | None = None
    filters: dict[str, list[str]] | None = None
    tool_used: bool = False
    specs: list[SearchSpec] = Field(default_factory=list)
    intent: Literal["greeting", "search", "general"] | None = None


class ChatDebug(BaseModel):
    prompt: dict[str, Any]
    response: dict[str, Any]


class ChatResponse(BaseModel):
    answer: str
    products: list[ProductRef]
    search_context: SearchContext | None = None
    tokens_used: int | None = None
    debug: ChatDebug | None = None


class SummarizeRequest(BaseModel):
    messages: list[ChatMessage]
    previous_summary: str = ""
    locale: str = "en"
    prompt: str | None = None


class SummarizeResponse(BaseModel):
    summary: str
    tokens_used: int


class TitleRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    locale: str = "en"
    prompt: str | None = None
    need_title: bool = True


class TitleResponse(BaseModel):
    title: str
