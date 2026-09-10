from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request

from app.core.exceptions import AppError
from app.core.rate_limit import check_login_rate_limit, check_rate_limit, record_failed_login, reset_login_attempts


def _mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.eval = AsyncMock(side_effect=NotImplementedError("no script support"))
    return redis


def _mock_request(user_id: str | None = None, path: str = "/test") -> MagicMock:
    req = MagicMock(spec=Request)
    req.client.host = "127.0.0.1"
    req.url.path = path
    req.state.user_id = user_id
    return req


@pytest.mark.asyncio
async def test_check_rate_limit_allowed():
    redis = _mock_redis()
    redis.incr.return_value = 1
    request = _mock_request()

    await check_rate_limit(redis, request, max_requests=10, window_seconds=60)

    redis.incr.assert_awaited_once()
    redis.expire.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_rate_limit_exceeded():
    redis = _mock_redis()
    redis.incr.return_value = 11
    request = _mock_request()

    with pytest.raises(AppError) as exc:
        await check_rate_limit(redis, request, max_requests=10, window_seconds=60)

    assert exc.value.code == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_check_rate_limit_no_client():
    redis = _mock_redis()
    redis.incr.return_value = 1
    request = MagicMock(spec=Request)
    request.client = None
    request.url.path = "/test"
    request.state.user_id = None

    await check_rate_limit(redis, request, max_requests=10, window_seconds=60)

    redis.incr.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_rate_limit_uses_user_id_from_state():
    redis = _mock_redis()
    redis.incr.return_value = 1
    request = _mock_request(user_id="user-123")

    await check_rate_limit(redis, request, max_requests=10, window_seconds=60)

    args, _ = redis.incr.call_args
    assert "user-123" in args[0]


@pytest.mark.asyncio
async def test_check_rate_limit_atomic_lua_path():
    redis = AsyncMock()
    redis.eval.return_value = 1
    request = _mock_request()

    await check_rate_limit(redis, request, max_requests=10, window_seconds=60)

    redis.eval.assert_awaited_once()
    redis.incr.assert_not_awaited()
    redis.expire.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_rate_limit_atomic_lua_exceeded():
    redis = AsyncMock()
    redis.eval.return_value = 11
    request = _mock_request()

    with pytest.raises(AppError) as exc:
        await check_rate_limit(redis, request, max_requests=10, window_seconds=60)

    assert exc.value.code == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_check_login_rate_limit_allowed():
    redis = _mock_redis()
    redis.incr.return_value = 1

    await check_login_rate_limit(redis, "test@example.com", max_attempts=5)

    redis.incr.assert_awaited_once()
    redis.expire.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_login_rate_limit_exceeded():
    redis = _mock_redis()
    redis.incr.return_value = 5

    with pytest.raises(AppError) as exc:
        await check_login_rate_limit(redis, "test@example.com", max_attempts=5)

    assert exc.value.code == "ACCOUNT_LOCKED"


@pytest.mark.asyncio
async def test_check_login_rate_limit_multiple_windows():
    redis = _mock_redis()
    redis.incr.return_value = 10

    with pytest.raises(AppError) as exc:
        await check_login_rate_limit(redis, "test@example.com", max_attempts=5, multiplier=2, window_minutes=15)

    assert exc.value.code == "ACCOUNT_LOCKED"
    assert "30" in exc.value.detail


@pytest.mark.asyncio
async def test_record_failed_login():
    redis = AsyncMock()

    await record_failed_login(redis, "test@example.com")

    redis.incr.assert_awaited_once()
    redis.expire.assert_awaited_once()


@pytest.mark.asyncio
async def test_reset_login_attempts():
    redis = AsyncMock()

    await reset_login_attempts(redis, "test@example.com")

    redis.delete.assert_awaited_once_with("login_attempts:test@example.com")
