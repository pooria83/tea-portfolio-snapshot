from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scrape_product import ScrapeProduct
from app.repositories.scrape_product import PROCESSING_MARKER, ScrapeProductRepository
from app.scrapers.zara.scraper import _detail_id_from_url


def _uid() -> str:
    return str(uuid.uuid4()).replace("-", "")[:12]


async def _seed_row(db: AsyncSession, source_id: str, source_url: str, raw_data: dict | None = None, error: str | None = None) -> ScrapeProduct:
    row = ScrapeProduct(
        source="zara",
        source_id=source_id,
        source_url=source_url,
        source_category="",
        country="kw",
        currency="KWD",
        raw_data=raw_data if raw_data is not None else {},
        scrape_error=error,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


class TestDetailIdFromUrl:
    def test_strips_leading_zeros_p_code(self):
        assert _detail_id_from_url("https://www.zara.com/kw/en/knit-dress-p01023211.html") == "1023211"

    def test_returns_v1_id_stripped_when_no_p_code(self):
        assert _detail_id_from_url("https://www.zara.com/kw/en/shirt.html?v1=0456001") == "456001"

    def test_no_match_returns_none(self):
        assert _detail_id_from_url("https://www.zara.com/kw/en/non-product-page") is None


class TestCompleteClaimed:
    async def test_migrates_claimed_row_to_canonical_id(self, db_session: AsyncSession):
        repo = ScrapeProductRepository(db_session)
        sid = _uid()
        canonical = "545" + _uid()
        await _seed_row(db_session, source_id=sid, source_url="https://www.zara.com/kw/en/x-p.html")

        data = {
            "source": "zara",
            "source_id": canonical,
            "source_url": "https://www.zara.com/kw/en/x-p.html",
            "source_category": "Dresses",
            "country": "kw",
            "currency": "KWD",
            "raw_data": {"product_id": canonical, "name": "x"},
        }
        row = await repo.complete_claimed(data, original_source_id=sid, original_source_url="https://www.zara.com/kw/en/x-p.html")
        await db_session.commit()

        assert row.source_id == canonical
        assert row.raw_data["name"] == "x"
        assert row.scrape_error is None
        assert not (await repo.exists("zara", sid, "kw"))
        assert await repo.exists("zara", canonical, "kw")

    async def test_reuses_existing_canonical_row_and_deletes_duplicate(self, db_session: AsyncSession):
        repo = ScrapeProductRepository(db_session)
        sid = _uid()
        canonical = "545" + _uid()
        await _seed_row(db_session, source_id=sid, source_url="https://www.zara.com/kw/en/x-p.html")
        await _seed_row(
            db_session,
            source_id=canonical,
            source_url="https://www.zara.com/kw/en/x-p.html",
            raw_data={"product_id": canonical, "name": "stale"},
            error="no_json_ld_en",
        )

        data = {
            "source": "zara",
            "source_id": canonical,
            "source_url": "https://www.zara.com/kw/en/x-p.html",
            "source_category": "Dresses",
            "country": "kw",
            "currency": "KWD",
            "raw_data": {"product_id": canonical, "name": "fresh"},
        }
        row = await repo.complete_claimed(data, original_source_id=sid, original_source_url="https://www.zara.com/kw/en/x-p.html")
        await db_session.commit()

        assert row.source_id == canonical
        assert row.raw_data["name"] == "fresh"
        assert row.scrape_error is None
        assert not (await repo.exists("zara", sid, "kw"))
        assert await repo.exists("zara", canonical, "kw")

    async def test_no_origin_row_falls_back_to_upsert(self, db_session: AsyncSession):
        repo = ScrapeProductRepository(db_session)
        canonical = "545" + _uid()
        data = {
            "source": "zara",
            "source_id": canonical,
            "source_url": "https://www.zara.com/kw/en/x-p.html",
            "source_category": "Dresses",
            "country": "kw",
            "currency": "KWD",
            "raw_data": {"product_id": canonical},
        }
        row = await repo.complete_claimed(data, original_source_id="", original_source_url="")
        await db_session.commit()

        assert row.source_id == canonical
        assert await repo.exists("zara", canonical, "kw")


class TestClaimPending:
    async def test_marks_dead_product_and_never_reclaims(self, db_session: AsyncSession):
        repo = ScrapeProductRepository(db_session)
        sid = _uid()
        await _seed_row(db_session, source_id=sid, source_url="https://www.zara.com/kw/en/dead-p.html")

        claimed = await repo.claim_pending(source="zara")
        assert len(claimed) == 1
        assert claimed[0].scrape_error == PROCESSING_MARKER

        await repo.mark_error("zara", sid, "kw", "dead_product")
        await db_session.commit()

        remaining = await repo.claim_pending(source="zara")
        assert remaining == []
        refreshed = await repo.get_by_key("zara", sid, "kw")
        assert refreshed is not None
        assert refreshed.scrape_error == "dead_product"

    async def test_release_processing_only_resets_marker(self, db_session: AsyncSession):
        repo = ScrapeProductRepository(db_session)
        sid = _uid()
        await _seed_row(db_session, source_id=sid, source_url="https://www.zara.com/kw/en/dead-p.html", error="dead_product")

        await repo.release_processing("zara")

        refreshed = await repo.get_by_key("zara", sid, "kw")
        assert refreshed is not None
        assert refreshed.scrape_error == "dead_product"
