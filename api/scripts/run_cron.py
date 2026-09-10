#!/usr/bin/env python3
"""
Run one cycle of the product AI generation cron manually.

Usage:
    python scripts/run_cron.py
"""

import asyncio
import sys

from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.client import AIEngineClient
from app.core.activity_logger import log_activity
from app.core.config import settings
from app.services.product_ai_cron import run_cycle, set_shutdown_event

logger.add(sys.stderr, level="INFO")


async def main() -> None:
    shutdown_event = asyncio.Event()
    set_shutdown_event(shutdown_event)

    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    redis = Redis.from_url(str(settings.redis_url))
    ai_client = AIEngineClient()

    try:
        await run_cycle(session_factory, ai_client, redis)
        await log_activity(
            session_factory=session_factory,
            actor_type="system",
            action="CRON_RUN",
            status_code=200,
            resource_type="cron",
            message="manual product_ai_cron trigger via script",
            path="/system/cron/product-ai",
            method="CRON",
        )
    finally:
        await ai_client.close()
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
