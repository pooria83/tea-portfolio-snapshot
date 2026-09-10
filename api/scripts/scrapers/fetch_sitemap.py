"""
Fetch Zara product sitemap → insert all product URLs into scrape_products.

Downloads the AE product sitemap (gzipped XML), converts URLs to KW domain,
and inserts them with raw_data={} for Phase 2 scraping.

Usage:
    # Full fetch (11K+ products)
    uv run scripts/scrapers/fetch_sitemap.py --cookie-file ./cookies.txt

    # Local sitemap file + mark stale non-scraped rows dead
    uv run scripts/scrapers/fetch_sitemap.py --sitemap-file ./sitemap-product-ae-en.xml --mark-stale-dead

    # Dry run (preview without inserting)
    uv run scripts/scrapers/fetch_sitemap.py --cookie-file ./cookies.txt --limit 5 --dry-run

    # Custom sitemap URL
    uv run scripts/scrapers/fetch_sitemap.py --cookie-file ./cookies.txt --sitemap-url "https://www.zara.com/sitemaps/sitemap-product-ae-en.xml.gz"
"""

import argparse
import asyncio
import contextlib
import gzip
import json
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.repositories.scrape_product import ScrapeProductRepository

logger.add(sys.stderr, level="INFO")

COUNTRY = "kw"
CURRENCY = "KWD"

SITEMAP_DEFAULT = "https://www.zara.com/sitemaps/sitemap-product-ae-en.xml.gz"
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


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
    parser = argparse.ArgumentParser(description="Fetch Zara product sitemap and insert into scrape_products")
    parser.add_argument("--sitemap-url", type=str, default=SITEMAP_DEFAULT, help="URL of the gzipped product sitemap")
    parser.add_argument("--sitemap-file", type=str, default="", help="Path to a local product sitemap XML file (alternative to --sitemap-url)")
    parser.add_argument("--cookie-file", type=str, default="cookies.txt", help="File containing cookie string")
    parser.add_argument("--scraper", type=str, default="zara", help="Scraper name for DB header lookup (default: zara)")
    parser.add_argument("--limit", type=int, default=0, help="Max product URLs to insert (0 = all)")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Parse and print URLs without inserting")
    parser.add_argument(
        "--mark-stale-dead",
        action="store_true",
        default=False,
        help="After inserting, mark all non-scraped zara rows absent from the sitemap as dead_product and reset __processing__ rows present in the sitemap so they get re-claimed",
    )
    return parser.parse_args()


async def download_sitemap(url: str, cookie_str: str) -> bytes:
    """Download the gzipped sitemap using Playwright (full browser session)."""
    import http.cookies

    from playwright.async_api import async_playwright

    download_path: str | None = None

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0",
        )

        sc = http.cookies.SimpleCookie(cookie_str)
        for key, morsel in sc.items():
            with contextlib.suppress(Exception):
                await context.add_cookies(
                    [
                        {"name": key, "value": morsel.value, "domain": ".zara.com", "path": "/"},
                    ]
                )

        page = await context.new_page()
        download_info: dict[str, Any] = {"obj": None}

        def on_download(dl: Any) -> None:
            download_info["obj"] = dl

        page.on("download", on_download)

        try:
            await page.goto("https://www.zara.com/kw/en/", wait_until="domcontentloaded", timeout=20000)
            logger.info("Session established on zara.com/kw/en")
        except Exception as exc:
            logger.warning("Main page load: {}", exc)

        try:
            await page.goto(url, timeout=30000)
        except Exception as exc:
            logger.info("Sitemap navigation: {} (expected — triggers file download)", exc)

        await asyncio.sleep(3)

        dl_obj = download_info.get("obj")
        if dl_obj is None:
            raise RuntimeError("No download event fired — sitemap URL may be blocked")

        import shutil

        dl_path = await dl_obj.path()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml.gz") as tmp:
            shutil.copy(dl_path, tmp.name)
            download_path = tmp.name
        logger.info("Sitemap downloaded to {}", download_path)
        await browser.close()

    if not download_path:
        raise RuntimeError("Failed to download sitemap")
    data = Path(download_path).read_bytes()
    Path(download_path).unlink(missing_ok=True)
    return data


def parse_sitemap_urls(raw_data: bytes) -> list[str]:
    """Parse XML sitemap (gzipped or plain) and return all product <loc> URLs."""
    try:
        xml_content = gzip.decompress(raw_data)
    except OSError:
        xml_content = raw_data
    root = ET.fromstring(xml_content)
    urls: list[str] = []
    for url_elem in root.findall("sm:url/sm:loc", SITEMAP_NS):
        if url_elem is not None and url_elem.text:
            urls.append(url_elem.text)
    return urls


def extract_sitemap_codes(all_urls: list[str]) -> set[str]:
    """Extract the unique normalized p-codes (leading zeros stripped) from sitemap URLs.

    Handles p<digits> (standard), pT<digits> (set products), pC<digits> (gift cards)
    and pG<digits> (kids) — the letter prefix is kept to avoid id collisions.
    """
    codes: set[str] = set()
    for url in all_urls:
        m = re.search(r"-p([A-Z]?)(\d+)\.html", url)
        if m:
            prefix, digits = m.group(1), m.group(2).lstrip("0") or m.group(2)
            codes.add(f"{prefix}{digits}" if prefix else digits)
    return codes


