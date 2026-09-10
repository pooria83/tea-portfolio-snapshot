"""
DEPRECATED: Replaced by scripts/scrapers/fetch_sitemap.py which downloads the
product sitemap (~11K product URLs) directly instead of crawling category pages.
Kept for reference only.

Legacy usage:
    # Full crawl from sitemap
    uv run scripts/scrapers/crawl.py --sitemap scripts/seed_data/zara_kw_categories.txt --cookie-file ./cookies.txt

    # Limit to first N categories (for testing)
    uv run scripts/scrapers/crawl.py --sitemap scripts/seed_data/zara_kw_categories.txt --cookie-file ./cookies.txt --limit 5

    # Direct cookie string
    uv run scripts/scrapers/crawl.py --sitemap scripts/seed_data/zara_kw_categories.txt --cookie "$(cat cookies.txt)"
"""

import argparse
import asyncio
import contextlib
import json
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.scrapers.zara.crawler import ZaraCrawler

logger.add(sys.stderr, level="INFO")


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
    parser = argparse.ArgumentParser(description="Crawl Zara categories from sitemap")
    parser.add_argument("--sitemap", type=str, default="", help="Path to sitemap category file (one URL per line)")
    parser.add_argument("--url", type=str, default="", help="Single category URL to crawl (bypasses sitemap)")
    parser.add_argument("--cookie", type=str, default="", help="Raw cookie string")
    parser.add_argument("--cookie-file", type=str, default=None, help="File containing cookie string")
    parser.add_argument("--limit", type=int, default=0, help="Max categories to crawl (0 = all)")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    cookie = args.cookie
    if args.cookie_file:
        cookie = Path(args.cookie_file).read_text().strip()
    if not cookie:
        logger.error("No cookies provided. Use --cookie or --cookie-file.")
        raise SystemExit(1)

    async with get_session() as session:
        crawler = ZaraCrawler(session)
        kwargs: dict[str, object] = {"cookie": cookie, "limit": args.limit}
        if args.url:
            kwargs["url"] = args.url
        elif args.sitemap:
            kwargs["sitemap"] = args.sitemap
        else:
            logger.error("Specify --url or --sitemap.")
            raise SystemExit(1)
        results = await crawler.run(**kwargs)

    logger.info(
        "Results: found={}, inserted={}, skipped={}, errors={} (categories: {})",
        results.get("found", 0),
        results.get("inserted", 0),
        results.get("skipped", 0),
        results.get("errors", 0),
        results.get("total_categories", 0),
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
