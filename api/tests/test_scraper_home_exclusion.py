"""Tests for ZaraScraper HOME-section exclusion and category-unresolved paths."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from app.scrapers.zara.scraper import ZaraScraper

ENTRY = {"path": "https://www.zara.com/kw/en/metal-flowerpot-p41311748.html"}


def _mock_http_client() -> Any:
    client = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {}
    client.get.return_value = resp
    return client


def _html(section: str, family: str, subfamily: str, name: str) -> str:
    ld = {"@type": "Product", "name": name, "productGroupID": "41311748"}
    analytics = {"section": section, "family": family, "subfamily": subfamily}
    return f'<html><head><script type="application/ld+json">{json.dumps(ld)}</script><script>zara.analyticsData = {json.dumps(analytics)};</script></head></html>'


def _harness(html: str) -> tuple[ZaraScraper, Any, AsyncMock, AsyncMock, Any]:
    scraper = ZaraScraper(None)
    pool = AsyncMock()
    pool.fetch_html = AsyncMock(return_value=html)
    repo = AsyncMock()
    repo.exists = AsyncMock(return_value=False)
    repo.mark_error = AsyncMock()
    session = AsyncMock()
    session.commit = AsyncMock()
    coro = scraper._scrape_single_impl(
        entry=ENTRY,
        pool=pool,
        cookie_str="cookie",
        session=session,
        repo=repo,
        raw_urls=False,
        ajax_client=None,
        auth_client=None,
    )
    return scraper, pool, repo, session, coro


async def test_genuine_home_product_is_excluded_before_ar_fetch() -> None:
    html = _html("HOME", "ACCESORIOS DECORAC", "SOPORTE MACETA", "METAL FLOWERPOT")
    _, pool, repo, session, coro = _harness(html)

    result = await coro

    assert result == {
        "url": ENTRY["path"],
        "status": "skipped",
        "reason": "zara_home_excluded",
    }
    assert pool.fetch_html.await_count == 1
    repo.mark_error.assert_awaited_once_with("zara", "41311748", "kw", "zara_home_excluded")
    session.commit.assert_awaited_once()


async def test_fashion_rescued_from_home_fetches_ar_page() -> None:
    html = _html("HOME", "BOLSOS", "H1:ACC BEACHWEA", "PAPER TOTE BAG")
    scraper2 = ZaraScraper(None)
    pool = AsyncMock()
    pool.fetch_html = AsyncMock(side_effect=[html, ""])
    repo = AsyncMock()
    repo.exists = AsyncMock(return_value=False)
    repo.mark_error = AsyncMock()
    repo.complete_claimed = AsyncMock()
    session = AsyncMock()
    session.commit = AsyncMock()

    result = await scraper2._scrape_single_impl(
        entry=ENTRY,
        pool=pool,
        cookie_str="cookie",
        session=session,
        repo=repo,
        raw_urls=False,
        ajax_client=_mock_http_client(),
        auth_client=_mock_http_client(),
    )

    assert pool.fetch_html.await_count >= 2
    assert result["status"] == "scraped"
    assert result["product_id"] == "41311748"
    repo.mark_error.assert_not_awaited()


async def test_unresolved_non_home_category_still_errors() -> None:
    html = _html("MAN", "UNKNOWN FAMILY CODE", "", "MYSTERY WIDGET DELUXE")
    _, pool, repo, session, coro = _harness(html)

    result = await coro

    assert result["status"] == "error"
    assert result["reason"] == "category_unresolved"
    assert pool.fetch_html.await_count == 1
    repo.mark_error.assert_awaited_once_with("zara", "41311748", "kw", "category_unresolved")
    session.commit.assert_awaited_once()
