import asyncio
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.activity_log import ActivityLog

RETENTION_DAYS = 60
CLEANUP_INTERVAL = 86400


async def cleanup_activity_logs(session_factory: async_sessionmaker[AsyncSession], retention_days: int = RETENTION_DAYS) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    try:
        async with session_factory() as db:
            result = await db.execute(delete(ActivityLog).where(ActivityLog.created_at < cutoff))
            await db.commit()
            deleted = result.rowcount or 0  # type: ignore[attr-defined]
            if deleted:
                logger.info("activity_log_cleanup deleted={} older_than={}d", deleted, retention_days)
            return deleted
    except Exception:
        logger.opt(exception=True).warning("activity_log_cleanup_failed")
        return 0


async def run_activity_log_cleanup(session_factory: async_sessionmaker[AsyncSession], shutdown_event: asyncio.Event, interval: int = CLEANUP_INTERVAL) -> None:
    await cleanup_activity_logs(session_factory)
    while not shutdown_event.is_set():
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=interval)
            break
        except TimeoutError:
            await cleanup_activity_logs(session_factory)
