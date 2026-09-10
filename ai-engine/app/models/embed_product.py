from typing import Any

from pydantic import BaseModel, Field


class EmbedProductRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=512)
    lang: str = Field(min_length=1, max_length=16)
    text: str = Field(min_length=1, max_length=20_000)
    webhook_url: str | None = Field(default=None, max_length=2048)
    payload: dict[str, Any] | None = None
    filters: dict[str, list[str]] | None = None
