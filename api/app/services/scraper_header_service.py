from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import E
from app.core.exceptions import NotFoundError
from app.models.scraper_header import ScraperHeader
from app.repositories.scraper_header import ScraperHeaderRepository
from app.scrapers.zara.header_parser import validate_header_block


async def list_headers(db: AsyncSession) -> list[ScraperHeader]:
    repo = ScraperHeaderRepository(db)
    return await repo.list_all()


async def get_header(db: AsyncSession, name: str) -> ScraperHeader:
    repo = ScraperHeaderRepository(db)
    header = await repo.get_by_name(name)
    if header is None:
        raise NotFoundError(f"Scraper header not found: {name}", translation_key=E.SCRAPER_HEADER_NOT_FOUND)
    return header


async def upsert_header(db: AsyncSession, name: str, raw: str) -> ScraperHeader:
    """Create or replace a scraper's raw header block.

    Validates the block (must contain a Cookie header) and resets the status
    back to ``ready``, clearing any previous error state.
    """
    validate_header_block(raw)

    repo = ScraperHeaderRepository(db)
    header = await repo.get_by_name(name)
    if header is None:
        header = ScraperHeader(name=name, header=raw, status="ready")
        db.add(header)
    else:
        header.header = raw
        header.status = "ready"
        header.error_message = None
        header.error_at = None
    await db.commit()
    await db.refresh(header)
    return header


async def clear_header(db: AsyncSession, name: str) -> ScraperHeader:
    """Clear the stored header back to NULL (scraper will exit with an error on start)."""
    repo = ScraperHeaderRepository(db)
    header = await repo.get_by_name(name)
    if header is None:
        raise NotFoundError(f"Scraper header not found: {name}", translation_key=E.SCRAPER_HEADER_NOT_FOUND)
    header.header = None
    header.status = "ready"
    header.error_message = None
    header.error_at = None
    await db.commit()
    await db.refresh(header)
    return header


async def mark_error(db: AsyncSession, name: str, message: str) -> None:
    """Mark a scraper header as failed so the admin panel shows the error."""
    repo = ScraperHeaderRepository(db)
    header = await repo.get_by_name(name)
    if header is None or header.header is None:
        return
    header.status = "error"
    header.error_message = message[:2000]
    header.error_at = datetime.now(UTC)
    await db.commit()


async def mark_ready(db: AsyncSession, name: str) -> None:
    """Reset a scraper header to ready after a successful run start."""
    repo = ScraperHeaderRepository(db)
    header = await repo.get_by_name(name)
    if header is None or header.header is None or header.status != "error":
        return
    header.status = "ready"
    header.error_message = None
    header.error_at = None
    await db.commit()
