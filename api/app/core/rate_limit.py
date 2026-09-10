from fastapi import Request
from redis.asyncio import Redis as AsyncRedis

from app.core.error_codes import E
from app.core.exceptions import AppError

_INCR_EXPIRE_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


async def _atomic_incr_expire(redis: AsyncRedis, key: str, window_seconds: int) -> int:
    """Increment a counter and set its TTL atomically on first use."""
    try:
        value = await redis.eval(_INCR_EXPIRE_LUA, 1, key, window_seconds)
        return int(value)
    except Exception:
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, window_seconds)
        return current


async def check_rate_limit(
    redis: AsyncRedis,
    request: Request,
    key_prefix: str = "rl",
    max_requests: int = 100,
    window_seconds: int = 60,
) -> None:
    host = request.client.host if request.client and request.client.host else "unknown"
    user_id = getattr(request.state, "user_id", host)
    route = request.url.path
    rate_key = f"{key_prefix}:{user_id}:{route}"

    current = await _atomic_incr_expire(redis, rate_key, window_seconds)

    remaining = max_requests - current
    if current > max_requests:
        raise AppError(
            detail="Rate limit exceeded",
            code="RATE_LIMITED",
            status_code=429,
            translation_key=E.RATE_LIMITED,
            headers={"X-RateLimit-Remaining": str(max(0, remaining))},
        )


async def check_login_rate_limit(
    redis: AsyncRedis,
    email: str,
    max_attempts: int = 5,
    window_minutes: int = 15,
    multiplier: int = 2,
) -> None:
    attempt_key = f"login_attempts:{email}"
    current = await _atomic_incr_expire(redis, attempt_key, window_minutes * 60)

    if current >= max_attempts:
        lockout_minutes = window_minutes * (multiplier ** (current // max_attempts - 1))
        raise AppError(
            detail=f"Account locked due to too many failed attempts. Try again in {lockout_minutes} minutes.",
            code="ACCOUNT_LOCKED",
            status_code=429,
            translation_key=E.ACCOUNT_LOCKED,
        )


async def record_failed_login(redis: AsyncRedis, email: str) -> None:
    attempt_key = f"login_attempts:{email}"
    await redis.incr(attempt_key)
    await redis.expire(attempt_key, 60 * 60)


async def reset_login_attempts(redis: AsyncRedis, email: str) -> None:
    await redis.delete(f"login_attempts:{email}")
