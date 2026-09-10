from fastapi import APIRouter, Depends, Request
from httpx import AsyncClient, HTTPError, TimeoutException
from loguru import logger
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import RateLimit, get_admin_user, get_authenticated_user
from app.core.error_codes import E
from app.core.exceptions import AuthenticationError, ServiceUnavailableError
from app.core.redis import get_redis
from app.core.response import APIResponse, success
from app.models.user import User
from app.schemas.user import LinkGoogleMobileRequest, LinkGoogleRequest, LinkPhoneRequest, LinkPhoneVerify, UserProfileUpdate, UserResponse, UserUpdate
from app.services import auth_service, user_service
from app.services.storage_service import move_url_to_bucket

router = APIRouter(prefix="/users", tags=["users"])


def _to_user_response(user: User) -> UserResponse:
    resp = UserResponse.model_validate(user)
    resp.has_google = user.google_id is not None
    return resp


@router.get("/me", response_model=APIResponse[UserResponse], dependencies=[Depends(RateLimit(max_requests=60, window_seconds=60))])
async def get_me(user: User = Depends(get_authenticated_user)) -> APIResponse[UserResponse]:
    return success(_to_user_response(user))


@router.patch("/me", response_model=APIResponse[UserResponse], dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def update_me(data: UserUpdate, request: Request, user: User = Depends(get_authenticated_user), db: AsyncSession = Depends(get_db)) -> APIResponse[UserResponse]:
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = user.id
        activity["message"] = f"user {user.id} update profile"
    return success(_to_user_response(await user_service.update_user(db, user, data)))


@router.get("/me/profile", response_model=APIResponse[UserResponse], dependencies=[Depends(RateLimit(max_requests=60, window_seconds=60))])
async def get_my_profile(user: User = Depends(get_authenticated_user)) -> APIResponse[UserResponse]:
    return success(_to_user_response(user))


@router.patch("/me/profile", response_model=APIResponse[UserResponse], dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def update_my_profile(
    data: UserProfileUpdate,
    request: Request,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[UserResponse]:
    if data.avatar_url:
        temp_storage = getattr(request.app.state, "temp_storage", None)
        profile_storage = getattr(request.app.state, "profile_storage", None)
        data.avatar_url = await move_url_to_bucket(data.avatar_url, temp_storage, profile_storage)
    return success(_to_user_response(await user_service.update_user_profile(db, user, data)))


@router.post(
    "/me/link/phone/send-otp",
    status_code=204,
    dependencies=[Depends(RateLimit(max_requests=10, window_seconds=60))],
)
async def link_phone_send_otp(data: LinkPhoneRequest, redis: AsyncRedis = Depends(get_redis)) -> None:
    await user_service.send_link_otp(redis, data.phone)


@router.post(
    "/me/link/phone/verify",
    response_model=APIResponse[UserResponse],
    dependencies=[Depends(RateLimit(max_requests=10, window_seconds=60))],
)
async def link_phone_verify(
    data: LinkPhoneVerify,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[UserResponse]:
    return success(_to_user_response(await user_service.verify_link_phone(db, redis, user, data.phone, data.code)))


@router.post(
    "/me/link/google",
    response_model=APIResponse[UserResponse],
    dependencies=[Depends(RateLimit(max_requests=10, window_seconds=60))],
)
async def link_google(
    data: LinkGoogleRequest,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[UserResponse]:
    if data.redirect_uri not in settings.allowed_redirect_uris_set:
        raise AuthenticationError("Invalid redirect URI", translation_key=E.INVALID_REDIRECT_URI)
    await auth_service.consume_oauth_state(redis, data.state)

    try:
        async with AsyncClient(timeout=30.0, proxy=None) as client:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": data.code,
                    "client_id": settings.google_web_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": data.redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
            if not token_resp.is_success:
                raise AuthenticationError("Failed to exchange Google authorization code", translation_key=E.GOOGLE_CODE_EXCHANGE_FAILED)

            token_data = token_resp.json()
            id_token_str: str | None = token_data.get("id_token")
            if not id_token_str:
                raise AuthenticationError("Google did not return an ID token", translation_key=E.GOOGLE_NO_ID_TOKEN)
    except TimeoutException:
        logger.error("google_token_exchange_timeout")
        raise ServiceUnavailableError("Google authentication timed out. Please try again.", translation_key=E.GOOGLE_AUTH_TIMEOUT) from None
    except HTTPError as e:
        logger.exception("google_token_exchange_failed")
        raise ServiceUnavailableError("Failed to communicate with Google. Please try again.", translation_key=E.GOOGLE_COMM_FAILED) from e

    return success(_to_user_response(await user_service.link_google(db, user, id_token_str)))


@router.post(
    "/me/link/google/mobile",
    response_model=APIResponse[UserResponse],
    dependencies=[Depends(RateLimit(max_requests=10, window_seconds=60))],
)
async def link_google_mobile(
    data: LinkGoogleMobileRequest,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[UserResponse]:
    return success(_to_user_response(await user_service.link_google(db, user, data.id_token)))


@router.get("/{user_id}", response_model=UserResponse, dependencies=[Depends(RateLimit(max_requests=30, window_seconds=60))])
async def get_user(user_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(get_admin_user)) -> User:
    return await user_service.get_user_by_id(db, user_id)
