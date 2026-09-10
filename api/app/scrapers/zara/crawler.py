"""
DEPRECATED: Replaced by scripts/scrapers/fetch_sitemap.py which downloads the
product sitemap (~11K URLs) directly instead of crawling category pages.
Kept for reference only.
"""

from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.scrape_product import ScrapeProductRepository
from app.scrapers.zara.browser_pool import BrowserPool
from app.scrapers.zara.exceptions import ScraperAuthError
from app.scrapers.zara.scraper import _extract_product_urls_from_category_html

COUNTRY = "kw"
CURRENCY = "KWD"


class ZaraCrawler:
    """Crawls Zara category URLs from a sitemap file and inserts
    discovered product URLs into scrape_products with raw_data={}.
    """

    def __init__(self, db: AsyncSession, cookie_file: str = "") -> None:
        self.db = db
        self.repo = ScrapeProductRepository(db)
        self.cookie_file = cookie_file

    async def run(self, **kwargs: object) -> dict[str, Any]:
        cookie_str = str(kwargs.get("cookie", ""))
        if not cookie_str and self.cookie_file:
            cookie_str = Path(self.cookie_file).read_text().strip()
        if not cookie_str:
            raise ScraperAuthError("No cookie provided — use --cookie or --cookie-file")

        single_url = str(kwargs.get("url", ""))
        sitemap_path = str(kwargs.get("sitemap", ""))

        if single_url:
            urls = [single_url]
            logger.info("Single URL mode: {}", single_url)
        elif sitemap_path:
            urls = Path(sitemap_path).read_text().strip().splitlines()
            urls = [u.strip() for u in urls if u.strip()]
            logger.info("Sitemap contains {} category URLs", len(urls))
        else:
            raise ValueError("Specify --url or --sitemap")

        limit_val = kwargs.get("limit", 0)
        max_categories = limit_val if isinstance(limit_val, int) else 0
        if max_categories > 0:
            urls = urls[:max_categories]

        pool = BrowserPool()
        await pool.start()

        try:
            found = 0
            inserted = 0
            skipped = 0
            errors = 0

            for cat_url in urls:
                try:
                    en_url = cat_url.replace("/kw/ar/", "/kw/en/")
                    html = await pool.fetch_html(en_url, cookie_str)

                    if "bm-verify" in html or len(html) < 5000:
                        logger.warning("Category {} returned block page", cat_url)
                        errors += 1
                        continue

                    products = _extract_product_urls_from_category_html(html, en_url)
                    for p in products:
                        logger.info("  Found: {} (ID={})", p["url"], p["product_id"])
                    found += len(products)

                    for prod in products:
                        source_id = prod["product_id"]
                        if await self.repo.exists("zara", source_id, COUNTRY):
                            skipped += 1
                            continue

                        await self.repo.upsert(
                            {
                                "source": "zara",
                                "source_id": source_id,
                                "source_url": prod["url"],
                                "source_category": cat_url,
                                "country": COUNTRY,
                                "currency": CURRENCY,
                                "raw_data": {},
                            }
                        )
                        inserted += 1

                    await self.db.commit()
                    logger.info(
                        "Category {}: {} products found, {} inserted (total found={}, inserted={})",
                        cat_url.rsplit("/", 1)[-1],
                        len(products),
                        inserted - (found - len(products)),
                        found,
                        inserted,
                    )
                except Exception as exc:
                    errors += 1
                    logger.exception("Error crawling {}: {}", cat_url, exc)

            return {
                "found": found,
                "inserted": inserted,
                "skipped": skipped,
                "errors": errors,
                "total_categories": len(urls),
            }
        finally:
            await pool.close()
