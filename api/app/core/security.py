from hmac import compare_digest

from fastapi import Depends, Query, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cookies import ACCESS_TOKEN_COOKIE
from app.core.database import get_db
from app.core.error_codes import E
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.jwt import decode_access_token
from app.core.logging import log_source_var, user_id_var
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

CSRF_HEADER = "x-requested-with"
CSRF_HEADER_VALUE = "XMLHttpRequest"

WEBHOOK_SECRET_HEADER = "x-webhook-secret"


async def verify_webhook_secret(
    request: Request,
    token: str | None = Query(default=None),
) -> None:
    """Verify the AI Engine webhook shared secret.

    Accepts the secret via the ``X-Webhook-Secret`` header or the ``token``
    query parameter. Verification is disabled when ``webhook_secret`` is
    empty (e.g. local development without an AI Engine).
    """
    secret = settings.webhook_secret
    if not secret:
        return
    candidate = request.headers.get(WEBHOOK_SECRET_HEADER) or token
    if not candidate or not compare_digest(candidate, secret):
        raise AuthenticationError("Invalid webhook secret", translation_key=E.NOT_AUTHENTICATED)


def _set_authenticated(user_id: str) -> None:
    user_id_var.set(user_id)
    log_source_var.set("authenticated")


async def get_current_user(
    request: Request,
    bearer: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Depends(api_key_header),
    db: AsyncSession | None = Depends(get_db),
) -> str | None:
    if api_key:
        if api_key == settings.api_key:
            if isinstance(db, AsyncSession):
                result = await db.execute(select(User.id).where(User.api_key == api_key))
                user_id = result.scalar_one_or_none()
                if user_id:
                    _set_authenticated(user_id)
                    return user_id
            return None
        if isinstance(db, AsyncSession):
            result = await db.execute(select(User.id).where(User.api_key == api_key))
            user_id = result.scalar_one_or_none()
            if user_id:
                _set_authenticated(user_id)
                return user_id
        raise AuthorizationError("Invalid API key", translation_key=E.INVALID_API_KEY)
    if bearer:
        user_id = decode_access_token(bearer.credentials)
        _set_authenticated(user_id)
        return user_id
    cookie_token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if cookie_token:
        if request.headers.get(CSRF_HEADER) != CSRF_HEADER_VALUE:
            raise AuthenticationError("CSRF header missing", translation_key=E.CSRF_HEADER_MISSING)
        user_id = decode_access_token(cookie_token)
        _set_authenticated(user_id)
        return user_id
    raise AuthenticationError("Not authenticated", translation_key=E.NOT_AUTHENTICATED)


async def get_jwt_user(
    request: Request,
    bearer: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if not bearer:
        raise AuthenticationError("Not authenticated", translation_key=E.NOT_AUTHENTICATED)
    user_id = decode_access_token(bearer.credentials)
    request.state.user_id = user_id
    _set_authenticated(user_id)
    return user_id


async def get_api_key_user(
    api_key: str | None = Depends(api_key_header),
    db: AsyncSession | None = Depends(get_db),
) -> str | None:
    if not api_key:
        raise AuthorizationError("Invalid API key", translation_key=E.INVALID_API_KEY)
    if api_key == settings.api_key:
        if isinstance(db, AsyncSession):
            result = await db.execute(select(User.id).where(User.api_key == api_key))
            user_id = result.scalar_one_or_none()
            if user_id:
                user_id_var.set(user_id)
                log_source_var.set("authenticated")
                return user_id
        return None
    if isinstance(db, AsyncSession):
        result = await db.execute(select(User.id).where(User.api_key == api_key))
        user_id = result.scalar_one_or_none()
        if user_id:
            user_id_var.set(user_id)
            log_source_var.set("authenticated")
            return user_id
    raise AuthorizationError("Invalid API key", translation_key=E.INVALID_API_KEY)
