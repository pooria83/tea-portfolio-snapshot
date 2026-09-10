import asyncio
import re
import time
from typing import Any

from curl_cffi import requests
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.repositories.scrape_product import ScrapeProductRepository
from app.scrapers.base import BaseScraper
from app.scrapers.registry import register_scraper
from app.scrapers.zara import browser as browser_mod
from app.scrapers.zara import cookie_mint
from app.scrapers.zara.browser_pool import BrowserPool
from app.scrapers.zara.camoufox_fetcher import CamoufoxFetcher
from app.scrapers.zara.config import (
    availability_url,
    extra_detail_url_lang,
    product_detail_url,
    size_guide_url,
)
from app.scrapers.zara.exceptions import ScraperAuthError
from app.scrapers.zara.header_parser import validate_header_block
from app.scrapers.zara.parser import (
    extract_analytics_section,
    extract_product_data,
    extract_product_id,
    extract_product_images,
    get_image_meta_url,
    get_unique_colors,
    parse_image_meta,
)
from app.services import scraper_header_service
from scripts.scrapers.mapper import HOME_SECTION, resolve_category_from_analytics

COUNTRY = "kw"
CURRENCY = "KWD"


@register_scraper("zara")
class ZaraScraper(BaseScraper):
    name = "zara"

    def __init__(self, db: AsyncSession, cookie_file: str = "") -> None:
        super().__init__(db)
        self.repo = ScrapeProductRepository(db)
        self.cookie_file = cookie_file

    @staticmethod
    def _parse_header_value(raw: str) -> tuple[str, dict[str, str]]:
        """Turn a raw header block (or plain cookie string) into (cookie, headers).

        Prefers parsing as a raw HTTP header block (the format pasted into the
        admin panel); falls back to treating the whole value as a cookie string.
        """
        if raw and "\n" in raw or "Cookie:" in raw:
            try:
                info = validate_header_block(raw)
                return info["cookie"], info["headers"]
            except ValueError:
                pass
        return raw, {}

    async def run(self, **kwargs: object) -> dict[str, Any]:
        raw_header, header_source = await self._resolve_header(kwargs)
        self._require_header(raw_header, header_source)
        cookie_str, raw_headers = self._parse_header_value(raw_header)

        concurrency_val = kwargs.get("concurrency", 5)
        concurrency = concurrency_val if isinstance(concurrency_val, int) else 5
        use_browser_val = kwargs.get("browser", False)
        use_browser = use_browser_val if isinstance(use_browser_val, bool) else False
        max_mint_val = kwargs.get("max_mint", 2)
        max_mint = max_mint_val if isinstance(max_mint_val, int) else 2

        engine: Any = None
        try:
            engine = create_async_engine(settings.database_url, echo=False, pool_size=concurrency + 5)
            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

            async def task(
                entry: dict[str, str],
                pool: BrowserPool | CamoufoxFetcher,
                cookie_str: str,
                session_factory: async_sessionmaker[AsyncSession],
                raw_urls_bool: bool,
                ajax_client: requests.Session[Any],
                auth_client: requests.Session[Any],
                auth_failed: asyncio.Event,
            ) -> dict[str, Any] | Exception:
                if auth_failed.is_set():
                    return {"url": entry.get("path", "?"), "status": "error", "reason": "auth_failed"}
                async with session_factory() as sess:
                    repo = ScrapeProductRepository(sess)
                    try:
                        return await self._scrape_single(
                            entry,
                            pool,
                            cookie_str,
                            sess,
                            repo,
                            raw_urls_bool,
                            ajax_client,
                            auth_client,
                        )
                    except ScraperAuthError:
                        auth_failed.set()
                        raise
                    except Exception as exc:
                        logger.exception("Error scraping {}", entry.get("path", "?"))
                        reason = str(exc)[:200]
                        try:
                            sid = entry.get("detail_id", "") or _detail_id_from_url(entry.get("path", "")) or ""
                            await repo.mark_error(self.name, sid, COUNTRY, reason)
                            await sess.commit()
                        except Exception:
                            pass
                        return {"url": entry.get("path", "?"), "status": "error", "reason": reason}

            active_client: requests.Session[Any] | None = None
            active_ajax: requests.Session[Any] | None = None
            active_auth: requests.Session[Any] | None = None
            pool: BrowserPool | CamoufoxFetcher | None = None
            claimed_ids: list[str] = []
            released = await self.repo.release_stale_processing(self.name)
            if released:
                logger.info("Released {} stale __processing__ markers from crashed workers", released)
            for mint_round in range(max_mint):
                try:
                    active_client = browser_mod.build_session(cookie_str, extra_headers=raw_headers)
                    active_ajax = browser_mod.build_ajax_session(cookie_str, extra_headers=raw_headers)
                    active_auth = browser_mod.build_auth_session(cookie_str, extra_headers=raw_headers)

                    browser_mod.validate_session(active_ajax)
                    logger.info("Session validated — cookies are active")
                    if header_source == "db":
                        await scraper_header_service.mark_ready(self.db, self.name)

                    pool = BrowserPool(max_concurrent=concurrency) if use_browser else CamoufoxFetcher(max_concurrent=concurrency)
                    await pool.start(cookie_str)
                    active_pool: BrowserPool | CamoufoxFetcher = pool

                    raw_urls = kwargs.get("urls")
                    raw_urls_bool = bool(raw_urls)
                    auth_failed = asyncio.Event()

                    batch_size_val = kwargs.get("batch_size", 50)
                    batch_size = batch_size_val if isinstance(batch_size_val, int) and batch_size_val > 0 else 50
                    restart_every_val = kwargs.get("browser_restart_every", 0)
                    restart_every = restart_every_val if isinstance(restart_every_val, int) and restart_every_val > 0 else 0

                    scraped = skipped = errors = 0
                    total_found = 0
                    processed_since_restart = 0

                    async def process_batch(
                        entries: list[dict[str, str]],
                        pool_arg: BrowserPool | CamoufoxFetcher,
                        cookie_arg: str,
                        restart_every_arg: int,
                        raw_urls_arg: bool,
                        ajax_arg: requests.Session[Any],
                        auth_arg: requests.Session[Any],
                        auth_failed_arg: asyncio.Event,
                    ) -> None:
                        nonlocal scraped, skipped, errors, total_found, processed_since_restart
                        if not entries:
                            return
                        if restart_every_arg and processed_since_restart >= restart_every_arg:
                            logger.info("Restarting browser after {} products to bound memory", processed_since_restart)
                            await pool_arg.restart(cookie_arg)
                            processed_since_restart = 0
                        total_found += len(entries)
                        tasks = [task(e, pool_arg, cookie_arg, session_factory, raw_urls_arg, ajax_arg, auth_arg, auth_failed_arg) for e in entries]
                        gather_results = await asyncio.gather(*tasks, return_exceptions=True)
                        for r in gather_results:
                            if isinstance(r, ScraperAuthError):
                                raise r
                            if isinstance(r, dict):
                                status = r.get("status", "")
                                if status == "scraped":
                                    scraped += 1
                                elif status == "skipped":
                                    skipped += 1
                                elif status == "error":
                                    errors += 1
                            elif isinstance(r, Exception):
                                errors += 1
                        processed_since_restart += len(entries)

                    if raw_urls:
                        raw_list = raw_urls if isinstance(raw_urls, list) else [str(raw_urls)]
                        url_category = str(kwargs.get("category", ""))
                        entries = [{"path": str(url_str), "detail_id": _detail_id_from_url(str(url_str)) or "", "category": url_category} for url_str in raw_list]
                        await process_batch(entries, active_pool, cookie_str, restart_every, raw_urls_bool, active_ajax, active_auth, auth_failed)
                    else:
                        limit_val = kwargs.get("limit", 0)
                        limit = limit_val if isinstance(limit_val, int) else 0
                        remaining = limit if limit > 0 else 0
                        while True:
                            claim_limit = batch_size if remaining == 0 else min(batch_size, remaining)
                            pending = await self.repo.claim_pending(source="zara", limit=claim_limit)
                            if not pending:
                                break
                            claimed_ids.extend(row.id for row in pending)
                            entries = [
                                {
                                    "path": row.source_url or "",
                                    "detail_id": row.source_id,
                                    "category": row.source_category or "",
                                }
                                for row in pending
                            ]
                            await process_batch(entries, active_pool, cookie_str, restart_every, raw_urls_bool, active_ajax, active_auth, auth_failed)
                            if remaining > 0:
                                remaining -= len(pending)

                    if total_found == 0:
                        logger.warning("No products found to scrape")
                        return {"scraped": 0, "skipped": 0, "errors": 0, "total_found": 0, "details": []}

                    return {"scraped": scraped, "skipped": skipped, "errors": errors, "total_found": total_found, "details": []}
                except ScraperAuthError:
                    if mint_round >= max_mint - 1:
                        if header_source == "db":
                            await scraper_header_service.mark_error(
                                self.db,
                                self.name,
                                f"Session invalid after {max_mint} attempts — header challenged or expired",
                            )
                        raise
                    logger.warning("Session challenged — re-minting cookies via Camoufox (round {})", mint_round + 1)
                    cookie_str = cookie_mint.merge_cookies(cookie_str, await cookie_mint.mint_cookies())
                finally:
                    if pool is not None:
                        await pool.close()
                    for s in (active_client, active_ajax, active_auth):
                        if s is not None:
                            s.close()
                    await self.repo.release_processing(self.name, ids=claimed_ids)
            raise ScraperAuthError("Session challenged — cookie minting exhausted")
        finally:
            if engine is not None:
                await engine.dispose()

    async def _scrape_single(
        self,
        entry: dict[str, str],
        pool: BrowserPool | CamoufoxFetcher,
        cookie_str: str,
        session: AsyncSession,
        repo: ScrapeProductRepository,
        raw_urls: bool,
        ajax_client: requests.Session[Any],
        auth_client: requests.Session[Any],
    ) -> dict[str, Any]:
        async with pool.serialized():
            path = entry["path"]
            logger.info("PROCESSING {} ({})", path, entry.get("detail_id", ""))
            try:
                result = await self._scrape_single_impl(entry, pool, cookie_str, session, repo, raw_urls, ajax_client, auth_client)
                logger.info(
                    "DONE {} -> {} ({})",
                    path,
                    result.get("status", "?"),
                    result.get("reason") or result.get("product_id") or "",
                )
                return result
            except ScraperAuthError:
                logger.warning("FAILED {} -> auth_error", path)
                raise
            except Exception as exc:
                logger.error("FAILED {} -> error ({})", path, str(exc)[:200])
                raise

    async def _scrape_single_impl(
        self,
        entry: dict[str, str],
        pool: BrowserPool | CamoufoxFetcher,
        cookie_str: str,
        session: AsyncSession,
        repo: ScrapeProductRepository,
        raw_urls: bool,
        ajax_client: requests.Session[Any],
        auth_client: requests.Session[Any],
    ) -> dict[str, Any]:
        path = entry["path"]
        detail_id = entry.get("detail_id", "")

        en_url = path if path.startswith("http") else product_detail_url(COUNTRY, "en", path.lstrip("/"))
        en_url = str(en_url)

        async def fetch_page(label: str, url: str) -> str:
            start = time.perf_counter()
            logger.info("FETCH PAGE {}: {}", label, url)
            html = await pool.fetch_html(url, cookie_str)
            elapsed = time.perf_counter() - start
            if html:
                logger.info("PAGE OK {}: {} ({} bytes, {:.2f}s)", label, url, len(html), elapsed)
            else:
                logger.info("PAGE EMPTY {}: {} ({:.2f}s)", label, url, elapsed)
            return html

        en_html = await fetch_page("EN", en_url)

        if not en_html:
            sid = entry.get("detail_id", "") or _detail_id_from_url(en_url) or ""
            await repo.mark_error(self.name, sid, COUNTRY, "dead_product")
            await session.commit()
            return {"url": en_url, "status": "error", "reason": "dead_product"}

        if "bm-verify" in en_html:
            raise ScraperAuthError("Session challenged (bm-verify) while fetching product page")

        en_json_ld = extract_product_data(en_html)
        if en_json_ld is None:
            sid = entry.get("detail_id", "") or _detail_id_from_url(en_url) or ""
            err = "session_expired" if "Inditex HLP" in en_html[:500] or "init-authorize" in en_html else "no_json_ld_en"
            await repo.mark_error(self.name, sid, COUNTRY, err)
            await session.commit()
            return {"url": en_url, "status": "error", "reason": err}

        source_id = extract_product_id(en_json_ld)
        source_id = source_id.lstrip("0") or source_id
        if not source_id:
            sid = entry.get("detail_id", "") or _detail_id_from_url(en_url) or ""
            await repo.mark_error(self.name, sid, COUNTRY, "no_product_id_in_jsonld")
            await session.commit()
            return {"url": en_url, "status": "error", "reason": "no_product_id_in_jsonld"}

        if raw_urls and await repo.exists(self.name, source_id, COUNTRY):
            return {"url": en_url, "status": "skipped", "reason": "already_exists", "product_id": source_id}

        analytics = extract_analytics_section(en_html)
        en_name = en_json_ld.get("name", "")
        source_category = resolve_category_from_analytics(
            analytics.get("section", ""),
            analytics.get("family", ""),
            analytics.get("subfamily", ""),
            en_name,
        )
        if not source_category:
            is_home = (analytics.get("section") or "").strip().upper() == HOME_SECTION
            if is_home:
                logger.info(
                    "ZARA HOME EXCLUDED: product_id={} name='{}' section={} family={} subfamily={} url={}",
                    source_id,
                    en_name,
                    analytics.get("section"),
                    analytics.get("family"),
                    analytics.get("subfamily"),
                    en_url,
                )
                await repo.mark_error(self.name, source_id, COUNTRY, "zara_home_excluded")
                await session.commit()
                return {"url": en_url, "status": "skipped", "reason": "zara_home_excluded"}
            logger.error(
                "CATEGORY UNRESOLVED: product_id={} name='{}' section={} family={} subfamily={} url={}",
                source_id,
                en_name,
                analytics.get("section"),
                analytics.get("family"),
                analytics.get("subfamily"),
                en_url,
            )
            await repo.mark_error(self.name, source_id, COUNTRY, "category_unresolved")
            await session.commit()
            return {"url": en_url, "status": "error", "reason": "category_unresolved"}

        ar_url = en_url.replace(f"/{COUNTRY}/en/", f"/{COUNTRY}/ar/")
        ar_html = await fetch_page("AR", ar_url) if "bm-verify" not in en_html else ""
        ar_json_ld = extract_product_data(ar_html) if ar_html else None

        en_description = en_json_ld.get("description", "")
        ar_name = ""
        ar_description = ""
        if ar_json_ld:
            ar_name = ar_json_ld.get("name", "")
            ar_description = ar_json_ld.get("description", "")

        v1_id = _extract_v1_from_variants(en_json_ld)

        colors = get_unique_colors(en_json_ld)
        images = extract_product_images(en_json_ld)
        has_multiple_colors = len(colors) > 1

        enrichment_id = v1_id or detail_id or source_id
        extra_detail_en = self._fetch_json_graceful(ajax_client, extra_detail_url_lang(enrichment_id, "en"))
        extra_detail_ar = self._fetch_json_graceful(ajax_client, extra_detail_url_lang(enrichment_id, "ar"))
        availability_data = self._fetch_json_graceful(auth_client, availability_url(v1_id or source_id or detail_id))
        size_guide_data = self._fetch_json_graceful(auth_client, size_guide_url(v1_id or source_id or detail_id))

        enriched_images = _gather_image_data(ajax_client, images)
        color_images = _build_color_images(product_id=v1_id or detail_id or source_id, colors=colors, json_ld=en_json_ld)

        images_per_color: dict[str, list[dict[str, Any]]] = {}
        if has_multiple_colors and color_images:
            for ci in color_images:
                code = ci.get("code", "")
                v1_url_param = ci.get("v1_url", "")
                if not code or not v1_url_param:
                    continue
                color_url = en_url + v1_url_param
                try:
                    color_html = await fetch_page(f"COLOR {code}", color_url)
                    if "bm-verify" in color_html:
                        logger.warning("Color page {} returned interstitial", color_url)
                        continue
                    color_json_ld = extract_product_data(color_html)
                    if not color_json_ld:
                        continue
                    color_image_urls = extract_product_images(color_json_ld)
                    if color_image_urls:
                        enriched = _gather_image_data(ajax_client, color_image_urls)
                        images_per_color[code] = enriched
                except Exception as exc:
                    logger.warning("Error fetching per-color images for code={}: {}", code, exc)

        raw_data: dict[str, Any] = {
            "en": {
                "json_ld": en_json_ld,
                "name": en_name,
                "description": en_description,
                "extra_detail": extra_detail_en,
            },
            "ar": {
                "json_ld": ar_json_ld,
                "name": ar_name,
                "description": ar_description,
                "extra_detail": extra_detail_ar,
            },
            "product_id": source_id,
            "detail_id": detail_id,
            "colors": [{"code": c["code"], "name": c["name"]} for c in colors],
            "has_multiple_colors": has_multiple_colors,
            "images": enriched_images,
            "images_per_color": images_per_color,
            "color_images": color_images,
            "availability": availability_data,
            "size_guide": size_guide_data,
            "variants_count": len(en_json_ld.get("hasVariant", [])),
        }

        result = {
            "source": self.name,
            "source_id": source_id,
            "source_url": en_url,
            "source_category": source_category,
            "country": COUNTRY,
            "currency": CURRENCY,
            "raw_data": raw_data,
        }

        await repo.complete_claimed(result, detail_id, path)
        await session.commit()
        logger.info("Scraped: {} (ID={}, category={})", path, source_id, source_category)
        return {"url": en_url, "status": "scraped", "product_id": source_id}

    def _fetch_json_graceful(self, client: requests.Session[Any], url: str) -> Any:
        start = time.perf_counter()
        resp = client.get(url)
        elapsed = time.perf_counter() - start
        if resp.status_code in (401, 403):
            logger.warning("AJAX FAIL {} (HTTP {}, {:.2f}s) — auth", url, resp.status_code, elapsed)
            raise ScraperAuthError(f"Auth failed at {url} — HTTP {resp.status_code}")
        if resp.status_code != 200:
            logger.warning("AJAX ERR {} (HTTP {}, {:.2f}s)", url, resp.status_code, elapsed)
            return None
        try:
            data = resp.json()
            logger.info("AJAX OK {} (HTTP 200, {:.2f}s)", url, elapsed)
            return data
        except Exception as exc:
            logger.warning("AJAX BAD JSON {} ({:.2f}s): {}", url, elapsed, exc)
            return None


