from fastapi import APIRouter, Depends, Request, Response
from httpx import AsyncClient, HTTPError, TimeoutException
from loguru import logger
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cookies import clear_auth_cookies, set_auth_cookies
from app.core.database import get_db
from app.core.deps import RateLimit
from app.core.error_codes import E
from app.core.exceptions import AuthenticationError, ServiceUnavailableError
from app.core.rate_limit import check_login_rate_limit, record_failed_login, reset_login_attempts
from app.core.redis import get_redis
from app.schemas.auth import GoogleAuthRequest, GoogleCodeRequest, GoogleNonceResponse, LoginRequest, RefreshRequest, RegisterRequest, SendOTPRequest, TokenResponse, VerifyOTPRequest
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    dependencies=[Depends(RateLimit(max_requests=5, window_seconds=300))],
)
async def register(data: RegisterRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await auth_service.register_user(db, data.email, data.username, data.password, data.full_name)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["action"] = "REGISTER"
        activity["resource_type"] = "user"
        activity["resource_id"] = user.id
        activity["message"] = f"user {user.id} register"
    tokens = await auth_service.create_tokens(db, user)
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return tokens


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(RateLimit(max_requests=10, window_seconds=60))],
)
async def login(data: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db), redis: AsyncRedis = Depends(get_redis)) -> TokenResponse:
    await check_login_rate_limit(
        redis,
        data.email,
        max_attempts=settings.login_max_attempts,
        window_minutes=settings.login_lockout_minutes,
        multiplier=settings.login_lockout_multiplier,
    )
    try:
        user = await auth_service.authenticate_user(db, data.email, data.password)
    except AuthenticationError:
        await record_failed_login(redis, data.email)
        raise
    await reset_login_attempts(redis, data.email)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["action"] = "LOGIN"
        activity["message"] = f"user login {data.email}"
    tokens = await auth_service.create_tokens(db, user)
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return tokens


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(RateLimit(max_requests=5, window_seconds=60))],
)
async def refresh(
    request: Request,
    response: Response,
    data: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    token = data.refresh_token if data and data.refresh_token else request.cookies.get("refresh_token")
    if not token:
        raise AuthenticationError("Refresh token required", translation_key=E.REFRESH_TOKEN_INVALID)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["action"] = "REFRESH_TOKEN"
        activity["message"] = "refresh token"
    tokens = await auth_service.refresh_access_token(db, token)
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return tokens


@router.post(
    "/logout",
    status_code=204,
    dependencies=[Depends(RateLimit(max_requests=10, window_seconds=60))],
)
async def logout(
    request: Request,
    response: Response,
    data: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> None:
    token = data.refresh_token if data and data.refresh_token else request.cookies.get("refresh_token")
    await auth_service.revoke_refresh_token(db, token)
    clear_auth_cookies(response)


@router.post(
    "/send-otp",
    status_code=204,
    dependencies=[Depends(RateLimit(max_requests=10, window_seconds=60))],
)
async def send_otp(data: SendOTPRequest, request: Request, redis: AsyncRedis = Depends(get_redis)) -> None:
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["action"] = "SEND_OTP"
        activity["message"] = f"send otp to {data.phone}"
    await auth_service.send_otp(redis, data.phone)


@router.post(
    "/verify-otp",
    response_model=TokenResponse,
    dependencies=[Depends(RateLimit(max_requests=10, window_seconds=60))],
)
async def verify_otp(data: VerifyOTPRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db), redis: AsyncRedis = Depends(get_redis)) -> TokenResponse:
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["action"] = "VERIFY_OTP"
        activity["message"] = f"verify otp for {data.phone}"
    tokens = await auth_service.verify_otp(db, redis, data.phone, data.code)
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return tokens


@router.post(
    "/google",
    response_model=TokenResponse,
    dependencies=[Depends(RateLimit(max_requests=10, window_seconds=60))],
)
async def google_auth(data: GoogleAuthRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["action"] = "GOOGLE_LOGIN"
        activity["message"] = "google auth"
    tokens = await auth_service.google_auth(db, data.id_token, data.client_type)
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return tokens


@router.post(
    "/google/nonce",
    response_model=GoogleNonceResponse,
    dependencies=[Depends(RateLimit(max_requests=10, window_seconds=60))],
)
async def google_nonce(redis: AsyncRedis = Depends(get_redis)) -> GoogleNonceResponse:
    state = await auth_service.issue_oauth_state(redis)
    return GoogleNonceResponse(state=state)


@router.post(
    "/google/code",
    response_model=TokenResponse,
    dependencies=[Depends(RateLimit(max_requests=10, window_seconds=60))],
)
async def google_code_auth(data: GoogleCodeRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db), redis: AsyncRedis = Depends(get_redis)) -> TokenResponse:
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

    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["action"] = "GOOGLE_LOGIN"
        activity["resource_type"] = "user"
        activity["message"] = "google code auth"
    tokens = await auth_service.google_auth(db, id_token_str, "web")
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return tokens
