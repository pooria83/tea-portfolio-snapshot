from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StoreMemberRole(StrEnum):
    owner = "owner"
    manager = "manager"


class StoreMemberResponse(BaseModel):
    id: str
    user_id: str
    role: StoreMemberRole
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None

    model_config = ConfigDict(from_attributes=True)


class StoreMemberAddRequest(BaseModel):
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)
    role: StoreMemberRole = StoreMemberRole.manager


class StoreWorkingHourInput(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    open_time: str | None = None
    close_time: str | None = None
    is_closed: bool = False


class StoreWorkingHourResponse(BaseModel):
    id: str
    day_of_week: int
    open_time: str | None
    close_time: str | None
    is_closed: bool

    model_config = ConfigDict(from_attributes=True)


class StoreCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    category_id: str
    store_type_id: str
    description: str | None = None
    phone: str = Field(..., max_length=20)
    address: str
    location_lat: float
    location_lng: float
    logo_url: str | None = None
    website: str | None = None
    instagram: str | None = None
    country_code: str = Field(..., min_length=2, max_length=5)
    price_unit_code: str = Field(..., min_length=2, max_length=10)
    working_hours: list[StoreWorkingHourInput] = []


class StoreUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    category_id: str | None = None
    store_type_id: str | None = None
    description: str | None = None
    phone: str | None = Field(None, max_length=20)
    address: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None
    logo_url: str | None = None
    website: str | None = None
    instagram: str | None = None
    is_active: bool | None = None
    country_code: str | None = Field(None, min_length=2, max_length=5)
    price_unit_code: str | None = Field(None, min_length=2, max_length=10)
    working_hours: list[StoreWorkingHourInput] | None = None


class StoreResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    category_id: str
    store_type_id: str
    description: str | None
    phone: str
    logo_url: str | None
    address: str
    location_lat: float
    location_lng: float
    website: str | None
    instagram: str | None
    is_active: bool
    country_code: str
    price_unit_code: str
    country_name_ar: str
    country_name_en: str
    country_name_fa: str
    currency_name_ar: str
    currency_name_en: str
    currency_name_fa: str
    currency_symbol: str
    active_products_count: int = 0
    created_at: datetime
    updated_at: datetime
    category_name_ar: str
    category_name_en: str
    category_name_fa: str
    store_type_name_ar: str
    store_type_name_en: str
    store_type_name_fa: str
    working_hours: list[StoreWorkingHourResponse] = []
    members: list[StoreMemberResponse] = []
    my_role: StoreMemberRole | None = None

    model_config = ConfigDict(from_attributes=True)


class StoreListResponse(BaseModel):
    id: str
    name: str
    country_code: str
    price_unit_code: str
    country_name_ar: str
    country_name_en: str
    country_name_fa: str
    currency_name_ar: str
    currency_name_en: str
    currency_name_fa: str
    currency_symbol: str
    category_name_ar: str
    category_name_en: str
    category_name_fa: str
    store_type_name_ar: str
    store_type_name_en: str
    store_type_name_fa: str
    logo_url: str | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductStatsResponse(BaseModel):
    total: int
    active: int
