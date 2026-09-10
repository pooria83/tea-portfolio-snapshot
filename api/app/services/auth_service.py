import asyncio
import secrets
import string

import requests
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from loguru import logger
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.error_codes import E
from app.core.exceptions import AuthenticationError, AuthorizationError, ConflictError, NotFoundError, ServiceUnavailableError
from app.core.jwt import create_access_token, create_refresh_token, decode_token
from app.core.password import hash_password, verify_password
from app.models.user import RefreshToken, User
from app.repositories.refresh_token import RefreshTokenRepository, hash_token
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse
from app.services.sms_service import SmsService

OTP_PREFIX = "otp"
OTP_SEND_PREFIX = "otp_send"
OTP_VERIFY_PREFIX = "otp_verify"

_sms_service = SmsService()


def _generate_otp(length: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


OAUTH_STATE_PREFIX = "google_oauth_state"


async def issue_oauth_state(redis: AsyncRedis) -> str:
    state = secrets.token_urlsafe(32)
    await redis.setex(
        f"{OAUTH_STATE_PREFIX}:{state}",
        settings.oauth_state_expire_seconds,
        "1",
    )
    return state


async def consume_oauth_state(redis: AsyncRedis, state: str) -> None:
    consumed = await redis.getdel(f"{OAUTH_STATE_PREFIX}:{state}")
    if not consumed:
        raise AuthenticationError("Invalid OAuth state", translation_key=E.INVALID_OAUTH_STATE)


def _get_google_audiences() -> list[str]:
    audiences: list[str] = []
    if settings.google_web_client_id:
        audiences.append(settings.google_web_client_id)
    if settings.google_android_client_id:
        audiences.append(settings.google_android_client_id)
    if settings.google_ios_client_id:
        audiences.append(settings.google_ios_client_id)
    if not audiences:
        raise ServiceUnavailableError("Google Sign-In is not configured.", translation_key=E.GOOGLE_NOT_CONFIGURED)
    return audiences


async def _verify_google_token(id_token_str: str, audiences: list[str]) -> dict[str, object]:
    try:
        loop = asyncio.get_running_loop()
        session = requests.Session()
        session.trust_env = False
        request_adapter = google_requests.Request(session=session)
        return await loop.run_in_executor(
            None,
            lambda: id_token.verify_oauth2_token(id_token_str, request_adapter, audience=audiences),  # type: ignore[no-untyped-call]
        )
    except ValueError as exc:
        raise AuthenticationError(f"Invalid Google token: {exc}", translation_key=E.INVALID_GOOGLE_TOKEN) from exc
    except Exception as exc:
        logger.exception("google_token_verification_failed")
        raise ServiceUnavailableError("Failed to verify Google token. Please try again.", translation_key=E.GOOGLE_VERIFY_FAILED) from exc


def _extract_google_info(info: dict[str, object]) -> tuple[str, str | None, str | None]:
    google_id_obj = info.get("sub")
    if not isinstance(google_id_obj, str):
        raise AuthenticationError("Google token missing user identifier.", translation_key=E.GOOGLE_TOKEN_MISSING_ID)
    email_obj = info.get("email")
    email: str | None = email_obj if isinstance(email_obj, str) else None
    name_obj = info.get("name")
    name: str | None = name_obj if isinstance(name_obj, str) else None
    return google_id_obj, email, name


async def _get_or_create_user_by_phone(db: AsyncSession, phone: str) -> User:
    user_repo = UserRepository(db)
    user = await user_repo.get_by_phone(phone)
    if user is None:
        username = await _ensure_unique_username(db, _generate_username(phone))
        user = await user_repo.add(User(phone=phone, username=username))
    return user


async def _check_otp_verify_limit(redis: AsyncRedis, prefix: str, phone: str) -> None:
    verify_key = f"{prefix}:{phone}"
    verify_count = await redis.get(verify_key)
    if verify_count and int(verify_count) >= settings.otp_max_verify_attempts:
        raise AuthenticationError("Too many verification attempts. Request a new OTP.", translation_key=E.TOO_MANY_OTP_ATTEMPTS)


async def _verify_otp_code(redis: AsyncRedis, otp_prefix: str, verify_prefix: str, phone: str, code: str) -> str:
    otp_key = f"{otp_prefix}:{phone}"
    verify_key = f"{verify_prefix}:{phone}"
    stored_code = await redis.get(otp_key)
    stored_code_str = stored_code.decode() if isinstance(stored_code, bytes) else stored_code
    if not stored_code or stored_code_str != code:
        verify_count_val = await redis.incr(verify_key)
        if verify_count_val == 1:
            await redis.expire(verify_key, 600)
        raise AuthenticationError("Invalid or expired OTP.", translation_key=E.INVALID_OTP)
    await redis.delete(otp_key)
    await redis.delete(verify_key)
    return stored_code_str


def _generate_username(source: str) -> str:
    if source.startswith("+"):
        suffix = source[-4:]
    elif "@" in source:
        suffix = source.split("@")[0][:8]
    else:
        suffix = source[:8]
    clean = "".join(c for c in suffix if c.isalnum() or c == "_")
    return f"user_{clean}"


async def register_user(db: AsyncSession, email: str, username: str, password: str, full_name: str | None = None) -> User:
    user_repo = UserRepository(db)
    if await user_repo.email_or_username_exists(email, username):
        raise ConflictError("Email or username already taken", translation_key=E.EMAIL_OR_USERNAME_TAKEN)
    user = await user_repo.add(User(email=email, username=username, hashed_password=hash_password(password), full_name=full_name))
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(email)
    if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
        raise AuthenticationError("Invalid credentials", translation_key=E.INVALID_CREDENTIALS)
    if not user.is_active:
        raise AuthorizationError("Account is inactive", translation_key=E.ACCOUNT_INACTIVE)
    return user


async def create_tokens(db: AsyncSession, user: User) -> TokenResponse:
    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)
    decoded = decode_token(refresh_token)
    token_repo = RefreshTokenRepository(db)
    await token_repo.add(RefreshToken(token=hash_token(refresh_token), user_id=user.id, expires_at=decoded.exp))
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, token_type="bearer")


