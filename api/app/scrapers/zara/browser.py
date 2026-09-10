import http.cookies
from typing import Any

from curl_cffi import requests

from app.scrapers.zara.config import AJAX_HEADERS, HEADERS, extract_access_token
from app.scrapers.zara.exceptions import ScraperAuthError


def _apply_cookies(session: requests.Session[Any], cookie_str: str) -> None:
    cookies = http.cookies.SimpleCookie(cookie_str)
    for key, morsel in cookies.items():
        session.cookies.set(key, morsel.value, domain=".zara.com", path="/")


def _apply_headers(session: requests.Session[Any], extra_headers: dict[str, str] | None = None) -> None:
    """Apply parsed browser headers (User-Agent, Referer, Sec-Fetch-*, ...).

    These come from the raw header block stored in the admin panel and are
    expected by Akamai on curl_cffi requests. The Cookie header is handled
    separately via the session cookie jar.
    """
    if not extra_headers:
        return
    for name, value in extra_headers.items():
        if name.lower() == "cookie":
            continue
        session.headers[name] = value


def build_session(cookie_str: str, timeout: int = 60, extra_headers: dict[str, str] | None = None) -> requests.Session[Any]:
    session: requests.Session[Any] = requests.Session(impersonate="chrome120", timeout=timeout)
    session.headers.update(HEADERS)
    _apply_headers(session, extra_headers)
    _apply_cookies(session, cookie_str)
    return session


def build_ajax_session(cookie_str: str, timeout: int = 60, extra_headers: dict[str, str] | None = None) -> requests.Session[Any]:
    session: requests.Session[Any] = requests.Session(impersonate="chrome120", timeout=timeout)
    session.headers.update(AJAX_HEADERS)
    _apply_headers(session, extra_headers)
    _apply_cookies(session, cookie_str)
    return session


def build_auth_session(cookie_str: str, timeout: int = 60, extra_headers: dict[str, str] | None = None) -> requests.Session[Any]:
    session: requests.Session[Any] = requests.Session(impersonate="chrome120", timeout=timeout)
    session.headers.update(AJAX_HEADERS)
    _apply_headers(session, extra_headers)
    token = extract_access_token(cookie_str)
    if not token and extra_headers:
        auth = extra_headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        raise ScraperAuthError("No access_token found in cookie string or Authorization header")
    session.headers["Authorization"] = f"Bearer {token}"
    _apply_cookies(session, cookie_str)
    return session


def validate_session(session: requests.Session[Any]) -> None:
    resp = session.get("https://www.zara.com/kw/en/product/id/545494298/extra-detail?ajax=true")
    if resp.status_code in (401, 403):
        raise ScraperAuthError(f"Session invalid — received HTTP {resp.status_code}")
    if resp.status_code != 200:
        raise ScraperAuthError(f"Session validation failed — HTTP {resp.status_code}")


def read_cookie_file(cookie_file: str) -> str:
    import pathlib

    return pathlib.Path(cookie_file).read_text().strip()


async def fetch_html_via_browser(url: str, cookie_str: str, timeout: int = 60) -> str:
    """Download HTML by rendering the page in a headless Camoufox browser.

    Kept as a single-shot helper for one-off fetches; the scraper itself uses
    the persistent :class:`CamoufoxFetcher` pool.
    """
    from camoufox.async_api import AsyncCamoufox

    async with AsyncCamoufox(headless=True) as browser:
        context = await browser.new_context(locale="en-US", timezone_id="Europe/Dublin")
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        html: str = await page.content()
        return html
