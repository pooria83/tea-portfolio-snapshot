from pydantic import BaseModel, Field

from app.schemas.chat import ProductRef, SearchSpec


class EvalQueriesRequest(BaseModel):
    count: int = Field(default=10, ge=1, le=50)
    locales: list[str] = Field(default_factory=lambda: ["en", "ar"])
    catalog_context: str = Field(default="", max_length=8000)


class EvalQueryItem(BaseModel):
    text: str
    locale: str


class EvalQueriesResponse(BaseModel):
    queries: list[EvalQueryItem]


class EvalSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    locale: str = "en"
    limit: int = Field(default=10, ge=1, le=50)


class EvalSearchResult(BaseModel):
    rank: int
    score: float
    product: ProductRef


class EvalSearchResponse(BaseModel):
    query: str
    locale: str
    rewritten_query: str | None = None
    filters: dict[str, list[str]] | None = None
    specs: list[SearchSpec] = Field(default_factory=list)
    results: list[EvalSearchResult] = Field(default_factory=list)
