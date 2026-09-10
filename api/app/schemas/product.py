from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, examples=["Wireless Headphones"])
    description: str | None = Field(None, max_length=5000, examples=["Noise-canceling Bluetooth headphones with 30h battery life"])
    price: float | None = Field(None, ge=0, examples=[79.99])
    currency: str = Field("USD", min_length=3, max_length=10, examples=["USD"])
    category: str | None = Field(None, max_length=100, examples=["Electronics"])
    image_url: str | None = Field(None, examples=["https://example.com/image.jpg"])
    buy_url: str | None = Field(None, examples=["https://example.com/buy"])


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)
    price: float | None = Field(None, ge=0)
    currency: str | None = Field(None, min_length=3, max_length=10)
    category: str | None = Field(None, max_length=100)
    image_url: str | None = None
    buy_url: str | None = None


class ProductResponse(BaseModel):
    id: str
    name: str
    description: str | None
    price: float | None
    currency: str
    category: str | None
    image_url: str | None
    buy_url: str | None
    source: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    skip: int
    limit: int
    has_next: bool
    has_previous: bool