async def mark_stale_dead(session: AsyncSession, codes: set[str]) -> tuple[int, int]:
    """Mark non-scraped rows absent from the sitemap as dead_product; reset stuck
    __processing__ rows that ARE in the sitemap so the next run re-claims them.

    Both filters must run against the FULL code set in a single statement —
    splitting into chunks would let a row belonging to one chunk be marked by a
    sibling chunk's NOT IN filter.

    Returns (marked_dead, reset_processing).
    """
    if not codes:
        return 0, 0
    code_list = sorted(codes)
    result = await session.execute(
        text(
            "UPDATE scrape_products SET scrape_error = 'dead_product' WHERE source = 'zara' AND raw_data::text = '{}' AND scrape_error IS DISTINCT FROM 'dead_product' AND source_id NOT IN :codes"
        ).bindparams(bindparam("codes", expanding=True)),
        {"codes": code_list},
    )
    marked_dead = int(result.rowcount or 0)  # type: ignore[attr-defined]
    result = await session.execute(
        text("UPDATE scrape_products SET scrape_error = NULL WHERE source = 'zara' AND scrape_error = '__processing__' AND source_id IN :codes").bindparams(bindparam("codes", expanding=True)),
        {"codes": code_list},
    )
    reset_processing = int(result.rowcount or 0)  # type: ignore[attr-defined]
    return marked_dead, reset_processing


async def resolve_db_cookie(scraper: str) -> str:
    """Read the scraper's raw header block from the DB and extract its Cookie string."""
    from app.repositories.scraper_header import ScraperHeaderRepository
    from app.scrapers.zara.header_parser import validate_header_block

    async with get_session() as session:
        repo = ScraperHeaderRepository(session)
        row = await repo.get_by_name(scraper)
    if row is None or not row.header:
        return ""
    try:
        info = validate_header_block(row.header)
    except ValueError:
        return ""
    return info["cookie"] or ""


async def main() -> None:
    args = parse_args()

    if args.sitemap_file:
        sitemap_path = Path(args.sitemap_file)
        if not sitemap_path.is_file():
            logger.error("Sitemap file not found: {}", sitemap_path)
            raise SystemExit(1)
        raw_data = sitemap_path.read_bytes()
        logger.info("Reading sitemap from local file {} ({} bytes) ...", sitemap_path, len(raw_data))
    else:
        cookie = ""
        if args.cookie_file:
            cookie = Path(args.cookie_file).read_text().strip()
        if not cookie:
            cookie = await resolve_db_cookie(args.scraper)
            if not cookie:
                logger.error(
                    "No cookies provided. Use --cookie-file, or set the header for scraper '{}' in the admin panel (Admin → Settings → Scrapers).",
                    args.scraper,
                )
                raise SystemExit(1)

        logger.info("Downloading sitemap from {} ...", args.sitemap_url)
        raw_data = await download_sitemap(args.sitemap_url, cookie)

    logger.info("Parsing sitemap XML ({} bytes) ...", len(raw_data))
    all_urls = parse_sitemap_urls(raw_data)

    kw_urls: list[str] = []
    for url in all_urls:
        if "-p" not in url or not url.endswith(".html"):
            continue
        kw_url = url.replace("/ae/en/", "/kw/en/")
        kw_urls.append(kw_url)

    logger.info("Product URLs: {} total → {} KW-adapted", len(all_urls), len(kw_urls))

    if args.limit > 0:
        kw_urls = kw_urls[: args.limit]
        logger.info("Limited to {} URLs", len(kw_urls))

    if args.dry_run:
        print(f"=== Dry run: {len(kw_urls)} URLs would be inserted ===")
        for u in kw_urls[:10]:
            print(f"  {u}")
        if len(kw_urls) > 10:
            print(f"  ... and {len(kw_urls) - 10} more")
        return

    async with get_session() as session:
        repo = ScrapeProductRepository(session)
        inserted = 0
        skipped = 0
        errors = 0

        for url in kw_urls:
            m = re.search(r"-p([A-Z]?)(\d+)\.html", url)
            if not m:
                errors += 1
                continue
            prefix, digits = m.group(1), m.group(2).lstrip("0") or m.group(2)
            source_id = f"{prefix}{digits}" if prefix else digits

            existing = await repo.exists("zara", source_id, COUNTRY)
            if not existing:
                existing = await repo.exists_by_url("zara", url)
            if existing:
                skipped += 1
                continue

            await repo.upsert(
                {
                    "source": "zara",
                    "source_id": source_id,
                    "source_url": url,
                    "source_category": "",
                    "country": COUNTRY,
                    "currency": CURRENCY,
                    "raw_data": {},
                }
            )
            inserted += 1

            if (inserted + skipped) % 1000 == 0:
                await session.commit()
                logger.info("Progress: {} inserted, {} skipped, {} errors", inserted, skipped, errors)

        await session.commit()

        marked_dead = 0
        reset_processing = 0
        if args.mark_stale_dead:
            codes = extract_sitemap_codes(all_urls)
            marked_dead, reset_processing = await mark_stale_dead(session, codes)
            await session.commit()

    logger.info("Done: {} inserted, {} skipped, {} errors", inserted, skipped, errors)
    if args.mark_stale_dead:
        logger.info("Stale cleanup: {} marked dead_product, {} __processing__ reset to re-claim", marked_dead, reset_processing)
    print(
        json.dumps(
            {
                "inserted": inserted,
                "skipped": skipped,
                "errors": errors,
                "total": len(kw_urls),
                "marked_dead": marked_dead,
                "reset_processing": reset_processing,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