def _extract_product_urls_from_category_html(html: str, base_url: str) -> list[dict[str, str]]:
    seen: set[str] = set()
    results: list[dict[str, str]] = []

    for m in re.finditer(r'"url"\s*:\s*"(https?://www\.zara\.com/kw/en/[^"]*-p(\d+)\.html[^"]*?)"', html):
        url = m.group(1)
        pid = m.group(2).lstrip("0") or m.group(2)
        if pid not in seen:
            seen.add(pid)
            results.append({"url": url, "product_id": pid})

    for m in re.finditer(r'data-productkey="[^"]+-(\d+)-[^"]+"', html):
        mid = m.group(1).split("_")[0]
        raw_id = mid[:8]
        pid = raw_id.lstrip("0") or raw_id
        if pid not in seen:
            seen.add(pid)
            url = f"https://www.zara.com/kw/en/p{raw_id}.html"
            results.append({"url": url, "product_id": pid})

    return results


def _extract_v1_from_variants(json_ld: dict[str, Any]) -> str:
    variants = json_ld.get("hasVariant", [])
    if variants and isinstance(variants, list) and len(variants) > 0:
        first = variants[0]
        if isinstance(first, dict):
            sku = str(first.get("sku", first.get("mpn", "")))
            if "-" in sku:
                return sku.split("-", 1)[0]
    return ""


