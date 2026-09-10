import asyncio
import contextlib
import http.cookies
import os
from collections.abc import AsyncGenerator
from typing import Any, cast

from loguru import logger


class BrowserPool:
    """Reusable Playwright browser pool with bounded concurrency.

    Launches Firefox once and reuses it across all page fetches,
    with an asyncio.Semaphore limiting the number of simultaneous
    page loads (default 5).
    """

    def __init__(self, max_concurrent: int = 5) -> None:
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._product_semaphore = asyncio.Semaphore(1)
        self._headless = os.environ.get("OPTS_HEADLESS", "0") == "1"
        self._playwright: Any = None
        self._browser: Any = None

    @contextlib.asynccontextmanager
    async def serialized(self) -> AsyncGenerator[None, None]:
        """Serialize the whole product scrape (not just single fetches).

        Mirrors CamoufoxFetcher.serialized — the scraper wraps one product in
        this lock so only one product is in flight at a time.
        """
        async with self._product_semaphore:
            yield

    async def start(self, cookie_str: str = "") -> None:
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.firefox.launch(headless=self._headless)
        self._context = await self._browser.new_context(
            user_agent="Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0",
        )
        if cookie_str:
            await self._set_cookies(cookie_str)
        logger.info("BrowserPool started (headless={}, max_concurrent={}, cookies={})", self._headless, self.max_concurrent, bool(cookie_str))

    async def _set_cookies(self, cookie_str: str) -> None:
        cookies = http.cookies.SimpleCookie(cookie_str)
        for key, morsel in cookies.items():
            await self._context.add_cookies(
                [
                    {"name": key, "value": morsel.value, "domain": ".zara.com", "path": "/"},
                ]
            )

    async def fetch_html(self, url: str, cookie_str: str, timeout: int = 60) -> str:
        """Fetch HTML by loading in a new tab within the shared context.

        Bounded by the semaphore — at most ``max_concurrent`` calls execute
        simultaneously; the rest wait.
        """
        async with self._semaphore:
            if not await self._context.cookies():
                await self._set_cookies(cookie_str)
            page = await self._context.new_page()
            try:
                await page.goto(url, wait_until="load", timeout=timeout * 1000)
                return cast(str, await page.content())
            finally:
                await page.close()

    async def close(self) -> None:
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("BrowserPool closed")

    async def restart(self, cookie_str: str = "") -> None:
        """Tear down and relaunch the browser to release accumulated renderer
        memory on long runs."""
        logger.info("BrowserPool restarting to release memory")
        await self.close()
        await self.start(cookie_str)
