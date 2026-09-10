import secrets
import string

from loguru import logger
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.error_codes import E
from app.core.exceptions import ConflictError, NotFoundError, ServiceUnavailableError
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserProfileUpdate, UserUpdate
from app.services.auth_service import _check_otp_verify_limit, _extract_google_info, _get_google_audiences, _verify_google_token, _verify_otp_code
from app.services.sms_service import SmsService

LINK_OTP_PREFIX = "link_otp"
LINK_OTP_SEND_PREFIX = "link_otp_send"
LINK_OTP_VERIFY_PREFIX = "link_otp_verify"

_sms_service = SmsService()


def _generate_otp(length: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


async def get_user_by_id(db: AsyncSession, user_id: str) -> User:
    repo = UserRepository(db)
    user = await repo.get(user_id)
    if not user:
        raise NotFoundError("User not found", translation_key=E.USER_NOT_FOUND)
    return user


async def update_user(db: AsyncSession, user: User, data: UserUpdate) -> User:
    repo = UserRepository(db)
    if data.email is not None:
        existing = await repo.get_by_email(data.email)
        if existing and existing.id != user.id:
            raise ConflictError("Email already taken", translation_key=E.EMAIL_TAKEN)
        user.email = data.email
    if data.full_name is not None:
        user.full_name = data.full_name
    await db.flush()
    return user


async def update_user_profile(db: AsyncSession, user: User, data: UserProfileUpdate) -> User:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    await db.flush()
    return user


async def send_link_otp(redis: AsyncRedis, phone: str) -> None:
    send_key = f"{LINK_OTP_SEND_PREFIX}:{phone}"
    send_count = await redis.get(send_key)
    if send_count and int(send_count) >= settings.otp_max_send_per_phone:
        raise ServiceUnavailableError("OTP send limit reached. Try again later.", translation_key=E.OTP_SEND_LIMIT)

    code = _generate_otp(settings.otp_code_length)
    if settings.twilio_bypass:
        logger.info("TWILIO_BYPASS active — link OTP {} for {} (not sent via SMS)", code, phone)
    else:
        sent = await _sms_service.send_otp(phone, code)
        if not sent:
            raise ServiceUnavailableError("Failed to send OTP. Try again later.", translation_key=E.OTP_SEND_FAILED)

    otp_key = f"{LINK_OTP_PREFIX}:{phone}"
    await redis.setex(otp_key, settings.otp_expire_seconds, code)

    send_count_val = await redis.incr(send_key)
    if send_count_val == 1:
        await redis.expire(send_key, 600)


async def verify_link_phone(db: AsyncSession, redis: AsyncRedis, user: User, phone: str, code: str) -> User:
    if settings.twilio_bypass and code == "123456":
        logger.info("TWILIO_BYPASS — magic code 123456 accepted for link phone {}", phone)
    else:
        await _check_otp_verify_limit(redis, LINK_OTP_VERIFY_PREFIX, phone)
        await _verify_otp_code(redis, LINK_OTP_PREFIX, LINK_OTP_VERIFY_PREFIX, phone, code)

    repo = UserRepository(db)
    existing = await repo.get_by_phone(phone)
    if existing and existing.id != user.id:
        raise ConflictError("This phone number is already linked to another account. Please sign in with that account first, or contact support.", translation_key=E.PHONE_ALREADY_LINKED)

    user.phone = phone
    await db.flush()
    return user


async def link_google(db: AsyncSession, user: User, id_token_str: str) -> User:
    audiences = _get_google_audiences()
    info = await _verify_google_token(id_token_str, audiences)
    google_id, email, name = _extract_google_info(info)

    repo = UserRepository(db)
    existing = await repo.get_by_google_id(google_id)
    if existing and existing.id != user.id:
        raise ConflictError("This Google account is already linked to another user. Please sign in with that account first, or contact support.", translation_key=E.GOOGLE_ALREADY_LINKED)

    if email:
        existing_email = await repo.get_by_email(email)
        if existing_email and existing_email.id != user.id:
            raise ConflictError("This Google email is already linked to another user. Please sign in with that account first, or contact support.", translation_key=E.GOOGLE_EMAIL_ALREADY_LINKED)

    user.google_id = google_id
    if email and not user.email:
        user.email = email
    if name and not user.full_name:
        user.full_name = name
    await db.flush()
    return user
