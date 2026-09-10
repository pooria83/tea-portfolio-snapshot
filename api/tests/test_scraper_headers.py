from __future__ import annotations

import uuid

from httpx import AsyncClient

from app.models.scraper_header import ScraperHeader
from app.scrapers.zara.header_parser import extract_cookie_string, parse_raw_headers, validate_header_block
from app.scrapers.zara.scraper import ZaraScraper
from tests.test_admin_search_eval import _db_admin_headers

RAW_BLOCK = """GET /kw/en/zw-collection-pleated-halter-top-p02678002.html?v1=562452056 HTTP/2
Host: www.zara.com
User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:153.0) Gecko/20100101 Firefox/153.0
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
Cookie: user_type=registered; user_id=2004178410407; access_token=eyJhbGciOiJIUzI1NiJ9.payload.signature; _abck=ABCDEF123456; bm_sz=XYZ
Sec-Fetch-Dest: document
Sec-Fetch-Mode: navigate
Sec-Fetch-Site: same-origin
Sec-Fetch-User: ?1
Priority: u=0, i
TE: trailers
"""


def _uid() -> str:
    return str(uuid.uuid4())


def _make_scraper(db) -> ZaraScraper:
    scraper = ZaraScraper(db)
    return scraper


class TestHeaderParser:
    def test_parse_raw_headers_skips_request_line_and_hop_by_hop(self):
        parsed = parse_raw_headers(RAW_BLOCK)
        assert "User-Agent" in parsed
        assert parsed["User-Agent"].startswith("Mozilla/5.0")
        assert "Sec-Fetch-Mode" in parsed
        assert "Host" not in parsed
        assert "TE" not in parsed
        assert "Connection" not in parsed

    def test_extract_cookie_string(self):
        parsed = parse_raw_headers(RAW_BLOCK)
        cookie = extract_cookie_string(parsed)
        assert cookie is not None
        assert "access_token=eyJhbGci" in cookie
        assert "user_type=registered" in cookie

    def test_validate_header_block_ok(self):
        info = validate_header_block(RAW_BLOCK)
        assert info["cookie_count"] >= 4
        assert info["has_access_token"] is True

    def test_validate_header_block_missing_cookie_raises(self):
        try:
            validate_header_block("User-Agent: Mozilla\nAccept: */*")
            raise AssertionError("expected ValueError")
        except ValueError:
            pass

    def test_validate_header_block_empty_raises(self):
        try:
            validate_header_block("   \n  ")
            raise AssertionError("expected ValueError")
        except ValueError:
            pass


class TestScraperHeaderParsing:
    def test_parse_header_value_raw_block(self):
        scraper = _make_scraper(db=None)
        cookie, headers = scraper._parse_header_value(RAW_BLOCK)
        assert "access_token=" in cookie
        assert headers["User-Agent"].startswith("Mozilla/5.0")

    def test_parse_header_value_plain_cookie_string(self):
        scraper = _make_scraper(db=None)
        cookie, headers = scraper._parse_header_value("a=1; b=2; access_token=xyz")
        assert cookie == "a=1; b=2; access_token=xyz"
        assert headers == {}

    def test_parse_header_value_empty(self):
        scraper = _make_scraper(db=None)
        cookie, headers = scraper._parse_header_value("")
        assert cookie == ""
        assert headers == {}


class TestScraperHeaderEndpoints:
    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/admin/scraper-headers")
        assert resp.status_code == 401

    async def test_forbidden(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/admin/scraper-headers", headers=auth_headers)
        assert resp.status_code == 403

    async def test_list_contains_seeded_zara(self, client: AsyncClient, db_session):
        headers = await _db_admin_headers(db_session)
        name = f"zara-list-{_uid()}"
        db_session.add(ScraperHeader(name=name, header=None, status="ready"))
        await db_session.flush()
        resp = await client.get("/api/v1/admin/scraper-headers", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert any(item["name"] == name and item["header"] is None for item in data)

    async def test_upsert_sets_header_and_resets_error(self, client: AsyncClient, db_session):
        headers = await _db_admin_headers(db_session)
        name = f"zara-up-{_uid()}"
        db_session.add(ScraperHeader(name=name, header=None, status="error", error_message="old failure"))
        await db_session.flush()
        resp = await client.put(
            f"/api/v1/admin/scraper-headers/{name}",
            json={"header": RAW_BLOCK},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["header"] == RAW_BLOCK
        assert data["status"] == "ready"
        assert data["error_message"] is None

    async def test_upsert_invalid_header_returns_422(self, client: AsyncClient, db_session):
        headers = await _db_admin_headers(db_session)
        resp = await client.put(
            f"/api/v1/admin/scraper-headers/zara-invalid-{_uid()}",
            json={"header": "User-Agent: Mozilla\nAccept: */*"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "scraper_header_invalid"

    async def test_get_missing_returns_404(self, client: AsyncClient, db_session):
        headers = await _db_admin_headers(db_session)
        resp = await client.get("/api/v1/admin/scraper-headers/unknown", headers=headers)
        assert resp.status_code == 404
        assert resp.json()["error"]["translation_key"] == "scraper_header_not_found"

    async def test_delete_clears_header(self, client: AsyncClient, db_session):
        headers = await _db_admin_headers(db_session)
        name = f"zara-del-{_uid()}"
        db_session.add(ScraperHeader(name=name, header=RAW_BLOCK, status="error", error_message="boom"))
        await db_session.flush()
        resp = await client.delete(f"/api/v1/admin/scraper-headers/{name}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["header"] is None
        assert data["status"] == "ready"


class TestNullHeaderExit:
    async def test_run_exits_with_error_when_header_missing(self):
        scraper = _make_scraper(db=None)
        try:
            await scraper.run()
            raise AssertionError("expected ScraperAuthError")
        except Exception as exc:
            assert exc.__class__.__name__ == "ScraperAuthError"
            assert "No header configured for scraper 'zara'" in str(exc)

    async def test_run_exits_with_error_when_db_header_null(self):
        class FakeRow:
            header = None

        class FakeResult:
            def scalars(self):
                return self

            def first(self):
                return FakeRow()

        class FakeDb:
            async def execute(self, *args, **kwargs):
                return FakeResult()

        scraper = _make_scraper(db=FakeDb())
        try:
            await scraper.run()
            raise AssertionError("expected ScraperAuthError")
        except Exception as exc:
            assert exc.__class__.__name__ == "ScraperAuthError"
            assert "No header configured for scraper 'zara'" in str(exc)