def _detail_id_from_url(url: str) -> str | None:
    m = re.search(r"p(\d{5,})(?:\.|\?|$)", url)
    if m:
        return m.group(1).lstrip("0") or m.group(1)
    m = re.search(r"v1=(\d+)", url)
    if m:
        return m.group(1).lstrip("0") or m.group(1)
    return None


def _build_color_images(
    product_id: str,
    colors: list[dict[str, str]],
    json_ld: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    color_v1_map: dict[str, str] = {}
    if json_ld:
        variants = json_ld.get("hasVariant", [])
        if isinstance(variants, dict):
            variants = [variants]
        for v in variants:
            if not isinstance(v, dict):
                continue
            color_val = v.get("color", "")
            color_name = str(color_val.get("name", color_val)) if isinstance(color_val, dict) else str(color_val)
            offers = v.get("offers", {})
            url = offers.get("url", "") if isinstance(offers, dict) else ""
            m = re.search(r"v1=(\d+)", url)
            if m and color_name and color_name not in color_v1_map:
                color_v1_map[color_name] = m.group(1)

    result: list[dict[str, Any]] = []
    for color in colors:
        code = color.get("code", "")
        name = color.get("name", "")
        per_color_v1 = color_v1_map.get(code) or color_v1_map.get(name) or product_id
        v1_url = f"?v1={per_color_v1}"
        result.append({"code": code, "name": name, "v1_url": v1_url})
    return result


def _gather_image_data(ajax_client: requests.Session[Any], image_urls: list[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    ok = 0
    start = time.perf_counter()
    for img_url in image_urls:
        entry: dict[str, Any] = {"url": img_url}
        meta_url = get_image_meta_url(img_url)
        if meta_url:
            try:
                meta_resp = ajax_client.get(meta_url)
                if meta_resp.status_code == 200:
                    entry["meta"] = parse_image_meta(meta_resp.json())
                    ok += 1
                    logger.debug("META OK {} (HTTP 200)", meta_url)
                else:
                    entry["meta_error"] = f"HTTP {meta_resp.status_code}"
                    logger.debug("META ERR {} (HTTP {})", meta_url, meta_resp.status_code)
            except Exception as exc:
                entry["meta_error"] = str(exc)[:100]
                logger.debug("META FAIL {}: {}", meta_url, str(exc)[:100])
        result.append(entry)
    elapsed = time.perf_counter() - start
    logger.info(
        "IMAGES OK {}/{} with meta ({} urls, {:.2f}s)",
        ok,
        len(image_urls),
        len(image_urls),
        elapsed,
    )
    return result
