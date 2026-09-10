from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, ServiceUnavailableError


@pytest.mark.asyncio
async def test_get_user_by_id_not_found():
    with patch("app.services.user_service.UserRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None
        mock_repo_cls.return_value = mock_repo

        from app.services.user_service import get_user_by_id

        with pytest.raises(NotFoundError):
            await get_user_by_id(AsyncMock(), "nonexistent")


@pytest.mark.asyncio
async def test_update_user_email_conflict():
    with patch("app.services.user_service.UserRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        existing = MagicMock()
        existing.id = "other-user"
        mock_repo.get_by_email.return_value = existing
        mock_repo_cls.return_value = mock_repo

        from app.schemas.user import UserUpdate

        user = MagicMock()
        user.id = "user-1"

        from app.services.user_service import update_user

        data = UserUpdate(email="taken@test.com")
        with pytest.raises(ConflictError, match="Email already taken"):
            await update_user(AsyncMock(), user, data)


@pytest.mark.asyncio
async def test_update_user_email_self_conflict():
    with patch("app.services.user_service.UserRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        existing = MagicMock()
        existing.id = "user-1"
        mock_repo.get_by_email.return_value = existing
        mock_repo_cls.return_value = mock_repo

        from app.schemas.user import UserUpdate

        user = MagicMock()
        user.id = "user-1"
        user.full_name = "Original"

        from app.services.user_service import update_user

        data = UserUpdate(email="same@test.com")
        result = await update_user(AsyncMock(), user, data)
        assert result is user


@pytest.mark.asyncio
async def test_update_user_success():
    with patch("app.services.user_service.UserRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get_by_email.return_value = None
        mock_repo_cls.return_value = mock_repo

        mock_db = AsyncMock(spec=AsyncSession)
        user = MagicMock()
        user.id = "user-1"
        user.full_name = "Old Name"

        from app.schemas.user import UserUpdate
        from app.services.user_service import update_user

        data = UserUpdate(full_name="New Name")
        result = await update_user(mock_db, user, data)
        assert result.full_name == "New Name"
        mock_db.flush.assert_awaited_once()


def test_generate_otp_length():
    from app.services.user_service import _generate_otp

    otp = _generate_otp(6)
    assert len(otp) == 6
    assert otp.isdigit()

    otp = _generate_otp(4)
    assert len(otp) == 4


@pytest.mark.asyncio
async def test_update_user_profile_success():
    mock_db = AsyncMock(spec=AsyncSession)
    user = MagicMock()

    from app.schemas.user import UserProfileUpdate
    from app.services.user_service import update_user_profile

    data = UserProfileUpdate(full_name="New Profile Name")
    result = await update_user_profile(mock_db, user, data)
    assert result.full_name == "New Profile Name"
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_user_profile_empty():
    mock_db = AsyncMock(spec=AsyncSession)
    user = MagicMock()

    from app.schemas.user import UserProfileUpdate
    from app.services.user_service import update_user_profile

    data = UserProfileUpdate()
    await update_user_profile(mock_db, user, data)
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_link_otp_bypass():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.incr.return_value = 1

    from app.services.user_service import send_link_otp

    await send_link_otp(mock_redis, "+966500000000")
    mock_redis.setex.assert_called_once()
    mock_redis.incr.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_link_otp_rate_limited():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = "5"

    from app.core.config import settings

    original = settings.otp_max_send_per_phone
    settings.otp_max_send_per_phone = 4
    try:
        from app.services.user_service import send_link_otp

        with pytest.raises(ServiceUnavailableError, match="OTP send limit reached"):
            await send_link_otp(mock_redis, "+966500000000")
    finally:
        settings.otp_max_send_per_phone = original


@pytest.mark.asyncio
async def test_send_link_otp_sms_failure():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.incr.return_value = 1

    with patch("app.services.user_service._sms_service.send_otp", new=AsyncMock(return_value=False)), patch("app.services.user_service.settings.twilio_bypass", False):
        from app.services.user_service import send_link_otp

        with pytest.raises(ServiceUnavailableError, match="Failed to send OTP"):
            await send_link_otp(mock_redis, "+966500000000")


@pytest.mark.asyncio
async def test_verify_link_phone_bypass():
    mock_db = AsyncMock(spec=AsyncSession)
    mock_redis = AsyncMock()
    user = MagicMock()
    user.id = "user-1"

    with patch("app.services.user_service.UserRepository") as mock_repo_cls:
        mock_repo = AsyncMock()
        mock_repo.get_by_phone.return_value = None
        mock_repo_cls.return_value = mock_repo

        with patch("app.services.user_service.settings.twilio_bypass", True):
            from app.services.user_service import verify_link_phone

            result = await verify_link_phone(mock_db, mock_redis, user, "+966500000000", "123456")
            assert result.phone == "+966500000000"
            mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_verify_link_phone_wrong_code():
    mock_db = AsyncMock(spec=AsyncSession)
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = [None, "654321"]
    mock_redis.incr.return_value = 1
    user = MagicMock()
    user.id = "user-1"

    with patch("app.services.user_service.settings.twilio_bypass", False):
        from app.services.user_service import verify_link_phone

        with pytest.raises(AuthenticationError, match="Invalid or expired OTP"):
            await verify_link_phone(mock_db, mock_redis, user, "+966500000000", "000000")


@pytest.mark.asyncio
async def test_verify_link_phone_rate_limited():
    mock_db = AsyncMock(spec=AsyncSession)
    mock_redis = AsyncMock()
    mock_redis.get.return_value = "5"
    user = MagicMock()
    user.id = "user-1"

    with patch("app.services.user_service.settings.twilio_bypass", False), patch("app.services.user_service.settings.otp_max_verify_attempts", 3):
        from app.services.user_service import verify_link_phone

        with pytest.raises(AuthenticationError, match="Too many verification attempts"):
            await verify_link_phone(mock_db, mock_redis, user, "+966500000000", "000000")


@pytest.mark.asyncio
async def test_verify_link_phone_conflict():
    mock_db = AsyncMock(spec=AsyncSession)
    mock_redis = AsyncMock()
    mock_redis.get.return_value = "123456"
    user = MagicMock()
    user.id = "user-1"

    with patch("app.services.user_service.UserRepository") as mock_repo_cls, patch("app.services.user_service.settings.twilio_bypass", True):
        mock_repo = AsyncMock()
        existing_user = MagicMock()
        existing_user.id = "other-user"
        mock_repo.get_by_phone.return_value = existing_user
        mock_repo_cls.return_value = mock_repo

        from app.services.user_service import verify_link_phone

        with pytest.raises(ConflictError, match="already linked to another account"):
            await verify_link_phone(mock_db, mock_redis, user, "+966500000000", "123456")


@pytest.mark.asyncio
async def test_link_google_no_audiences():
    with (
        patch("app.services.user_service.settings.google_web_client_id", None),
        patch("app.services.user_service.settings.google_android_client_id", None),
        patch("app.services.user_service.settings.google_ios_client_id", None),
    ):
        from app.services.user_service import link_google

        with pytest.raises(ServiceUnavailableError, match="Google Sign-In is not configured"):
            await link_google(AsyncMock(), MagicMock(), "token")


@pytest.mark.asyncio
async def test_link_google_verification_failure():
    with patch("app.services.auth_service.settings.google_web_client_id", "web-id"), patch("app.services.auth_service.id_token.verify_oauth2_token", side_effect=ValueError("Invalid token")):
        from app.services.user_service import link_google

        with pytest.raises(AuthenticationError, match="Invalid Google token"):
            await link_google(AsyncMock(), MagicMock(), "bad-token")


@pytest.mark.asyncio
async def test_link_google_missing_sub():
    with patch("app.services.auth_service.settings.google_web_client_id", "web-id"), patch("app.services.auth_service.id_token.verify_oauth2_token", return_value={"email": "test@example.com"}):
        from app.services.user_service import link_google

        with pytest.raises(AuthenticationError, match="missing user identifier"):
            await link_google(AsyncMock(), MagicMock(), "token")


@pytest.mark.asyncio
async def test_link_google_success():
    with (
        patch("app.services.auth_service.settings.google_web_client_id", "web-id"),
        patch("app.services.auth_service.settings.google_android_client_id", None),
        patch("app.services.auth_service.settings.google_ios_client_id", None),
        patch(
            "app.services.auth_service.id_token.verify_oauth2_token",
            return_value={
                "sub": "google-123",
                "email": "new@example.com",
                "name": "New User",
            },
        ),
    ):
        mock_db = AsyncMock(spec=AsyncSession)
        user = MagicMock()
        user.email = None
        user.full_name = None

        from app.services.user_service import UserRepository

        with patch.object(UserRepository, "get_by_google_id", new=AsyncMock(return_value=None)), patch.object(UserRepository, "get_by_email", new=AsyncMock(return_value=None)):
            from app.services.user_service import link_google

            result = await link_google(mock_db, user, "valid-token")
            assert result.google_id == "google-123"
            assert result.email == "new@example.com"
            assert result.full_name == "New User"
            mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_link_google_google_id_conflict():
    with (
        patch("app.services.auth_service.settings.google_web_client_id", "web-id"),
        patch(
            "app.services.auth_service.id_token.verify_oauth2_token",
            return_value={
                "sub": "google-123",
                "email": "test@example.com",
            },
        ),
    ):
        existing = MagicMock()
        existing.id = "other-user"

        from app.services.user_service import UserRepository

        with patch.object(UserRepository, "get_by_google_id", new=AsyncMock(return_value=existing)):
            from app.services.user_service import link_google

            with pytest.raises(ConflictError, match="already linked to another user"):
                await link_google(AsyncMock(), MagicMock(id="user-1"), "token")


@pytest.mark.asyncio
async def test_link_google_email_conflict():
    with (
        patch("app.services.auth_service.settings.google_web_client_id", "web-id"),
        patch(
            "app.services.auth_service.id_token.verify_oauth2_token",
            return_value={
                "sub": "google-123",
                "email": "taken@example.com",
            },
        ),
    ):
        existing_email = MagicMock()
        existing_email.id = "other-user"

        from app.services.user_service import UserRepository

        with patch.object(UserRepository, "get_by_google_id", new=AsyncMock(return_value=None)), patch.object(UserRepository, "get_by_email", new=AsyncMock(return_value=existing_email)):
            from app.services.user_service import link_google

            with pytest.raises(ConflictError, match="already linked to another user"):
                await link_google(AsyncMock(), MagicMock(id="user-1"), "token")
