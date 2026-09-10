from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, AuthorizationError, ConflictError, NotFoundError, ServiceUnavailableError


def test_generate_username_from_email():
    from app.services.auth_service import _generate_username

    username = _generate_username("user@example.com")
    assert username == "user_user"


def test_generate_username_from_phone():
    from app.services.auth_service import _generate_username

    username = _generate_username("+966500000000")
    assert username == "user_0000"


def test_generate_username_from_arbitrary():
    from app.services.auth_service import _generate_username

    username = _generate_username("some_arbitrary_string")
    assert username == "user_some_arb"


def test_generate_username_cleans_non_alnum():
    from app.services.auth_service import _generate_username

    username = _generate_username("hello0123456789")
    assert username == "user_hello012"


@pytest.mark.asyncio
async def test_register_user_conflict():
    with patch("app.services.auth_service.UserRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.email_or_username_exists.return_value = True
        mock_repo_cls.return_value = mock_repo

        from app.services.auth_service import register_user

        with pytest.raises(ConflictError, match="Email or username already taken"):
            await register_user(AsyncMock(), "test@test.com", "testuser", "Pass123!")


@pytest.mark.asyncio
async def test_authenticate_user_inactive():
    with patch("app.services.auth_service.UserRepository") as mock_repo_cls:
        user = MagicMock()
        user.hashed_password = "$2b$12$"
        user.is_active = False
        mock_repo = AsyncMock()
        mock_repo.get_by_email.return_value = user
        mock_repo_cls.return_value = mock_repo

        with patch("app.services.auth_service.verify_password", return_value=True):
            from app.services.auth_service import authenticate_user

            with pytest.raises(AuthorizationError, match="Account is inactive"):
                await authenticate_user(AsyncMock(), "inactive@test.com", "Pass123!")


@pytest.mark.asyncio
async def test_authenticate_user_invalid_credentials():
    with patch("app.services.auth_service.UserRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get_by_email.return_value = None
        mock_repo_cls.return_value = mock_repo

        from app.services.auth_service import authenticate_user

        with pytest.raises(AuthenticationError, match="Invalid credentials"):
            await authenticate_user(AsyncMock(), "nobody@test.com", "wrong")


@pytest.mark.asyncio
async def test_refresh_access_token_user_not_found():
    mock_payload = MagicMock()
    mock_payload.sub = "deleted-user"

    with patch("app.services.auth_service.decode_token", return_value=mock_payload), patch("app.services.auth_service.RefreshTokenRepository") as mock_rt_repo_cls:
        mock_rt_repo = AsyncMock()
        mock_rt_repo.get_by_hash.return_value = MagicMock(revoked=False)
        mock_rt_repo_cls.return_value = mock_rt_repo

        from app.services.auth_service import UserRepository

        with patch.object(UserRepository, "get", new=AsyncMock(return_value=None)):
            from app.services.auth_service import refresh_access_token

            with pytest.raises(NotFoundError, match="User not found"):
                await refresh_access_token(AsyncMock(), "valid-token")


@pytest.mark.asyncio
async def test_send_otp_rate_limited():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = "5"

    from app.core.config import settings

    original = settings.otp_max_send_per_phone
    settings.otp_max_send_per_phone = 4
    try:
        from app.services.auth_service import send_otp

        with pytest.raises(ServiceUnavailableError, match="OTP send limit reached"):
            await send_otp(mock_redis, "+966500000000")
    finally:
        settings.otp_max_send_per_phone = original


@pytest.mark.asyncio
async def test_send_otp_twilio_failure():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.incr.return_value = 1

    with patch("app.services.auth_service._sms_service.send_otp", new=AsyncMock(return_value=False)), patch("app.services.auth_service.settings.twilio_bypass", False):
        from app.services.auth_service import send_otp

        with pytest.raises(ServiceUnavailableError, match="Failed to send OTP"):
            await send_otp(mock_redis, "+966500000000")


@pytest.mark.asyncio
async def test_verify_otp_bypass_new_user():
    mock_db = AsyncMock(spec=AsyncSession)
    mock_redis = AsyncMock()

    with patch("app.services.auth_service.settings.twilio_bypass", True), patch("app.services.auth_service.UserRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get_by_phone.return_value = None
        mock_repo.add.return_value = MagicMock(is_active=True)
        mock_repo_cls.return_value = mock_repo

        with (
            patch("app.services.auth_service._ensure_unique_username", new=AsyncMock(return_value="user_+966")),
            patch("app.services.auth_service.create_tokens", new=AsyncMock(return_value="tokens")),
        ):
            from app.services.auth_service import verify_otp

            result = await verify_otp(mock_db, mock_redis, "+966500000000", "123456")
            assert result == "tokens"
            mock_repo.add.assert_called_once()


@pytest.mark.asyncio
async def test_verify_otp_bypass_inactive_user():
    mock_db = AsyncMock(spec=AsyncSession)
    mock_redis = AsyncMock()

    with patch("app.services.auth_service.settings.twilio_bypass", True), patch("app.services.auth_service.UserRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        inactive = MagicMock()
        inactive.is_active = False
        mock_repo.get_by_phone.return_value = inactive
        mock_repo_cls.return_value = mock_repo

        from app.services.auth_service import verify_otp

        with pytest.raises(AuthorizationError, match="Account is inactive"):
            await verify_otp(mock_db, mock_redis, "+966500000000", "123456")


@pytest.mark.asyncio
async def test_verify_otp_rate_limited():
    mock_db = AsyncMock(spec=AsyncSession)
    mock_redis = AsyncMock()
    mock_redis.get.return_value = "5"

    with patch("app.services.auth_service.settings.twilio_bypass", False), patch("app.services.auth_service.settings.otp_max_verify_attempts", 3):
        from app.services.auth_service import verify_otp

        with pytest.raises(AuthenticationError, match="Too many verification attempts"):
            await verify_otp(mock_db, mock_redis, "+966500000000", "000000")


@pytest.mark.asyncio
async def test_verify_otp_inactive_user():
    mock_db = AsyncMock(spec=AsyncSession)
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = [None, "123456"]

    with patch("app.services.auth_service.settings.twilio_bypass", False), patch("app.services.auth_service.UserRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        inactive = MagicMock()
        inactive.is_active = False
        mock_repo.get_by_phone.return_value = inactive
        mock_repo_cls.return_value = mock_repo

        from app.services.auth_service import verify_otp

        with pytest.raises(AuthorizationError, match="Account is inactive"):
            await verify_otp(mock_db, mock_redis, "+966500000000", "123456")


@pytest.mark.asyncio
async def test_google_auth_no_audiences():
    with (
        patch("app.services.auth_service.settings.google_web_client_id", None),
        patch("app.services.auth_service.settings.google_android_client_id", None),
        patch("app.services.auth_service.settings.google_ios_client_id", None),
    ):
        from app.services.auth_service import google_auth

        with pytest.raises(ServiceUnavailableError, match="Google Sign-In is not configured"):
            await google_auth(AsyncMock(), "token")


@pytest.mark.asyncio
async def test_google_auth_verification_value_error():
    with patch("app.services.auth_service.settings.google_web_client_id", "web-id"), patch("app.services.auth_service.id_token.verify_oauth2_token", side_effect=ValueError("bad token")):
        from app.services.auth_service import google_auth

        with pytest.raises(AuthenticationError, match="Invalid Google token"):
            await google_auth(AsyncMock(), "bad-token")


@pytest.mark.asyncio
async def test_google_auth_missing_sub():
    with patch("app.services.auth_service.settings.google_web_client_id", "web-id"), patch("app.services.auth_service.id_token.verify_oauth2_token", return_value={"email": "test@test.com"}):
        from app.services.auth_service import google_auth

        with pytest.raises(AuthenticationError, match="missing user identifier"):
            await google_auth(AsyncMock(), "token")


@pytest.mark.asyncio
async def test_google_auth_existing_user():
    existing_user = MagicMock()
    existing_user.is_active = True

    with (
        patch("app.services.auth_service.settings.google_web_client_id", "web-id"),
        patch(
            "app.services.auth_service.id_token.verify_oauth2_token",
            return_value={
                "sub": "google-123",
                "email": "existing@test.com",
            },
        ),
        patch("app.services.auth_service.UserRepository") as mock_repo_cls,
    ):
        mock_repo = AsyncMock()
        mock_repo.get_by_google_id.return_value = existing_user
        mock_repo_cls.return_value = mock_repo

        with patch("app.services.auth_service.create_tokens", new=AsyncMock(return_value="tokens")):
            from app.services.auth_service import google_auth

            result = await google_auth(AsyncMock(), "token")
            assert result == "tokens"


@pytest.mark.asyncio
async def test_google_auth_existing_user_inactive():
    inactive_user = MagicMock()
    inactive_user.is_active = False

    with (
        patch("app.services.auth_service.settings.google_web_client_id", "web-id"),
        patch(
            "app.services.auth_service.id_token.verify_oauth2_token",
            return_value={
                "sub": "google-123",
            },
        ),
        patch("app.services.auth_service.UserRepository") as mock_repo_cls,
    ):
        mock_repo = AsyncMock()
        mock_repo.get_by_google_id.return_value = inactive_user
        mock_repo_cls.return_value = mock_repo

        from app.services.auth_service import google_auth

        with pytest.raises(AuthorizationError, match="Account is inactive"):
            await google_auth(AsyncMock(), "token")


@pytest.mark.asyncio
async def test_google_auth_email_link():
    existing = MagicMock()
    existing.id = "user-1"
    existing.is_active = True
    existing.full_name = None
    existing.google_id = None

    with (
        patch("app.services.auth_service.settings.google_web_client_id", "web-id"),
        patch(
            "app.services.auth_service.id_token.verify_oauth2_token",
            return_value={
                "sub": "google-456",
                "email": "existing@test.com",
                "name": "Existing User",
            },
        ),
        patch("app.services.auth_service.UserRepository") as mock_repo_cls,
    ):
        mock_repo = AsyncMock()
        mock_repo.get_by_google_id.return_value = None
        mock_repo.get_by_email.return_value = existing
        mock_repo_cls.return_value = mock_repo

        with patch("app.services.auth_service.create_tokens", new=AsyncMock(return_value="tokens")):
            from app.services.auth_service import google_auth

            result = await google_auth(AsyncMock(), "token")
            assert result == "tokens"
            assert existing.google_id == "google-456"
            assert existing.full_name == "Existing User"


@pytest.mark.asyncio
async def test_google_auth_new_user():
    with (
        patch("app.services.auth_service.settings.google_web_client_id", "web-id"),
        patch(
            "app.services.auth_service.id_token.verify_oauth2_token",
            return_value={
                "sub": "google-new",
                "email": "new@test.com",
                "name": "New User",
            },
        ),
        patch("app.services.auth_service.UserRepository") as mock_repo_cls,
    ):
        mock_repo = AsyncMock()
        mock_repo.get_by_google_id.return_value = None
        mock_repo.get_by_email.return_value = None
        new_user = MagicMock()
        new_user.is_active = True
        mock_repo.add.return_value = new_user
        mock_repo_cls.return_value = mock_repo

        with (
            patch("app.services.auth_service._ensure_unique_username", new=AsyncMock(return_value="user_newuser")),
            patch("app.services.auth_service.create_tokens", new=AsyncMock(return_value="tokens")),
        ):
            from app.services.auth_service import google_auth

            result = await google_auth(AsyncMock(), "token")
            assert result == "tokens"
            mock_repo.add.assert_called_once()
