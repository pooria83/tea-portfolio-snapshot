from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scrape_product import ScrapeProduct
from app.repositories.scrape_product import PROCESSING_MARKER, ScrapeProductRepository
from scripts.scrapers.run import per_worker_limit


@pytest.fixture(autouse=True)
async def _clean_zara_rows(db_session: AsyncSession):
    yield
    await db_session.execute(delete(ScrapeProduct).where(ScrapeProduct.source == "zara"))
    await db_session.commit()


def _uid() -> str:
    return str(uuid.uuid4()).replace("-", "")[:12]


async def _seed_row(db: AsyncSession, source_id: str, source_url: str, error: str | None = None) -> ScrapeProduct:
    row = ScrapeProduct(
        source="zara",
        source_id=source_id,
        source_url=source_url,
        source_category="",
        country="kw",
        currency="KWD",
        raw_data={},
        scrape_error=error,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


class TestReleaseProcessing:
    async def test_scoped_release_only_clears_claimed_ids(self, db_session: AsyncSession):
        repo = ScrapeProductRepository(db_session)
        mine = await _seed_row(db_session, _uid(), "https://zara.test/mine.html", error=PROCESSING_MARKER)
        theirs = await _seed_row(db_session, _uid(), "https://zara.test/theirs.html", error=PROCESSING_MARKER)

        await repo.release_processing("zara", ids=[mine.id])
        await db_session.refresh(mine)
        await db_session.refresh(theirs)

        assert mine.scrape_error is None
        assert theirs.scrape_error == PROCESSING_MARKER

    async def test_none_ids_clears_nothing(self, db_session: AsyncSession):
        repo = ScrapeProductRepository(db_session)
        row = await _seed_row(db_session, _uid(), "https://zara.test/x.html", error=PROCESSING_MARKER)

        await repo.release_processing("zara", ids=[])
        await db_session.refresh(row)

        assert row.scrape_error == PROCESSING_MARKER

    async def test_other_source_unaffected(self, db_session: AsyncSession):
        repo = ScrapeProductRepository(db_session)
        zara_row = await _seed_row(db_session, _uid(), "https://zara.test/z.html", error=PROCESSING_MARKER)
        other = ScrapeProduct(
            source="other",
            source_id=_uid(),
            source_url="https://other.test/o.html",
            source_category="",
            country="kw",
            currency="KWD",
            raw_data={},
            scrape_error=PROCESSING_MARKER,
        )
        db_session.add(other)
        await db_session.commit()

        await repo.release_processing("zara", ids=[zara_row.id])
        await db_session.refresh(other)

        assert other.scrape_error == PROCESSING_MARKER


class TestReleaseStaleProcessing:
    async def test_releases_only_old_markers(self, db_session: AsyncSession):
        repo = ScrapeProductRepository(db_session)
        old = await _seed_row(db_session, _uid(), "https://zara.test/old.html", error=PROCESSING_MARKER)
        fresh = await _seed_row(db_session, _uid(), "https://zara.test/fresh.html", error=PROCESSING_MARKER)
        old.updated_at = datetime.now(UTC) - timedelta(hours=2)
        fresh.updated_at = datetime.now(UTC)
        await db_session.commit()

        released = await repo.release_stale_processing("zara", older_than_minutes=30)
        await db_session.refresh(old)
        await db_session.refresh(fresh)

        assert released == 1
        assert old.scrape_error is None
        assert fresh.scrape_error == PROCESSING_MARKER

    async def test_ignores_rows_without_marker(self, db_session: AsyncSession):
        repo = ScrapeProductRepository(db_session)
        row = await _seed_row(db_session, _uid(), "https://zara.test/no-marker.html")
        row.updated_at = datetime.now(UTC) - timedelta(hours=2)
        await db_session.commit()

        released = await repo.release_stale_processing("zara", older_than_minutes=30)

        assert released == 0
        await db_session.refresh(row)
        assert row.scrape_error is None


class TestPerWorkerLimit:
    def test_even_split(self):
        assert per_worker_limit(100, 4) == 25

    def test_ceil_split(self):
        assert per_worker_limit(10, 3) == 4

    def test_zero_limit_means_all(self):
        assert per_worker_limit(0, 4) == 0

    def test_single_worker(self):
        assert per_worker_limit(50, 1) == 50

    def test_zero_workers(self):
        assert per_worker_limit(50, 0) == 0


class TestCountPending:
    async def test_counts_only_claimable_rows(self, db_session: AsyncSession):
        repo = ScrapeProductRepository(db_session)
        await _seed_row(db_session, _uid(), "https://zara.test/a.html")
        await _seed_row(db_session, _uid(), "https://zara.test/b.html", error=PROCESSING_MARKER)
        await _seed_row(db_session, _uid(), "https://zara.test/c.html", error="category_unresolved")
        await _seed_row(db_session, _uid(), "https://zara.test/d.html")

        count = await repo.count_pending("zara")

        assert count == 2

    async def test_other_sources_not_counted(self, db_session: AsyncSession):
        repo = ScrapeProductRepository(db_session)
        await _seed_row(db_session, _uid(), "https://zara.test/a.html")
        other = ScrapeProduct(
            source="hm",
            source_id=_uid(),
            source_url="https://hm.test/x.html",
            source_category="",
            country="kw",
            currency="KWD",
            raw_data={},
            scrape_error=None,
        )
        db_session.add(other)
        await db_session.commit()

        assert await repo.count_pending("zara") == 1
        assert await repo.count_pending("hm") == 1


class TestExistsByUrl:
    async def test_finds_row_by_url_regardless_of_id(self, db_session: AsyncSession):
        repo = ScrapeProductRepository(db_session)
        url = "https://zara.test/p12345678.html"
        await _seed_row(db_session, "1234567", url)

        assert await repo.exists_by_url("zara", url) is True

    async def test_missing_url(self, db_session: AsyncSession):
        repo = ScrapeProductRepository(db_session)
        await _seed_row(db_session, _uid(), "https://zara.test/a.html")

        assert await repo.exists_by_url("zara", "https://zara.test/b.html") is False

    async def test_other_source_url_not_counted(self, db_session: AsyncSession):
        repo = ScrapeProductRepository(db_session)
        url = "https://zara.test/p12345678.html"
        await _seed_row(db_session, "1234567", url)
        other = ScrapeProduct(
            source="hm",
            source_id=_uid(),
            source_url=url,
            source_category="",
            country="kw",
            currency="KWD",
            raw_data={},
            scrape_error=None,
        )
        db_session.add(other)
        await db_session.commit()

        assert await repo.exists_by_url("hm", url) is True
        assert await repo.exists_by_url("zara", url) is True
