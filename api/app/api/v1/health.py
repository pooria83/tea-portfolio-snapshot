import platform
import time
from collections.abc import Awaitable
from typing import Any

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import RateLimit
from app.core.metrics import metrics_endpoint
from app.core.redis import get_redis

router = APIRouter(tags=["health"])

_STARTED_AT = time.time()


@router.get("/health")
async def health() -> dict[str, str | int]:
    return {
        "status": "ok",
        "service": "product-graph-api",
        "environment": settings.environment,
        "git_sha": settings.git_sha,
        "uptime_seconds": int(time.time() - _STARTED_AT),
        "python_version": platform.python_version(),
    }


async def _check_dependency(coro: Awaitable[Any]) -> str:
    try:
        await coro
        return "ok"
    except Exception:
        return "error"


@router.get("/ready")
async def ready(request: Request, db: AsyncSession = Depends(get_db), redis: AsyncRedis = Depends(get_redis)) -> dict[str, str]:
    db_status = await _check_dependency(db.execute(text("SELECT 1")))
    redis_status = await _check_dependency(redis.ping())
    broker_status = await _check_dependency(_check_broker(request))
    ai_status = await _check_dependency(_check_ai(request))
    all_ok = all(v == "ok" for v in (db_status, redis_status, broker_status, ai_status))
    return {"status": "ok" if all_ok else "degraded", "database": db_status, "redis": redis_status, "rabbitmq": broker_status, "ai_engine": ai_status}


async def _check_broker(request: Request) -> None:
    broker = request.app.state.broker
    if not broker or not broker.is_connected():
        raise RuntimeError("Broker not connected")


async def _check_ai(request: Request) -> None:
    ai_client = request.app.state.ai_client
    await ai_client.health()


@router.get("/metrics", dependencies=[Depends(RateLimit(max_requests=10, window_seconds=60))])
async def metrics() -> Response:
    if not settings.debug:
        return Response(status_code=404)
    return await metrics_endpoint(None)
