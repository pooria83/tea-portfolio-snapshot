#!/usr/bin/env python3
"""
Run one cycle of the embedding backfill manually.

Fetches all products that need embedding (pending, generating, or error)
and submits them to the AI Engine for embedding.

Usage:
    uv run scripts/run_embedding_backfill.py
    uv run scripts/run_embedding_backfill.py --include-errors   # also retry failed
"""

import argparse
import asyncio
import sys

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.client import AIEngineClient
from app.core.activity_logger import log_activity
from app.core.config import settings
from app.services.embedding_cron import fetch_unembedded_products, submit_for_embedding_concurrent

logger.remove()
logger.add(sys.stderr, level="INFO")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill embeddings for products")
    parser.add_argument("--include-errors", action="store_true", help="Also retry products in error status")
    args = parser.parse_args()

    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    ai_client = AIEngineClient()

    try:
        async with session_factory() as db:
            products = await fetch_unembedded_products(db, include_errors=args.include_errors)
            if not products:
                logger.info("No products need embedding")
                return
            logger.info("Found {} products to embed (include_errors={})", len(products), args.include_errors)

        ok = await submit_for_embedding_concurrent(session_factory, products, ai_client, max_concurrency=5)
        logger.info("Done. Successfully embedded {}/{} products.", ok, len(products))
        await log_activity(
            session_factory=session_factory,
            actor_type="system",
            action="SCRIPT_RUN",
            status_code=200,
            resource_type="cron",
            message=f"embedding backfill: {ok}/{len(products)} products embedded",
            details={"total": len(products), "success": ok} if ok else None,
            path="/system/backfill/embedding",
            method="SCRIPT",
        )
    finally:
        await ai_client.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
