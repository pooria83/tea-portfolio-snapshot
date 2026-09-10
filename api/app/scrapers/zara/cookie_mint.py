"""Mint Zara cookies by solving the Akamai bm-verify challenge with Camoufox.

The minted cookie string carries the anti-bot tokens (_abck, bm_sz, ak_bmsc,
TS* etc.) that let the curl_cffi chrome120 sessions reach the AJAX endpoints
(extra-detail, availability, size-guide). The Akamai protection on the product
HTML pages is bound to the solving browser session itself, so the scraper
fetches HTML pages through a persistent Camoufox context instead of curl_cffi.
"""

import asyncio
import contextlib

from loguru import logger

from app.scrapers.zara.exceptions import ScraperAuthError

MINT_URL = "https://www.zara.com/kw/en/zw-collection-pleated-halter-top-p02678002.html?v1=562452056"
MAX_ATTEMPTS = 6


def _solved(content: str) -> bool:
    return "viewPayload" in content and "bm-verify" not in content


def _has_anti_bot_cookies(header: str) -> bool:
    keys = [part.split("=", 1)[0] for part in header.split("; ")]
    return "_abck" in keys and any(k.startswith("TS") for k in keys)


def merge_cookies(base: str, fresh: str) -> str:
    """Merge fresh cookies over a base cookie string.

    Anti-bot tokens from the minted string win, but cookies that only exist in
    the base string (e.g. the user's ``access_token``) are preserved.
    """
    merged: dict[str, str] = {}
    for part in base.split("; "):
        if "=" in part:
            key, value = part.split("=", 1)
            merged[key] = value
    for part in fresh.split("; "):
        if "=" in part:
            key, value = part.split("=", 1)
            merged[key] = value
    return "; ".join(f"{k}={v}" for k, v in merged.items())


async def mint_cookies(url: str = MINT_URL, max_attempts: int = MAX_ATTEMPTS) -> str:
    """Solve the bm-verify challenge headlessly and return the zara.com cookie header.

    Akamai writes the full cookie set (including the TS* edge token) only after a
    few page loads, so we keep reloading until the anti-bot cookies are complete.
    """
    try:
        from camoufox.async_api import AsyncCamoufox
    except ImportError as exc:
        raise ScraperAuthError("camoufox is not installed — install the 'scrapers' extra (uv pip install -e '.[scrapers]')") from exc

    async with AsyncCamoufox(headless=True) as browser:
        context = await browser.new_context(locale="en-US", timezone_id="Europe/Dublin")
        page = await context.new_page()

        async def cookie_header() -> str:
            cookies = await context.cookies()
            zara = [c for c in cookies if "zara.com" in c.get("domain", "")]
            return "; ".join(f"{c['name']}={c['value']}" for c in zara)

        status: int | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            except Exception as exc:
                logger.warning("cookie-mint goto failed (attempt {}): {}", attempt, exc)
                continue
            status = response.status if response else None
            await asyncio.sleep(3)
            content = await page.content()
            header = await cookie_header()
            if status == 200 and _solved(content) and _has_anti_bot_cookies(header):
                logger.info(
                    "Cookie-mint OK after {} attempts: _abck={} bm_sz={} ak_bmsc={}",
                    attempt,
                    "_abck" in header,
                    "bm_sz" in header,
                    "ak_bmsc" in header,
                )
                return header
            logger.info(
                "cookie-mint attempt {}/{}: status={} challenge={} cookies={}",
                attempt,
                max_attempts,
                status,
                "bm-verify" in content,
                len(header.split("; ")) if header else 0,
            )
            if attempt < max_attempts:
                with contextlib.suppress(Exception):
                    await page.reload(wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(2)

        header = await cookie_header()
        if not _has_anti_bot_cookies(header):
            raise ScraperAuthError(f"Cookie minting failed — incomplete anti-bot cookies after {max_attempts} attempts (last status={status})")
        return header
