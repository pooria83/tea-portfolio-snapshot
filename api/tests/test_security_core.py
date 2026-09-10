from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt as pyjwt
import pytest
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import get_api_key_user, get_current_user, get_jwt_user

_AUD = settings.jwt_audience
_ISS = settings.jwt_issuer


class _Headers:
    def __init__(self, values: dict | None = None):
        self._values = {k.lower(): str(v) for k, v in (values or {}).items()}

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._values.get(key.lower(), default)


class _FakeRequest:
    def __init__(self, cookies: dict | None = None, headers: dict | None = None):
        self.cookies = cookies or {}
        self.headers = _Headers(headers or {})
        self.state = SimpleNamespace()


def _make_token(payload: dict, secret: str | None = None) -> str:
    full = {
        "aud": _AUD,
        "iss": _ISS,
        "type": "access",
        **payload,
    }
    return pyjwt.encode(full, secret or settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


class TestGetCurrentUser:
    async def test_with_valid_api_key(self):
        result = await get_current_user(request=_FakeRequest(), bearer=None, api_key=settings.api_key)
        assert result is None

    async def test_with_invalid_api_key(self):
        with pytest.raises(AuthorizationError, match="Invalid API key"):
            await get_current_user(request=_FakeRequest(), bearer=None, api_key="wrong-key")

    async def test_with_valid_bearer_token(self):
        token = _make_token({"sub": "user-123", "exp": datetime.now(UTC) + timedelta(hours=1), "role": "user"})
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        result = await get_current_user(request=_FakeRequest(), bearer=creds, api_key=None)
        assert result == "user-123"

    async def test_with_expired_bearer_token(self):
        token = _make_token({"sub": "user-123", "exp": datetime.now(UTC) - timedelta(hours=1)})
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(AuthenticationError, match="Invalid token"):
            await get_current_user(request=_FakeRequest(), bearer=creds, api_key=None)

    async def test_without_any_auth(self):
        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await get_current_user(request=_FakeRequest(), bearer=None, api_key=None)

    async def test_with_valid_cookie_and_csrf_header(self):
        token = _make_token({"sub": "user-123", "exp": datetime.now(UTC) + timedelta(hours=1), "role": "user"})
        request = _FakeRequest(
            cookies={"access_token": token},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        result = await get_current_user(request=request, bearer=None, api_key=None)
        assert result == "user-123"

    async def test_with_cookie_missing_csrf_header(self):
        token = _make_token({"sub": "user-123", "exp": datetime.now(UTC) + timedelta(hours=1), "role": "user"})
        request = _FakeRequest(cookies={"access_token": token})
        with pytest.raises(AuthenticationError, match="CSRF header missing"):
            await get_current_user(request=request, bearer=None, api_key=None)

    async def test_with_expired_cookie_token(self):
        token = _make_token({"sub": "user-123", "exp": datetime.now(UTC) - timedelta(hours=1)})
        request = _FakeRequest(
            cookies={"access_token": token},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        with pytest.raises(AuthenticationError, match="Invalid token"):
            await get_current_user(request=request, bearer=None, api_key=None)


class TestGetJwtUser:
    async def test_with_valid_token(self):
        token = _make_token({"sub": "user-123", "exp": datetime.now(UTC) + timedelta(hours=1)})
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        result = await get_jwt_user(request=_FakeRequest(), bearer=creds)
        assert result == "user-123"

    async def test_without_token(self):
        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await get_jwt_user(request=_FakeRequest(), bearer=None)

    async def test_with_expired_token(self):
        token = _make_token({"sub": "user-123", "exp": datetime.now(UTC) - timedelta(hours=1)})
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(AuthenticationError, match="Invalid token"):
            await get_jwt_user(request=_FakeRequest(), bearer=creds)

    async def test_with_refresh_token_rejected(self):
        token = _make_token({"sub": "user-123", "exp": datetime.now(UTC) + timedelta(hours=1), "type": "refresh"})
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await get_jwt_user(request=_FakeRequest(), bearer=creds)


class TestGetApiKeyUser:
    async def test_with_valid_key(self):
        result = await get_api_key_user(api_key=settings.api_key)
        assert result is None

    async def test_without_key(self):
        with pytest.raises(AuthorizationError, match="Invalid API key"):
            await get_api_key_user(api_key=None)

    async def test_with_invalid_key(self):
        with pytest.raises(AuthorizationError, match="Invalid API key"):
            await get_api_key_user(api_key="wrong-key")