async def revoke_all_sessions(db: AsyncSession, user_id: str) -> None:
    """Persistently revoke all refresh tokens for a user.

    Commits independently of the caller's transaction so the revocation
    survives even when the caller subsequently raises (e.g. reuse detection).
    """
    token_repo = RefreshTokenRepository(db)
    await token_repo.revoke_all_for_user(user_id)
    await db.commit()


async def refresh_access_token(db: AsyncSession, token: str) -> TokenResponse:
    payload = decode_token(token)
    token_repo = RefreshTokenRepository(db)
    db_token = await token_repo.get_by_hash(token)
    if not db_token:
        raise AuthenticationError("Invalid or expired refresh token", translation_key=E.REFRESH_TOKEN_INVALID)
    if db_token.revoked:
        await revoke_all_sessions(db, payload.sub)
        raise AuthenticationError("Refresh token reuse detected. All sessions revoked.", translation_key=E.REFRESH_TOKEN_REUSE)
    db_token.revoked = True
    user_repo = UserRepository(db)
    user = await user_repo.get(payload.sub)
    if not user:
        raise NotFoundError("User not found", translation_key=E.USER_NOT_FOUND)
    return await create_tokens(db, user)


async def revoke_refresh_token(db: AsyncSession, token: str | None) -> None:
    if not token:
        return
    try:
        decode_token(token)
    except AuthenticationError:
        return
    await RefreshTokenRepository(db).revoke_by_hash(token)


async def _ensure_unique_username(db: AsyncSession, base: str) -> str:
    user_repo = UserRepository(db)
    username = base
    counter = 1
    while await user_repo.get_by_username(username):
        username = f"{base}_{counter}"
        counter += 1
    return username


async def send_otp(redis: AsyncRedis, phone: str) -> None:
    send_key = f"{OTP_SEND_PREFIX}:{phone}"
    send_count = await redis.get(send_key)
    if send_count and int(send_count) >= settings.otp_max_send_per_phone:
        raise ServiceUnavailableError("OTP send limit reached. Try again later.", translation_key=E.OTP_SEND_LIMIT)

    code = _generate_otp(settings.otp_code_length)
    if settings.twilio_bypass:
        logger.info("TWILIO_BYPASS active — OTP {} for {} (not sent via SMS)", code, phone)
    else:
        sent = await _sms_service.send_otp(phone, code)
        if not sent:
            raise ServiceUnavailableError("Failed to send OTP. Try again later.", translation_key=E.OTP_SEND_FAILED)

    otp_key = f"{OTP_PREFIX}:{phone}"
    await redis.setex(otp_key, settings.otp_expire_seconds, code)

    send_count_val = await redis.incr(send_key)
    if send_count_val == 1:
        await redis.expire(send_key, 600)


async def verify_otp(db: AsyncSession, redis: AsyncRedis, phone: str, code: str) -> TokenResponse:
    if settings.twilio_bypass and code == "123456":
        logger.info("TWILIO_BYPASS — magic code 123456 accepted for {}", phone)
        user = await _get_or_create_user_by_phone(db, phone)
        if not user.is_active:
            raise AuthorizationError("Account is inactive", translation_key=E.ACCOUNT_INACTIVE)
        return await create_tokens(db, user)

    await _check_otp_verify_limit(redis, OTP_VERIFY_PREFIX, phone)
    await _verify_otp_code(redis, OTP_PREFIX, OTP_VERIFY_PREFIX, phone, code)

    user = await _get_or_create_user_by_phone(db, phone)
    if not user.is_active:
        raise AuthorizationError("Account is inactive", translation_key=E.ACCOUNT_INACTIVE)
    return await create_tokens(db, user)


async def google_auth(db: AsyncSession, id_token_str: str, client_type: str | None = None) -> TokenResponse:
    audiences = _get_google_audiences()
    info = await _verify_google_token(id_token_str, audiences)
    google_id, email, name = _extract_google_info(info)

    user_repo = UserRepository(db)
    user = await user_repo.get_by_google_id(google_id)
    if user is not None:
        if not user.is_active:
            raise AuthorizationError("Account is inactive", translation_key=E.ACCOUNT_INACTIVE)
        return await create_tokens(db, user)

    if email:
        user = await user_repo.get_by_email(email)
        if user is not None:
            user.google_id = google_id
            if name and not user.full_name:
                user.full_name = name
            if not user.is_active:
                raise AuthorizationError("Account is inactive", translation_key=E.ACCOUNT_INACTIVE)
            return await create_tokens(db, user)

    username = await _ensure_unique_username(db, _generate_username(email or google_id))
    user = await user_repo.add(User(google_id=google_id, email=email, username=username, full_name=name))
    return await create_tokens(db, user)
