import secrets
from datetime import UTC, datetime, timedelta

import jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.error_codes import E
from app.core.exceptions import AuthenticationError


class TokenPayload(BaseModel):
    sub: str
    exp: datetime
    role: str = "user"
    type: str = "access"


def create_access_token(
    user_id: str,
    role: str = "user",
    token_type: str = "access",
    expires_delta: timedelta | None = None,
) -> str:
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    token: str = jwt.encode(
        {
            "sub": user_id,
            "exp": expire,
            "role": role,
            "type": token_type,
            "aud": settings.jwt_audience,
            "iss": settings.jwt_issuer,
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    token: str = jwt.encode(
        {
            "sub": user_id,
            "exp": expire,
            "type": "refresh",
            "jti": secrets.token_urlsafe(16),
            "aud": settings.jwt_audience,
            "iss": settings.jwt_issuer,
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token


def decode_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
        return TokenPayload(
            sub=payload["sub"],
            exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
            role=payload.get("role", "user"),
            type=payload.get("type", "access"),
        )
    except jwt.InvalidTokenError as e:
        raise AuthenticationError("Invalid token", translation_key=E.INVALID_TOKEN) from e


def extract_bearer_token(value: str | None) -> str | None:
    """Return the token from an ``Authorization: Bearer <token>`` header value."""
    if not value:
        return None
    parts = value.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def decode_access_token(token: str) -> str:
    """Decode and validate an access token, returning the subject id."""
    payload = decode_token(token)
    if payload.exp < datetime.now(UTC):
        raise AuthenticationError("Token expired", translation_key=E.TOKEN_EXPIRED)
    if payload.type != "access":
        raise AuthenticationError("Not authenticated", translation_key=E.NOT_AUTHENTICATED)
    return payload.sub
