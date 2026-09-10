from typing import Any

from pydantic import BaseModel, Field


class SimilarRequest(BaseModel):
    product_id: str = Field(min_length=1)
    lang: str = "en"
    limit: int = Field(default=10, ge=1, le=50)
    # Ordered category chain (leaf -> parent -> ... -> root). Each entry is the
    # bilingual display names [name_en, name_ar] for that level, used to build
    # the metadata filter ladder. Optional: omitted by callers without a DB.
    categories: list[list[str]] | None = None


class SimilarResponse(BaseModel):
    products: list[dict[str, Any]]
