from datetime import datetime

from pydantic import BaseModel, Field


class ScraperHeaderResponse(BaseModel):
    id: str
    name: str
    header: str | None
    status: str
    error_message: str | None
    error_at: datetime | None
    updated_at: datetime


class ScraperHeaderUpdate(BaseModel):
    header: str = Field(..., min_length=1, max_length=200_000, description="Raw HTTP request header block (contains Cookie header)")


class ScraperHeaderClearResponse(BaseModel):
    name: str
    header: str | None
    status: str
