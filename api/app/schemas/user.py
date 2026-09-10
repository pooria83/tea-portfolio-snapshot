from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserResponse(BaseModel):
    id: str
    email: str | None = None
    phone: str | None = None
    username: str | None = None
    full_name: str | None
    role: str
    is_active: bool
    avatar_url: str | None = None
    address: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None
    preferred_language: str = "ar"
    has_google: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None
    address: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None
    preferred_language: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None


class LinkPhoneRequest(BaseModel):
    phone: str


class LinkPhoneVerify(BaseModel):
    phone: str
    code: str


class LinkGoogleRequest(BaseModel):
    code: str
    redirect_uri: str
    state: str = Field(..., min_length=8, max_length=128)


class LinkGoogleMobileRequest(BaseModel):
    id_token: str
