from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import cast as sa_cast
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import CursorResult

from app.models.scrape_product import ScrapeProduct
from app.repositories.base import BaseRepository

PROCESSING_MARKER = "__processing__"


class ScrapeProductRepository(BaseRepository[ScrapeProduct]):
    model = ScrapeProduct

    async def exists(self, source: str, source_id: str, country: str) -> bool:
        stmt = select(ScrapeProduct).where(ScrapeProduct.source == source).where(ScrapeProduct.source_id == source_id).where(ScrapeProduct.country == country)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def exists_by_url(self, source: str, source_url: str) -> bool:
        """True when any row (any id) already carries this URL.

        Scraped rows migrate their source_id from the URL p-code to the
        canonical JSON-LD id, so fetch_sitemap must dedup on the URL too or it
        re-inserts every already-scraped product as pending on every re-run.
        """
        stmt = select(ScrapeProduct).where(ScrapeProduct.source == source).where(ScrapeProduct.source_url == source_url)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_by_key(self, source: str, source_id: str, country: str) -> ScrapeProduct | None:
        stmt = select(ScrapeProduct).where(ScrapeProduct.source == source).where(ScrapeProduct.source_id == source_id).where(ScrapeProduct.country == country)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_pending_sync(self, limit: int = 0, source: str = "") -> list[ScrapeProduct]:
        """Scraped rows awaiting API sync (cached images, no api_product_id, no error)."""
        stmt = select(ScrapeProduct).where(
            ScrapeProduct.api_product_id.is_(None),
            ScrapeProduct.images_cached.is_(True),
            ScrapeProduct.scrape_error.is_(None),
        )
        if source:
            stmt = stmt.where(ScrapeProduct.source == source)
        stmt = stmt.order_by(ScrapeProduct.created_at)
        if limit > 0:
            stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_pending_scrape(self, source: str, limit: int = 0) -> list[ScrapeProduct]:
        stmt = (
            select(ScrapeProduct)
            .where(ScrapeProduct.source == source)
            .where(ScrapeProduct.raw_data.cast(JSONB) == sa_cast({}, JSONB))
            .where(ScrapeProduct.api_product_id.is_(None))
            .where(ScrapeProduct.scrape_error.is_(None))
            .order_by(ScrapeProduct.scraped_at)
        )
        if limit > 0:
            stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def claim_pending(self, source: str, limit: int = 0) -> list[ScrapeProduct]:
        """Atomically claim pending rows using SELECT ... FOR UPDATE SKIP LOCKED.

        Two concurrent instances never get the same rows because SKIP LOCKED
        skips rows already locked by another transaction.
        Pass limit=0 (default) for no limit (all pending).
        """
        ids_stmt = (
            select(ScrapeProduct.id)
            .where(ScrapeProduct.source == source)
            .where(ScrapeProduct.raw_data.cast(JSONB) == sa_cast({}, JSONB))
            .where(ScrapeProduct.api_product_id.is_(None))
            .where(ScrapeProduct.scrape_error.is_(None))
            .order_by(ScrapeProduct.scraped_at)
            .with_for_update(skip_locked=True)
        )
        if limit > 0:
            ids_stmt = ids_stmt.limit(limit)
        ids_result = await self.db.execute(ids_stmt)
        ids = [row[0] for row in ids_result.fetchall()]
        if not ids:
            await self.db.commit()
            return []

        await self.db.execute(
            update(ScrapeProduct).where(ScrapeProduct.id.in_(ids)).values(scrape_error=PROCESSING_MARKER),
        )
        await self.db.commit()

        stmt = select(ScrapeProduct).where(ScrapeProduct.id.in_(ids)).order_by(ScrapeProduct.scraped_at)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_pending(self, source: str) -> int:
        """Count rows eligible for claiming (same filter as claim_pending)."""
        stmt = (
            select(func.count())
            .select_from(ScrapeProduct)
            .where(ScrapeProduct.source == source)
            .where(ScrapeProduct.raw_data.cast(JSONB) == sa_cast({}, JSONB))
            .where(ScrapeProduct.api_product_id.is_(None))
            .where(ScrapeProduct.scrape_error.is_(None))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def upsert(self, data: dict[str, Any]) -> ScrapeProduct:
        source = data["source"]
        source_id = data["source_id"]
        country = data["country"]
        stmt = select(ScrapeProduct).where(ScrapeProduct.source == source).where(ScrapeProduct.source_id == source_id).where(ScrapeProduct.country == country)
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.raw_data = data["raw_data"]
            existing.source_url = data.get("source_url", existing.source_url)
            existing.source_category = data.get("source_category", existing.source_category)
            existing.currency = data.get("currency", existing.currency)
            existing.scrape_error = None
            return existing
        instance = ScrapeProduct(
            source=source,
            source_id=source_id,
            source_url=data.get("source_url"),
            source_category=data.get("source_category"),
            country=country,
            currency=data.get("currency"),
            raw_data=data["raw_data"],
        )
        self.db.add(instance)
        await self.db.flush()
        return instance

    async def complete_claimed(self, data: dict[str, Any], original_source_id: str, original_source_url: str) -> ScrapeProduct:
        """Complete a claimed sitemap row in place, avoiding duplicate source_id rows.

        The claimed sitemap row uses the URL p-code as source_id (e.g. "1023211"),
        while scraped data carries the canonical JSON-LD product id (e.g. "545409133").
        This migrates the claimed row to the canonical id, or reuses an existing
        canonical row from a previous duplicate run, so the sitemap row is consumed
        and never re-claimed.
        """
        source = data["source"]
        country = data["country"]
        canonical_id = data["source_id"]

        stmt = select(ScrapeProduct).where(ScrapeProduct.source == source).where(ScrapeProduct.source_id == original_source_id).where(ScrapeProduct.country == country)
        existing = (await self.db.execute(stmt)).scalar_one_or_none()

        if existing is not None and existing.source_id != canonical_id:
            canonical = await self.get_by_key(source, canonical_id, country)
            if canonical is not None:
                await self.db.delete(existing)
                existing = canonical
            else:
                existing.source_id = canonical_id

        if existing is None:
            return await self.upsert(data)

        existing.source_url = data.get("source_url", existing.source_url)
        existing.source_category = data.get("source_category", existing.source_category)
        existing.currency = data.get("currency", existing.currency)
        existing.raw_data = data["raw_data"]
        existing.scrape_error = None
        return existing

    async def mark_error(self, source: str, source_id: str, country: str, error: str) -> None:
        stmt = select(ScrapeProduct).where(ScrapeProduct.source == source).where(ScrapeProduct.source_id == source_id).where(ScrapeProduct.country == country)
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.scrape_error = error

    async def release_processing(self, source: str, ids: list[str] | None = None) -> None:
        """Reset this instance's own stale __processing__ markers back to NULL.

        With multiple scraper instances running concurrently, only the rows
        claimed by this instance may be released — a global sweep would unmark
        another instance's in-flight rows and cause duplicate scraping.
        """
        stmt = update(ScrapeProduct).where(ScrapeProduct.source == source).where(ScrapeProduct.scrape_error == PROCESSING_MARKER).values(scrape_error=None)
        if ids is not None:
            stmt = stmt.where(ScrapeProduct.id.in_(ids))
        await self.db.execute(stmt)
        await self.db.commit()

    async def release_stale_processing(self, source: str, older_than_minutes: int = 30) -> int:
        """Reset __processing__ markers older than the cutoff (crash recovery).

        Rows claimed by a worker that died mid-run are re-claimable after the
        timeout so a fresh instance can pick them up.
        """
        cutoff = datetime.now(UTC) - timedelta(minutes=older_than_minutes)
        stmt = update(ScrapeProduct).where(ScrapeProduct.source == source).where(ScrapeProduct.scrape_error == PROCESSING_MARKER).where(ScrapeProduct.updated_at < cutoff).values(scrape_error=None)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return cast(CursorResult[Any], result).rowcount or 0
