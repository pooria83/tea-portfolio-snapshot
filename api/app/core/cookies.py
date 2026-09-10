from typing import Literal, TypedDict

from fastapi import Response

from app.core.config import settings

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"


class _CookieArgs(TypedDict, total=False):
    max_age: int | None
    path: str | None
    secure: bool
    httponly: bool
    samesite: Literal["lax", "strict", "none"] | None


def _cookie_kwargs(max_age: int) -> _CookieArgs:
    return {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "max_age": max_age,
        "path": "/",
    }


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        access_token,
        **_cookie_kwargs(settings.access_token_expire_minutes * 60),
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        refresh_token,
        **_cookie_kwargs(settings.refresh_token_expire_days * 24 * 60 * 60),
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path="/")
