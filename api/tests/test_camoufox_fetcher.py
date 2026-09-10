from __future__ import annotations

import asyncio

from app.scrapers.zara.camoufox_fetcher import CamoufoxFetcher, _is_search_redirect


class TestIsSearchRedirect:
    def test_dead_product_redirect_url(self):
        assert _is_search_redirect("https://www.zara.com/kw/en/search?searchTerm=plain%20swimsuit%20with%20stones%20marisa%20berenson%20x%20zara&section=WOMAN")

    def test_dead_product_redirect_ar_locale(self):
        assert _is_search_redirect("https://www.zara.com/kw/ar/search?searchTerm=test&section=WOMAN")

    def test_live_product_url_not_redirect(self):
        assert not _is_search_redirect("https://www.zara.com/kw/en/bucket-hat-p1023211.html")

    def test_variant_url_not_redirect(self):
        assert not _is_search_redirect("https://www.zara.com/kw/en/ruffled-split-suede-ankle-boots-p13100610.html?v1=545492163")

    def test_empty_url_not_redirect(self):
        assert not _is_search_redirect("")

    def test_search_word_in_slug_not_redirect(self):
        assert not _is_search_redirect("https://www.zara.com/kw/en/searching-the-sun-p1023211.html")


class TestSerialized:
    async def test_serializes_concurrent_products(self):
        fetcher = CamoufoxFetcher()
        active = 0
        peak = 0

        async def work():
            nonlocal active, peak
            async with fetcher.serialized():
                active += 1
                peak = max(peak, active)
                await asyncio.sleep(0.05)
                active -= 1

        await asyncio.gather(*[work() for _ in range(5)])

        assert peak == 1

    async def test_fetch_semaphore_still_serializes(self):
        fetcher = CamoufoxFetcher()
        active = 0
        peak = 0

        async def work():
            nonlocal active, peak
            async with fetcher._semaphore:
                active += 1
                peak = max(peak, active)
                await asyncio.sleep(0.05)
                active -= 1

        await asyncio.gather(*[work() for _ in range(5)])

        assert peak == 1
