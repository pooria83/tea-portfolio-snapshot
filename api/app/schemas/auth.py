import re

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., examples=["user@example.com"])
    username: str = Field(..., min_length=3, max_length=100, examples=["johndoe"], pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=128, examples=["StrongPass1!"])
    full_name: str | None = Field(None, max_length=255, examples=["John Doe"])


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., examples=["user@example.com"])
    password: str = Field(..., examples=["StrongPass1!"])


class SendOTPRequest(BaseModel):
    phone: str = Field(..., examples=["+989123456789"])

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^\+?[1-9]\d{6,14}$", v):
            raise ValueError("Invalid phone number format")
        return v


class VerifyOTPRequest(BaseModel):
    phone: str = Field(..., examples=["+989123456789"])
    code: str = Field(..., min_length=4, max_length=8, examples=["123456"])

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^\+?[1-9]\d{6,14}$", v):
            raise ValueError("Invalid phone number format")
        return v


class GoogleAuthRequest(BaseModel):
    id_token: str = Field(..., examples=["eyJhbGciOiJSUzI1NiIs..."])
    client_type: str | None = Field(None, pattern=r"^(web|android|ios)$", examples=["android"])


class GoogleCodeRequest(BaseModel):
    code: str = Field(..., examples=["4/0AeaYSHB..."])
    redirect_uri: str = Field(..., examples=["https://portfolio.example.invalid/auth/google/callback"])
    state: str = Field(..., min_length=8, max_length=128, examples=["uK8vqQ3x..."])


class GoogleNonceResponse(BaseModel):
    state: str = Field(..., examples=["uK8vqQ3x..."])


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str | None = Field(None, examples=["eyJhbGciOiJSUzI1NiIs..."])
