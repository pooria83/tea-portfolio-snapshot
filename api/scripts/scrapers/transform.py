"""
Transform: sync scraped products (api_product_id IS NULL) to the API.

Usage:
    uv run scripts/scrapers/transform.py
    uv run scripts/scrapers/transform.py --limit 10
    uv run scripts/scrapers/transform.py --limit 10 --dry-run
    uv run scripts/scrapers/transform.py --source zara
    uv run scripts/scrapers/transform.py --api-url http://localhost:8000 --api-token <jwt>

    # Or use API key instead of JWT
    uv run scripts/scrapers/transform.py --api-key tea_xxxxxxxxxxxx

    # Sync a single product by its numeric ID
    uv run scripts/scrapers/transform.py --source-id 00706757

    # Sync a single product by its full URL (auto-scrapes if not in DB)
    uv run scripts/scrapers/transform.py --url "https://www.zara.com/kw/en/checked-cropped-fit-jacket-p00706757.html" \\
        --cookie-file /tmp/zara_cookies.txt
"""

import argparse
import asyncio
import contextlib
import re
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.scrape_product import ScrapeProduct
from scripts.scrapers.api_client import ScraperAPIClient

logger.add(sys.stderr, level="INFO")


def _product_id_from_url(url: str) -> str | None:
    m = re.search(r"p(\d{5,})(?:\.|\?|$)", url)
    if m:
        return m.group(1)
    m = re.search(r"v1=(\d+)", url)
    return m.group(1) if m else None


@contextlib.asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(settings.database_url, echo=False, pool_size=5)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            with contextlib.suppress(Exception):
                await session.rollback()
            raise
        finally:
            await session.close()
    await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync scraped products to the API")
    parser.add_argument("--limit", type=int, default=0, help="Max products to sync (0 = all)")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Count only, no POSTs")
    parser.add_argument("--source", type=str, default="", help="Filter by scraper name (e.g. zara)")
    parser.add_argument("--source-id", type=str, default="", help="Sync a specific product by source_id")
    parser.add_argument("--url", type=str, default="", help="Full Zara product URL to scrape and/or sync")
    parser.add_argument("--category", type=str, default="", help="Category for single URL (e.g. man/jackets)")
    parser.add_argument("--cookie", type=str, default="", help="Raw cookie string (for auto-scrape)")
    parser.add_argument("--cookie-file", type=str, default=None, help="File containing cookie string (for auto-scrape)")
    parser.add_argument("--api-url", type=str, default=settings.zara_scraper_api_base_url, help="API base URL (default: from settings)")
    parser.add_argument("--api-token", type=str, default="", help="API JWT token (default: from settings)")
    parser.add_argument("--api-key", type=str, default="", help="API key (alternative to --api-token)")
    parser.add_argument("--concurrency", type=int, default=5, help="Max concurrent product syncs (default: 5)")
    return parser.parse_args()


async def _sync_one_product(session: AsyncSession, api_client: ScraperAPIClient, row: ScrapeProduct) -> dict[str, int]:
    source_category = row.source_category or ""
    if not source_category:
        logger.warning(
            "source_category is empty for {} ({}) — transform may fail. Re-scrape with --category to set it.",
            row.source_id,
            row.source_url,
        )
    result = {
        "source": row.source,
        "source_id": row.source_id,
        "source_url": row.source_url or "",
        "source_category": source_category,
        "country": row.country,
        "currency": row.currency or "",
        "raw_data": row.raw_data,
    }
    pid = await api_client.sync_product(result)
    return {"created": 1 if pid else 0, "errors": 0 if pid else 1, "total": 1}


async def main() -> None:
    args = parse_args()

    api_token = args.api_token or settings.zara_scraper_api_token or ""
    api_key = args.api_key or ""
    if not api_token and not api_key:
        logger.error("API token or API key required. Set ZARA_SCRAPER_API_TOKEN or pass --api-token / --api-key.")
        raise SystemExit(1)

    async with get_session() as session:
        api_client = ScraperAPIClient(session, args.api_url, api_token=api_token, api_key=api_key)
        try:
            if args.source_id or args.url:
                source_id = args.source_id
                if args.url and not source_id:
                    parsed = _product_id_from_url(args.url)
                    if not parsed:
                        logger.error("Could not extract product ID from URL: {}", args.url)
                        raise SystemExit(1)
                    source_id = parsed
                    logger.info("Extracted product ID {} from URL", source_id)

                stmt = select(ScrapeProduct).where(ScrapeProduct.source_id == source_id)
                if args.source:
                    stmt = stmt.where(ScrapeProduct.source == args.source)
                row = (await session.execute(stmt)).scalar_one_or_none()

                if row:
                    if row.api_product_id is not None:
                        logger.info("Product {} ({}) is already synced (api_product_id={})", source_id, row.source_url, row.api_product_id)
                        stats = {"created": 0, "errors": 0, "total": 1}
                    else:
                        logger.info("Found pending product: {}", source_id)
                        if args.dry_run:
                            return
                        stats = await _sync_one_product(session, api_client, row)
                elif args.url:
                    # Auto-scrape: product not in DB, scrape it first
                    cookie = args.cookie
                    if args.cookie_file:
                        cookie = Path(args.cookie_file).read_text().strip()
                    if not cookie:
                        logger.error(
                            "Product {} not found in DB. To auto-scrape, provide --cookie or --cookie-file.",
                            source_id,
                        )
                        raise SystemExit(1)

                    logger.info("Scraping product {} from {} ...", source_id, args.url)
                    from app.scrapers.zara.scraper import ZaraScraper

                    scraper = ZaraScraper(session)
                    scrape_kwargs: dict[str, object] = {"cookie": cookie, "urls": [args.url]}
                    if args.category:
                        scrape_kwargs["category"] = args.category
                    await scraper.run(**scrape_kwargs)

                    row = (await session.execute(select(ScrapeProduct).where(ScrapeProduct.source_id == source_id))).scalar_one_or_none()
                    if not row:
                        logger.error("Scraper ran but product {} not found in DB", source_id)
                        stats = {"created": 0, "errors": 1, "total": 1}
                    elif row.api_product_id is not None:
                        logger.info("Product {} scraped and already synced", source_id)
                        stats = {"created": 0, "errors": 0, "total": 1}
                    else:
                        logger.info("Scraped, now syncing product {} ...", source_id)
                        if args.dry_run:
                            return
                        stats = await _sync_one_product(session, api_client, row)
                else:
                    logger.info("Product {} not found in DB", source_id)
                    stats = {"created": 0, "errors": 0, "total": 1}
            else:
                count_stmt = (
                    select(func.count())
                    .select_from(ScrapeProduct)
                    .where(
                        ScrapeProduct.api_product_id.is_(None),
                        ScrapeProduct.images_cached.is_(True),
                        ScrapeProduct.scrape_error.is_(None),
                    )
                )
                if args.source:
                    count_stmt = count_stmt.where(ScrapeProduct.source == args.source)
                total_pending = (await session.execute(count_stmt)).scalar() or 0
                if total_pending == 0:
                    logger.info("No pending products to sync")
                    return
                logger.info("Found {} pending product(s)", total_pending)
                if args.dry_run:
                    return
                stats = await api_client.sync_pending(limit=args.limit, source=args.source, concurrency=args.concurrency)
        finally:
            await api_client.close()

    logger.info(
        "Done: {} created, {} errors (out of {} total)",
        stats.get("created", 0),
        stats.get("errors", 0),
        stats.get("total", 0),
    )


if __name__ == "__main__":
    asyncio.run(main())
