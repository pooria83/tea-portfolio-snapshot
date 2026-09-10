from datetime import datetime

from pydantic import BaseModel


class FavoriteItemResponse(BaseModel):
    id: str
    store_id: str
    store_name: str | None = None
    name_ar: str | None = None
    name_en: str | None = None
    name_fa: str | None = None
    brand: str | None = None
    price: float | None = None
    original_price: float | None = None
    sale_price: float | None = None
    currency: str | None = None
    image_url: str | None = None
    created_at: datetime
