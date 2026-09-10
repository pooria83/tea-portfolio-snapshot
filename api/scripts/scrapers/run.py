"""
Usage:
    # Scrape pending products from DB (after crawl.py has populated scrape_products)
    uv run scripts/scrapers/run.py zara --cookie-file ./cookies.txt

    # Scrape with limit (for testing)
    uv run scripts/scrapers/run.py zara --cookie-file ./cookies.txt --limit 10

    # Scrape specific product URLs
    uv run scripts/scrapers/run.py zara --urls "https://www.zara.com/kw/en/..." --cookie-file ./cookies.txt

    # Single product with explicit category (recommended for debugging)
    uv run scripts/scrapers/run.py zara --urls "https://www.zara.com/kw/en/..." --category man/jackets --cookie-file ./cookies.txt

    # Direct cookie string
    uv run scripts/scrapers/run.py zara --cookie "$(cat cookies.txt)"

"""

import argparse
import asyncio
import contextlib
import json
import math
import signal
import subprocess
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.scrapers.zara.scraper  # noqa: F401 — registers scrapers
from app.core.config import settings
from app.scrapers.exceptions import ScraperAuthError
from app.scrapers.registry import get_scraper

logger.remove()
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
    parser = argparse.ArgumentParser(description="Run a product scraper")
    parser.add_argument("scraper", type=str, help="Scraper name (e.g. zara)")
    parser.add_argument("--urls", nargs="*", default=[], help="Product URLs to scrape")
    parser.add_argument("--file", type=str, default=None, help="File containing URLs (one per line)")
    parser.add_argument("--limit", type=int, default=0, help="Max pending products to process from DB (0 = all)")
    parser.add_argument("--cookie", type=str, default="", help="Raw cookie string")
    parser.add_argument("--cookie-file", type=str, default=None, help="File containing cookie string")
    parser.add_argument("--category", type=str, default="", help="Category for single URLs (e.g. man/jackets)")
    parser.add_argument("--concurrency", "-j", type=int, default=5, help="Max concurrent product scrapes")
    parser.add_argument("--workers", type=int, default=1, help="Number of scraper processes to run (each with its own browser context)")
    parser.add_argument("--batch-size", type=int, default=50, help="Products claimed and processed per DB batch (bounds memory)")
    parser.add_argument("--browser-restart-every", type=int, default=50, help="Restart the browser every N products to release memory (0 = never)")
    parser.add_argument("--worker-index", type=int, default=None, help=argparse.SUPPRESS)
    return parser.parse_args()


def per_worker_limit(limit: int, workers: int) -> int:
    """Split a total limit across N workers (ceil so the sum >= limit)."""
    if limit <= 0 or workers <= 0:
        return 0
    return math.ceil(limit / workers)


async def run_workers(args: argparse.Namespace) -> int:
    """Spawn N scraper child processes, each with its own browser context.

    The parent queries the total pending row count and hands each child an
    explicit --limit=ceil(total/N). Each child then claims a disjoint set via
    claim_pending's FOR UPDATE SKIP LOCKED. Returns the first non-zero child
    exit code (0 when all succeed).
    """
    if args.workers <= 1:
        return -1
    if args.urls or args.file:
        logger.error("--workers cannot be combined with --urls/--file (per-instance URL lists are not shared).")
        raise SystemExit(1)

    total = args.limit
    if total <= 0:
        from app.repositories.scrape_product import ScrapeProductRepository

        async with get_session() as session:
            total = await ScrapeProductRepository(session).count_pending(args.scraper)
        logger.info("Pending rows for '{}': {}", args.scraper, total)
    per_worker = per_worker_limit(total, args.workers)

    script = str(Path(__file__).resolve())

    def build_child_argv(idx: int) -> list[str]:
        argv = [sys.executable, script, args.scraper]
        if per_worker > 0:
            argv.append(f"--limit={per_worker}")
        if args.cookie:
            argv.append(f"--cookie={args.cookie}")
        if args.cookie_file:
            argv.append(f"--cookie-file={args.cookie_file}")
        if args.category:
            argv.append(f"--category={args.category}")
        if args.concurrency != 5:
            argv.append(f"--concurrency={args.concurrency}")
        if args.batch_size != 50:
            argv.append(f"--batch-size={args.batch_size}")
        if args.browser_restart_every != 50:
            argv.append(f"--browser-restart-every={args.browser_restart_every}")
        argv.append(f"--worker-index={idx}")
        return argv

    logger.info("Launching {} scraper workers (per-worker limit: {})", args.workers, per_worker if per_worker else "all")
    procs: list[subprocess.Popen[bytes]] = []

    def _forward_signal(signum: int, _frame: object) -> None:
        for p in procs:
            with contextlib.suppress(Exception):
                p.send_signal(signum)

    previous_int = signal.signal(signal.SIGINT, _forward_signal)
    previous_term = signal.signal(signal.SIGTERM, _forward_signal)

    try:
        for idx in range(args.workers):
            child_argv = build_child_argv(idx)
            logger.info("[launcher] starting worker {}", idx)
            procs.append(subprocess.Popen(child_argv, cwd=Path.cwd()))
        rc = 0
        for idx, p in enumerate(procs):
            proc_rc = p.wait()
            logger.info("[launcher] worker {} exited with code {}", idx, proc_rc)
            if proc_rc != 0 and rc == 0:
                rc = proc_rc
        return rc
    finally:
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous_term)


async def main() -> None:
    args = parse_args()

    if args.worker_index is None and args.workers > 1:
        rc = await run_workers(args)
        sys.exit(rc)

    if args.worker_index is not None:
        logger.remove()
        logger.add(
            sys.stderr,
            level="INFO",
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
            f"<cyan>worker {args.worker_index}</cyan> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        )

    cookie = args.cookie
    if args.cookie_file:
        cookie = Path(args.cookie_file).read_text().strip()

    scraper_kwargs: dict[str, object] = {
        "cookie": cookie,
        "concurrency": args.concurrency,
        "batch_size": args.batch_size,
        "browser_restart_every": args.browser_restart_every,
    }

    if args.urls or args.file:
        urls = list(args.urls or [])
        if args.file:
            with open(args.file) as f:
                urls.extend(line.strip() for line in f if line.strip())
        if not urls:
            logger.error("No URLs provided via --urls or --file.")
            raise SystemExit(1)
        scraper_kwargs["urls"] = urls
        if args.category:
            scraper_kwargs["category"] = args.category
    else:
        scraper_kwargs["limit"] = args.limit
        logger.info("Reading pending products from DB (limit={})", args.limit if args.limit else "all")

    scraper_cls = get_scraper(args.scraper)
    async with get_session() as session:
        scraper = scraper_cls(session)
        try:
            results = await scraper.run(**scraper_kwargs)
        except ScraperAuthError as exc:
            logger.error(str(exc))
            raise SystemExit(1) from exc

    logger.info(
        "Results: scraped={}, skipped={}, errors={} (total found: {})",
        results.get("scraped", 0),
        results.get("skipped", 0),
        results.get("errors", 0),
        results.get("total_found", 0),
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
