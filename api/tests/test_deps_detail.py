from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request

from app.core.deps import RateLimit
from app.core.exceptions import AppError


class TestRateLimitDependency:
    @pytest.mark.asyncio
    async def test_call_passes_to_check_rate_limit(self):
        redis = AsyncMock()
        redis.eval = AsyncMock(side_effect=NotImplementedError("no script support"))
        redis.incr.return_value = 1

        request = MagicMock(spec=Request)
        request.client.host = "127.0.0.1"
        request.url.path = "/test"
        request.state.user_id = None

        rl = RateLimit(max_requests=5, window_seconds=30)
        await rl(request, redis)

        redis.incr.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_call_exceeded_raises(self):
        redis = AsyncMock()
        redis.eval = AsyncMock(side_effect=NotImplementedError("no script support"))
        redis.incr.return_value = 6

        request = MagicMock(spec=Request)
        request.client.host = "127.0.0.1"
        request.url.path = "/test"
        request.state.user_id = None

        rl = RateLimit(max_requests=5, window_seconds=30)
        with pytest.raises(AppError) as exc:
            await rl(request, redis)
        assert exc.value.code == "RATE_LIMITED"
