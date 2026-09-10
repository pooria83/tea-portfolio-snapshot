"""
Download images for scraped products to disk cache (no MinIO, no API).

Job 1 of the split pipeline:
  - Reads scraped products where images_cached = False
  - Downloads all product images to the cache directory
  - Marks images_cached = True on success

Usage:
    uv run scripts/scrapers/download_images.py
    uv run scripts/scrapers/download_images.py --limit 100
    uv run scripts/scrapers/download_images.py --limit 100 --concurrency 20
"""

import argparse
import asyncio
import sys

from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.scrape_product import ScrapeProduct
from scripts.scrapers.api_client import IMAGE_CACHE_DIR, _extract_ext_from_url

logger.add(sys.stderr, level="INFO")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download product images to disk cache")
    parser.add_argument("--limit", type=int, default=0, help="Max products to process (0 = all)")
    parser.add_argument("--concurrency", type=int, default=10, help="Max concurrent image downloads")
    parser.add_argument("--source", type=str, default="", help="Filter by scraper name (e.g. zara)")
    return parser.parse_args()


def _extract_image_urls(raw_data: dict) -> list[str]:
    """Extract all unique image URLs from product raw_data."""
    urls: set[str] = set()

    images = raw_data.get("images", [])
    if isinstance(images, list):
        for img in images:
            url = img.get("url", "") if isinstance(img, dict) else ""
            if url:
                urls.add(url)

    images_per_color = raw_data.get("images_per_color", {})
    if isinstance(images_per_color, dict):
        for color_images in images_per_color.values():
            if isinstance(color_images, list):
                for img in color_images:
                    url = img.get("url", "") if isinstance(img, dict) else ""
                    if url:
                        urls.add(url)

    return list(urls)


async def main() -> None:
    args = parse_args()

    engine = create_async_engine(settings.database_url, echo=False, pool_size=5)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        base_where = (
            ScrapeProduct.api_product_id.is_(None),
            ScrapeProduct.images_cached.is_(False),
            ScrapeProduct.scrape_error.is_(None),
            ScrapeProduct.raw_data.isnot(None),
        )
        count_stmt = select(func.count()).select_from(ScrapeProduct).where(*base_where)
        if args.source:
            count_stmt = count_stmt.where(ScrapeProduct.source == args.source)
        total = (await session.execute(count_stmt)).scalar() or 0
        if total == 0:
            logger.info("No products pending image download")
            return
            logger.info("Found {} products pending image download", total)

        stmt = select(ScrapeProduct.id, ScrapeProduct.source_id, ScrapeProduct.raw_data).where(*base_where)
        if args.source:
            stmt = stmt.where(ScrapeProduct.source == args.source)
        stmt = stmt.order_by(ScrapeProduct.created_at)
        if args.limit > 0:
            stmt = stmt.limit(args.limit)
        rows = (await session.execute(stmt)).all()

    sem = asyncio.Semaphore(args.concurrency)

    async def _download_single(url: str) -> bool:
        async with sem:
            ext = _extract_ext_from_url(url)
            cache_key = hashlib.md5(url.encode()).hexdigest() + ext
            cache_path = IMAGE_CACHE_DIR / cache_key
            if cache_path.exists():
                return True

            import httpx

            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0",
                    "Accept": "image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.zara.com/",
                    "Sec-Fetch-Dest": "image",
                    "Sec-Fetch-Mode": "no-cors",
                    "Sec-Fetch-Site": "cross-site",
                }
                async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                    resp = await client.get(url, headers=headers)
                    resp.raise_for_status()
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_bytes(resp.content)
                return True
            except Exception as exc:
                logger.warning("Download failed for {}: {}", url, exc)
                return False

    product_urls: list[tuple[str, list[str]]] = []
    for row_id, source_id, raw_data in rows:
        if not raw_data or raw_data == {}:
            continue
        urls = _extract_image_urls(raw_data)
        if urls:
            product_urls.append((row_id, urls))
        else:
            logger.info("No images for {}, marking cached", source_id)
            async with factory() as s:
                await s.execute(update(ScrapeProduct).where(ScrapeProduct.id == row_id).values(images_cached=True))
                await s.commit()

    total_ok = 0
    total_fail = 0
    for idx, (row_id, urls) in enumerate(product_urls):
        logger.info("[{}/{}] Downloading {} images for product {} ...", idx + 1, len(product_urls), len(urls), row_id[:8])
        results = await asyncio.gather(*[_download_single(u) for u in urls])
        ok = sum(results)
        fail = len(results) - ok
        total_ok += ok
        total_fail += fail

        async with factory() as s:
            await s.execute(update(ScrapeProduct).where(ScrapeProduct.id == row_id).values(images_cached=True))
            await s.commit()

    logger.info("Done: {} images downloaded successfully, {} failed", total_ok, total_fail)

    await engine.dispose()


if __name__ == "__main__":
    import hashlib

    asyncio.run(main())
