"""Reusable Camoufox page fetcher with bounded concurrency.

Akamai now binds the anti-bot cookies to the solving browser session, so
product HTML pages must be fetched through the same headless Camoufox context
that solved the bm-verify challenge. curl_cffi is still used for the AJAX
endpoints (extra-detail, availability, size-guide), which do not challenge.
"""

import asyncio
import contextlib
import http.cookies
from collections.abc import AsyncGenerator
from typing import Any, cast
from urllib.parse import urlparse

from loguru import logger

from app.scrapers.zara.cookie_mint import MINT_URL, _solved
from app.scrapers.zara.exceptions import ScraperAuthError
from app.scrapers.zara.parser import extract_product_data

MAX_RELOADS = 4
MAX_SOLVE_ATTEMPTS = 6


def _is_search_redirect(url: str) -> bool:
    """True when the URL is Zara's dead-product redirect target (/search?...).

    Removed products redirect to a search results page, e.g.
    /kw/en/search?searchTerm=...&section=WOMAN. Live product URLs are always
    /kw/en/<slug>-pNNNNNN.html — a slug may contain the word "search", so the
    path segment must be exactly "search" (optionally followed by more parts).
    """
    parts = [p for p in urlparse(url).path.split("/") if p]
    return "search" in parts


class CamoufoxFetcher:
    """Launches Camoufox headlessly once and reuses the context for all page fetches.

    Bounded by a semaphore (default 5 concurrent loads), like the legacy
    Playwright BrowserPool. Each fetch retries through interstitial/challenge
    pages; a still-challenged page is returned as-is so the scraper can treat
    it as a session issue.
    """

    def __init__(self, max_concurrent: int = 5) -> None:
        # Akamai throttles parallel navigations on a shared context, so fetches
        # are serialized regardless of the configured concurrency. The value is
        # kept for API compatibility only.
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(1)
        self._product_semaphore = asyncio.Semaphore(1)
        self._browser: Any = None
        self._context: Any = None

    @contextlib.asynccontextmanager
    async def serialized(self) -> AsyncGenerator[None, None]:
        """Serialize the whole product scrape (not just single fetches).

        The scraper wraps one product (EN+AR pages, per-color fetches, AJAX)
        in this lock so only one product is in flight at a time. Kept separate
        from ``_semaphore`` — ``fetch_html`` acquires that one nested inside.
        """
        async with self._product_semaphore:
            yield

    async def start(self, cookie_str: str = "") -> None:
        try:
            from camoufox.async_api import AsyncCamoufox
        except ImportError as exc:
            raise ScraperAuthError("camoufox is not installed — install the 'scrapers' extra (uv pip install -e '.[scrapers]')") from exc
        self._browser = await AsyncCamoufox(headless=True).__aenter__()
        self._context = await self._browser.new_context(locale="en-US", timezone_id="Europe/Dublin")
        if cookie_str:
            await self._set_cookies(cookie_str)
        await self._solve_challenge()
        logger.info("CamoufoxFetcher started (headless, max_concurrent={}, cookies={})", self.max_concurrent, bool(cookie_str))

    async def _solve_challenge(self) -> None:
        """Solve the Akamai bm-verify challenge inside this context.

        Anti-bot tokens (_abck, bm_sz, ...) are bound to the browser session that
        solved them, so seeding an old cookie string is not enough — the context
        itself must navigate through the challenge once. A stale/expired header
        (AJAX-valid but HTML-challenged) is detected here and surfaces as
        ScraperAuthError, which the scraper handles by minting fresh cookies.
        """
        page = await self._context.new_page()
        try:
            for attempt in range(1, MAX_SOLVE_ATTEMPTS + 1):
                try:
                    response = await page.goto(MINT_URL, wait_until="domcontentloaded", timeout=45000)
                except Exception as exc:
                    logger.warning("Camoufox challenge-solve goto failed (attempt {}): {}", attempt, exc)
                    await asyncio.sleep(1)
                    continue
                await asyncio.sleep(2)
                content = cast(str, await page.content())
                if response is not None and response.status == 200 and _solved(content):
                    logger.info("Akamai challenge solved on attempt {}", attempt)
                    return
                logger.info("Challenge not solved yet (attempt {}/{})", attempt, MAX_SOLVE_ATTEMPTS)
                if attempt < MAX_SOLVE_ATTEMPTS:
                    with contextlib.suppress(Exception):
                        await page.reload(wait_until="domcontentloaded", timeout=45000)
                    await asyncio.sleep(2)
        finally:
            with contextlib.suppress(Exception):
                await page.close()
        raise ScraperAuthError("Camoufox context could not solve the Akamai challenge — cookies may be stale")

    async def _set_cookies(self, cookie_str: str) -> None:
        cookies = http.cookies.SimpleCookie(cookie_str)
        for key, morsel in cookies.items():
            await self._context.add_cookies(
                [
                    {"name": key, "value": morsel.value, "domain": ".zara.com", "path": "/"},
                ]
            )

    async def fetch_html(self, url: str, cookie_str: str = "", timeout: int = 15) -> str:
        """Fetch product HTML through the solving context, retrying on interstitial pages.

        Returns an empty string for dead products: Zara serves removed items
        either as HTTP 410 or as a 200 "Search engine" 404 shell whose
        viewPayload carries no product data. Live pages are returned only when
        they contain a real product payload (viewPayload.product or JSON-LD).
        Still-challenged pages (bm-verify) are returned as-is so the scraper
        can treat them as a session issue. The cookie_str is used to seed the
        context on first use when ``start()`` was called without cookies — the
        anti-bot cookies belong to the solving context itself.

        Navigation uses ``wait_until="commit"`` plus short content polling so
        fetches are fast — waiting for full ``domcontentloaded`` on Zara can
        take 60s+ per page.
        """
        async with self._semaphore:
            if cookie_str and not await self._context.cookies():
                await self._set_cookies(cookie_str)
            page = await self._context.new_page()
            try:
                for attempt in range(1, MAX_RELOADS + 1):
                    try:
                        response = await page.goto(url, wait_until="commit", timeout=timeout * 1000)
                    except Exception as exc:
                        logger.warning("Camoufox goto failed ({}): {}", url, exc)
                        await asyncio.sleep(1)
                        continue
                    content = ""
                    if response is not None and response.status == 410:
                        return ""
                    if response is not None and _is_search_redirect(response.url):
                        return ""
                    for _ in range(8):
                        await asyncio.sleep(0.25)
                        if _is_search_redirect(page.url):
                            return ""
                        content = cast(str, await page.content())
                        if "bm-verify" not in content and extract_product_data(content) is not None:
                            return content
                        if "bm-verify" in content:
                            break
                    if "bm-verify" not in content:
                        logger.info("Interstitial/challenge for {} (attempt {})", url, attempt)
                        if attempt < MAX_RELOADS:
                            with contextlib.suppress(Exception):
                                await page.reload(wait_until="commit", timeout=timeout * 1000)
                        await asyncio.sleep(0.5)
                content = cast(str, await page.content())
                if "bm-verify" not in content and extract_product_data(content) is None:
                    return ""
                return content
            finally:
                with contextlib.suppress(Exception):
                    await page.close()

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.__aexit__(None, None, None)
            self._browser = None
        logger.info("CamoufoxFetcher closed")

    async def restart(self, cookie_str: str = "") -> None:
        """Tear down and relaunch the browser context to release accumulated
        renderer memory on long runs (Firefox heap grows monotonically)."""
        logger.info("CamoufoxFetcher restarting to release memory")
        await self.close()
        await self.start(cookie_str)
