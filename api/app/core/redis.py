import json
from typing import Any

from fastapi import Request
from redis.asyncio import Redis as AsyncRedis


async def get_redis(request: Request) -> AsyncRedis:
    redis: AsyncRedis | None = getattr(request.app.state, "redis", None)
    if redis is None:
        raise RuntimeError("Redis not initialized")
    return redis


async def publish_json(redis: AsyncRedis, channel: str, data: dict[str, Any]) -> None:
    await redis.publish(channel, json.dumps(data, default=str))
