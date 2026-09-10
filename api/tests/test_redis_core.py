from unittest.mock import MagicMock

import pytest
from fastapi import Request

from app.core.redis import get_redis, publish_json


@pytest.mark.asyncio
async def test_get_redis_success():
    mock_redis = MagicMock()
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.redis = mock_redis

    result = await get_redis(mock_request)
    assert result is mock_redis


@pytest.mark.asyncio
async def test_get_redis_not_initialized():
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.redis = None

    with pytest.raises(RuntimeError, match="Redis not initialized"):
        await get_redis(mock_request)


@pytest.mark.asyncio
async def test_get_redis_missing_attr():
    class State:
        pass

    mock_request = MagicMock(spec=Request)
    mock_request.app.state = State()

    with pytest.raises(RuntimeError, match="Redis not initialized"):
        await get_redis(mock_request)


@pytest.mark.asyncio
async def test_publish_json():
    from unittest.mock import AsyncMock

    mock_redis = AsyncMock()
    await publish_json(mock_redis, "test-channel", {"key": "value"})
    mock_redis.publish.assert_awaited_once()
    call_args = mock_redis.publish.call_args[0]
    assert call_args[0] == "test-channel"
    assert '"key": "value"' in call_args[1]
