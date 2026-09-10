from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

EvalQuerySource = Literal["manual", "llm", "seed"]
EvalQueryStatus = Literal["pending", "evaluated", "skipped"]


class EvalQueriesGenerateRequest(BaseModel):
    count: int = Field(default=10, ge=1, le=50)
    locales: list[str] = Field(default_factory=lambda: ["en", "ar"])


class EvalQueryImportItem(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    locale: str = Field(default="en", max_length=5)
    relevant_ids: list[str] = Field(default_factory=list)


class EvalQueriesImportRequest(BaseModel):
    queries: list[EvalQueryImportItem] = Field(min_length=1, max_length=500)


class EvalQueryItem(BaseModel):
    id: str
    text: str
    locale: str
    source: EvalQuerySource
    status: EvalQueryStatus
    rewritten_query: str | None = None
    filters: dict[str, list[str]] | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class EvalQueryUpdate(BaseModel):
    status: EvalQueryStatus | None = None
    rewritten_query: str | None = Field(default=None, max_length=4000)
    filters: dict[str, list[str]] | None = None


class EvalJudgmentItem(BaseModel):
    product_id: str = Field(min_length=1, max_length=64)
    relevant: bool
    rank: int | None = Field(default=None, ge=1, le=100)


class EvalJudgmentsRequest(BaseModel):
    judgments: list[EvalJudgmentItem] = Field(default_factory=list, max_length=200)


class EvalSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    locale: str = Field(default="en", max_length=5)
    limit: int = Field(default=10, ge=1, le=50)


class EvalSearchResultItem(BaseModel):
    rank: int
    score: float
    id: str
    name: str | None = None
    price: float | None = None
    currency: str = "SAR"
    brand: str | None = None
    image_url: str | None = None
    store_id: str | None = None
    product_data: dict[str, Any] | None = None


class EvalSearchResponse(BaseModel):
    query: str
    locale: str
    rewritten_query: str | None = None
    filters: dict[str, list[str]] | None = None
    specs: list[dict[str, Any]] = Field(default_factory=list)
    results: list[EvalSearchResultItem] = Field(default_factory=list)


class EvalMetricItem(BaseModel):
    locale: str
    query_count: int
    mrr_10: float
    recall_10: float


class EvalMetricsResponse(BaseModel):
    overall: EvalMetricItem | None = None
    per_locale: list[EvalMetricItem] = Field(default_factory=list)


class EvalQueryListResponse(BaseModel):
    items: list[EvalQueryItem]
    total: int
    skip: int
    limit: int


class EvalImportResult(BaseModel):
    created: int
    skipped: int
    judgments_created: int
