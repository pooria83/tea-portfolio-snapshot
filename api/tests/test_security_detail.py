from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core.security import get_api_key_user, get_current_user, get_jwt_user


class _FakeRequest:
    def __init__(self):
        self.cookies = {}
        self.headers = {}
        self.state = SimpleNamespace()


@pytest.mark.asyncio
async def test_get_current_user_with_api_key():
    user = await get_current_user(
        request=_FakeRequest(),
        bearer=None,
        api_key="test-api-key",
    )
    assert user is None


@pytest.mark.asyncio
async def test_get_current_user_with_invalid_api_key():
    from app.core.exceptions import AuthorizationError

    with pytest.raises(AuthorizationError):
        await get_current_user(
            request=_FakeRequest(),
            bearer=None,
            api_key="wrong-key",
        )


@pytest.mark.asyncio
async def test_get_current_user_no_auth():
    from app.core.exceptions import AuthenticationError

    with pytest.raises(AuthenticationError):
        await get_current_user(request=_FakeRequest(), bearer=None, api_key=None)


@pytest.mark.asyncio
async def test_get_jwt_user_not_authenticated():
    from app.core.exceptions import AuthenticationError

    with pytest.raises(AuthenticationError):
        await get_jwt_user(request=_FakeRequest(), bearer=None)


@pytest.mark.asyncio
async def test_get_jwt_user_expired():
    from unittest.mock import MagicMock

    from app.core.exceptions import AuthenticationError
    from app.core.jwt import TokenPayload

    mock_bearer = MagicMock()
    mock_bearer.credentials = "expired.token.here"

    with patch("app.core.jwt.decode_token") as mock_decode:
        mock_decode.return_value = TokenPayload(
            sub="user-1",
            exp=datetime.now(UTC) - timedelta(hours=1),
            role="user",
            type="access",
        )
        with pytest.raises(AuthenticationError, match="Token expired"):
            await get_jwt_user(request=_FakeRequest(), bearer=mock_bearer)


@pytest.mark.asyncio
async def test_get_api_key_user_valid():
    user = await get_api_key_user(api_key="test-api-key")
    assert user is None


@pytest.mark.asyncio
async def test_get_api_key_user_invalid():
    from app.core.exceptions import AuthorizationError

    with pytest.raises(AuthorizationError):
        await get_api_key_user(api_key="wrong-key")


@pytest.mark.asyncio
async def test_get_api_key_user_missing():
    from app.core.exceptions import AuthorizationError

    with pytest.raises(AuthorizationError):
        await get_api_key_user(api_key=None)
