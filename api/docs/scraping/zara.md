# Zara Kuwait Scraper

## Overview

Scrapes Zara fashion products from the Kuwait store (`tea-zara`) with bilingual data (EN/AR), internal API enrichment, and per-color image fetching.

**Scraper name:** `zara`
**Country:** Kuwait (`kw`) only
**Currency:** KWD
**Store KV ID:** `11750`

The pipeline is **database-driven**: a sitemap fetch seeds pending rows into `scrape_products`, the scraper claims and fills them, an image cache step downloads media, and a transform step pushes finished products to the API. Category assignment happens at scrape time from each product's `analyticsData` (not from the URL it was discovered under).

## Pipeline

| Phase | Script | Reads | Writes |
|-------|--------|-------|--------|
| 1 — sitemap fetch | `scripts/scrapers/fetch_sitemap.py` | Zara AE product sitemap | `scrape_products` rows with `raw_data={}` |
| 1b — category crawl (optional, deprecated) | `scripts/scrapers/crawl.py` | Category listing pages | Same as phase 1 |
| 2 — scrape | `scripts/scrapers/run.py zara` | Pending `scrape_products` | Fills `raw_data` per row |
| 2b — image cache | `scripts/scrapers/download_images.py` | Scraped rows, not cached | Downloads images to disk cache, sets `images_cached` |
| 3 — sync | `scripts/scrapers/transform.py` | Cached rows without `api_product_id` | Creates store products via the API |

Full payload/mapping rules are documented in [SCRAPER_MAPPING.md](../../SCRAPER_MAPPING.md).

### Phase 1: Sitemap Fetch — `fetch_sitemap.py`

Downloads Zara's gzipped AE product sitemap (~11K URLs), rewrites `/ae/en/` → `/kw/en/`, and inserts new URLs with `raw_data={}`. Deduplication uses `(source, source_id, country)` plus a URL check so already-scraped rows (whose `source_id` migrated to the canonical JSON-LD id) are never re-inserted.

```bash
# Full fetch (downloads via Playwright Firefox)
uv run scripts/scrapers/fetch_sitemap.py --cookie-file ./cookies.txt

# Local sitemap file instead of downloading
uv run scripts/scrapers/fetch_sitemap.py --sitemap-file ./sitemap-product-ae-en.xml --mark-stale-dead

# Preview without inserting
uv run scripts/scrapers/fetch_sitemap.py --limit 5 --dry-run
```

| Flag | Purpose |
|------|---------|
| `--sitemap-url` | Gzipped sitemap URL (default: `sitemap-product-ae-en.xml.gz`) |
| `--sitemap-file` | Read a local sitemap XML file instead of downloading |
| `--cookie-file` / `--scraper` | Cookie for the download; falls back to the scraper header stored in the DB for the given scraper name |
| `--limit` | Max URLs to insert (0 = all) |
| `--dry-run` | Parse and print URLs without inserting |
| `--mark-stale-dead` | After inserting: mark non-scraped rows absent from the sitemap as `dead_product`, and reset `__processing__` rows that ARE in the sitemap so they get re-claimed |

### Phase 1b (Optional): Category Crawl — `crawl.py`

**Deprecated** — kept for reference; `fetch_sitemap.py` replaced it. Crawls category listing pages (from `--sitemap scripts/seed_data/zara_kw_categories.txt` or a single `--url`) and extracts product URLs from the listing HTML.

### Phase 2: Scrape — `run.py`

DB-driven: claims pending products (`raw_data = {}`, no error) from `scrape_products` and scrapes each one.

```bash
# Scrape everything pending (header comes from the admin panel DB store)
uv run scripts/scrapers/run.py zara

# With a cookie/header file, capped at 10 products
uv run scripts/scrapers/run.py zara --cookie-file ./cookies.txt --limit 10

# Specific URLs (+ optional category hint)
uv run scripts/scrapers/run.py zara --urls "https://www.zara.com/kw/en/..." --category man/jackets

# Direct header string
uv run scripts/scrapers/run.py zara --cookie "$(cat cookies.txt)"

# Four parallel worker processes, each with its own browser context
uv run scripts/scrapers/run.py zara --workers 4
```

| Flag | Default | Purpose |
|------|---------|---------|
| `--urls` / `--file` | — | Scrape specific URLs instead of reading the DB |
| `--category` | — | Category path for explicit URLs (e.g. `man/jackets`) |
| `--limit` | `0` | Max pending products to process (0 = all) |
| `--cookie` / `--cookie-file` | — | Legacy explicit credential (see [Credentials](#credentials--anti-bot)) |
| `--concurrency`, `-j` | `5` | Max concurrent product scrapes |
| `--workers` | `1` | Spawn N child scraper processes; the parent counts pending rows and hands each child `--limit=ceil(total/N)` (cannot be combined with `--urls`/`--file`; signals are forwarded, first non-zero exit code wins) |
| `--batch-size` | `50` | Products claimed and processed per DB batch (bounds memory) |
| `--browser-restart-every` | `50` | Restart the browser every N products to release renderer memory (0 = never) |

The claim loop uses `claim_pending()` (`SELECT ... FOR UPDATE SKIP LOCKED` + `scrape_error='__processing__'` marker), so multiple instances never claim the same row. Each claimed row's URL p-code is later migrated to the canonical JSON-LD product id by `complete_claimed()`, keeping one row per product. Products are committed individually, so partial results survive interruptions.

### Phase 2b: Image Cache — `download_images.py`

Downloads product images to the local disk cache (`settings.tea_image_cache_dir`, default `/tmp/tea-assist-img-cache`). Processes rows with `images_cached = false`.

```bash
uv run scripts/scrapers/download_images.py --source zara --limit 100 --concurrency 20
```

### Phase 3: Transform & Sync — `transform.py`

Reads scraped rows that have cached images, no `api_product_id`, and no error; builds API payloads (via `api_client.py` + `mapper.py`), uploads images to MinIO, resolves categories/attributes, and creates store products.

```bash
# Sync everything ready
uv run scripts/scrapers/transform.py --api-key tea_xxxxxxxxxxxx

# Dry run: count only
uv run scripts/scrapers/transform.py --dry-run

# Sync a specific product
uv run scripts/scrapers/transform.py --source-id 00706757 --api-key tea_xxxxxxxxxxxx
```

Auth accepts `--api-key` (sent as `X-API-Key`) or `--api-token` (Bearer JWT). Defaults come from the `ZARA_SCRAPER_*` settings (`.env`). Backfill utilities: `backfill_variant_images.py`, `backfill_variant_sizes.py`.

## Credentials & Anti-Bot

Akamai protects both the product HTML pages and issues short-lived anti-bot cookies (`_abck`, `bm_sz`, `ak_bmsc`, `TS*`). Two mechanisms coexist:

1. **DB-backed scraper headers (preferred)** — the raw HTTP request header block is stored verbatim in the `scraper_headers` table (migration `a1b2c3d4e5f6`: `name` unique, `header` TEXT, `status` `ready|error`, `error_message`/`error_at`) and managed via admin CRUD endpoints:

   | Method | Path | Description |
   |--------|------|-------------|
   | GET | `/admin/scraper-headers` | List configured scrapers |
   | GET | `/admin/scraper-headers/{name}` | Get one (returns the stored block verbatim) |
   | PUT | `/admin/scraper-headers/{name}` | Upsert raw header block (validated — must contain a `Cookie:` header; invalid → 422 `E.SCRAPER_HEADER_INVALID`) |
   | DELETE | `/admin/scraper-headers/{name}` | Clear the header |

   The block is parsed by `app/scrapers/zara/header_parser.py` into a cookie string plus browser headers (User-Agent, Referer, Sec-Fetch-*) replayed on curl_cffi requests.

2. **Legacy flags** — `--cookie "<string>"` or `--cookie-file <path>` still work and take priority over the DB row. A plain cookie string or a full header block are both accepted.

Resolution order (`BaseScraper._resolve_header`): explicit flag → DB row → fail hard with `ScraperAuthError` telling you to set the header in Admin → Settings → Scrapers. The Bearer JWT for `itxrest/` endpoints is extracted automatically from the `access_token` cookie.

**Camoufox fetching** (`camoufox_fetcher.py`): Akamai binds anti-bot tokens to the *browser session that solved the challenge*, so product HTML must be fetched through the same headless Camoufox (hardened Firefox) context that solved it. The context solves the `bm-verify` challenge once at startup (up to 6 attempts) and every product scrape is wrapped in a `serialized()` lock (one product fully in flight at a time). curl_cffi chrome120 sessions are still used for the AJAX endpoints (extra-detail, availability, size-guide, meta.json), which don't challenge. The legacy Playwright `BrowserPool` remains available as an alternative pool but cannot solve challenges itself.

**Auto re-minting** (`cookie_mint.py`): when a page comes back challenged (`bm-verify` interstitial → `ScraperAuthError`), the scraper doesn't give up immediately — it re-mints cookies headlessly (`mint_cookies()` keeps reloading until the challenge is solved and the anti-bot cookie set is complete) and merges them over the current string (`merge_cookies()` — minted anti-bot tokens win, base-only cookies like `access_token` are preserved), then retries. Up to 2 rounds (`max_mint=2`); if the session is still invalid afterwards, a DB-sourced header is marked `error` and the run aborts with exit code 1.

## Dead Products & Crash Recovery

`CamoufoxFetcher.fetch_html()` returns an empty string (→ `dead_product`) when:

- Zara responds **HTTP 410** (gone), or
- the URL **redirects to a search results page** (`/kw/en/search?...` — detected on the exact `search` path segment so slug URLs containing "search" aren't misread), or
- the page renders but carries **no product payload** (`viewPayload.product` / JSON-LD never appears after retries)

These rows get `scrape_error = 'dead_product'`, which permanently excludes them from future claims (pending filters require `scrape_error IS NULL`). Distinguishable from transient errors like `no_json_ld_en` or `session_expired`.

A challenged page (`bm-verify`) is a *session* problem, not a dead product — it raises `ScraperAuthError` and triggers the re-mint loop above.

Crash recovery: rows claimed by a worker that died keep the `__processing__` marker. Every run starts with `release_stale_processing()`, which resets markers older than 30 minutes so they become claimable again; live workers only ever release their own claimed ids.

## Category Mapping

At scrape time the category comes from the page's `analyticsData` via `mapper.resolve_category_from_analytics(section, family, subfamily, product_name)`:

1. **`FAMILY_MAP`** (gender-aware dict keyed by analytics section → family code → category sub-path) resolves known families.
2. **Keyword fallback**: unknown family → keyword rules matched against the product name.
3. **HOME exclusion + rescue** (commit `373a309`): `section == "HOME"` is genuine Zara Home (non-fashion) and returns empty → the row is skipped as `zara_home_excluded` — except families in `HOME_FAMILY_RESCUE` / `_resolve_home_category()` (beach-capsule and bébé items misfiled under HOME: swimwear, flat sandals, bags, CAMISETA tops, BAÑADOR kids swimwear, VESTIDO dresses, …) which are rescued into real fashion categories.
4. Unresolved non-home products error out as `category_unresolved` instead of being guessed.

The mapper's stateless helpers (`CATEGORY_MAP`, `KEYWORD_OVERRIDE_RULES`, `normalize_color`, …) also drive Phase 3 payload building — see [SCRAPER_MAPPING.md](../../SCRAPER_MAPPING.md).

## Internal API Endpoints

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `product/id/{id}/extra-detail?ajax=true` | Cookies | Materials, care instructions, country of origin |
| `itxrest/1/catalog/store/11750/product/id/{id}/availability` | Bearer JWT | Per-SKU stock availability |
| `itxrest/4/catalog/store/11750/product/{id}/size-measure-guide?locale=en_GB` | Bearer JWT | Size measurements (chest, length, sleeve, etc.) |
| `static.zara.net/assets/public/{uuid4}/meta.json` | None | Per-image localized alt text and size variants — lives **two levels up** from the image file, inside the UUID directory |

## Enrichment ID (v1)

Most enrichment endpoints (`extra-detail`, `availability`, `size-guide`) require the **detail ID** (`v1`), not the `productGroupID`. The `v1` ID is extracted from the first variant's SKU in the JSON-LD:

```
SKU format: {v1}-{color_code}-{size_code}
Example:    545490315-711-1  →  v1 = 545490315
```

This is preferred over the `productGroupID` (e.g. `03500002`) which the `extra-detail` endpoint rejects with 404.

## Bilingual Scraping

For each product, two pages are fetched through the Camoufox context:
- `/kw/en/...` — English name, description, JSON-LD
- `/kw/ar/...` — Arabic name, description, JSON-LD (URL derived by swapping `/kw/en/` → `/kw/ar/`)

Extra-detail is also fetched in both languages.

## Per-Color Images

For multi-color products (`variesBy: ["color", "size"]`):
- Each color has its own `v1` parameter, mapped from the variant offers' URLs (`?v1=568668299-250-1`)
- The scraper loads each color's page variant and collects its images separately (`images_per_color`)
- All images carry their `meta.json` metadata when reachable

## Output: `raw_data` JSONB Structure

```json
{
  "en": {
    "json_ld": { "...": "..." },
    "name": "Product Name",
    "description": "Product description",
    "extra_detail": { "materials": ["..."], "care_instructions": "...", "country_of_origin": "..." }
  },
  "ar": {
    "json_ld": { "...": "..." },
    "name": "اسم المنتج",
    "description": "وصف المنتج",
    "extra_detail": { "...": "..." }
  },
  "product_id": "568668299",
  "detail_id": "568668299",
  "colors": [{"code": "250", "name": "BLACK"}, {"code": "800", "name": "OFF-WHITE"}],
  "has_multiple_colors": true,
  "images": [{"url": "...", "meta": {"alt_texts": {"en-US": "...", "ar-SA": "..."}}}],
  "images_per_color": {"250": [{"url": "...", "meta": {"...": "..."}}]},
  "color_images": [{"code": "250", "name": "BLACK", "v1_url": "?v1=568668299-250-1"}],
  "availability": {"...": "..."},
  "size_guide": [{"size_id": "1", "chest": 96, "front_length": 72}],
  "variants_count": 12
}
```

## Database Model & Status Machine

`scrape_products` (`app/models/scrape_product.py`):

| Column | Notes |
|--------|-------|
| `id` | UUID PK |
| `source` | `"zara"` |
| `source_id` | Canonical JSON-LD product id (migrated from the URL p-code on completion) |
| `source_url` | EN product page |
| `source_category` | Category path from analytics mapping (e.g. `woman/dresses`) |
| `country` / `currency` | `"kw"` / `"KWD"` |
| `raw_data` | JSONB — structure above (`{}` while pending) |
| `api_product_id` | Set by Phase 3 after successful sync |
| `scrape_error` | Status/error field (see below) |
| `images_cached` | Set by Phase 2b |
| `scraped_at` | Timestamp |

Unique constraint: `(source, source_id, country)`.

Status machine via `scrape_error`:

```
pending (raw_data={}, scrape_error=NULL)
  └─ claim_pending() → __processing__ (SKIP LOCKED claim marker)
       ├─ success      → NULL + raw_data filled          (complete_claimed)
       ├─ dead product → 'dead_product'                  (permanent)
       ├─ other error  → '<reason>' (e.g. category_unresolved)
       └─ crash        → stays __processing__ until release_stale_processing() (>30 min)
synced (Phase 3)       → api_product_id set
```

## File Map

| File | Purpose |
|------|---------|
| `app/scrapers/base.py` | Abstract base scraper + header resolution (`_resolve_header`) |
| `app/scrapers/registry.py` | Scraper registration / lookup |
| `app/scrapers/exceptions.py` | Shared exceptions (`ScraperAuthError`, `ScraperHTTPError`, `ScraperParseError`) |
| `app/scrapers/zara/config.py` | URLs, endpoint builders, image meta URL, access-token extraction |
| `app/scrapers/zara/browser.py` | curl_cffi chrome120 session builders (plain / AJAX / auth) |
| `app/scrapers/zara/browser_pool.py` | Legacy Playwright Firefox pool (bounded concurrency, restartable) |
| `app/scrapers/zara/camoufox_fetcher.py` | Headless Camoufox fetcher: challenge solving, serialized fetches, dead-page detection |
| `app/scrapers/zara/cookie_mint.py` | Headless Akamai challenge solving → fresh cookie string |
| `app/scrapers/zara/crawler.py` | Legacy category crawler (used by the deprecated `crawl.py`) |
| `app/scrapers/zara/header_parser.py` | Raw DevTools header-block parser/validation |
| `app/scrapers/zara/parser.py` | JSON-LD extraction, viewPayload parsing, image/meta helpers |
| `app/scrapers/zara/exceptions.py` | Scraper-specific exceptions |
| `app/scrapers/zara/scraper.py` | Main `ZaraScraper` (claim batches, enrich, persist, re-mint loop) |
| `scripts/scrapers/fetch_sitemap.py` | Phase 1: sitemap → keyword URLs (+ stale cleanup) |
| `scripts/scrapers/crawl.py` | Phase 1b (deprecated): category crawl |
| `scripts/scrapers/run.py` | Phase 2 CLI: DB-driven scraping, multi-worker launcher |
| `scripts/scrapers/download_images.py` | Phase 2b: disk image cache |
| `scripts/scrapers/transform.py` | Phase 3 CLI: sync to API |
| `scripts/scrapers/api_client.py` | Payload builder + API communication (X-API-Key / Bearer) |
| `scripts/scrapers/mapper.py` | Stateless mapping: categories, colors, variants, HOME rescue rules |
| `scripts/scrapers/backfill_variant_images.py` | Utility: backfill images per color variant |
| `scripts/scrapers/backfill_variant_sizes.py` | Utility: backfill variant size options |
| `scripts/scrapers/run_batch.sh` | Shell script: batch scrape loop |
| `app/models/scrape_product.py` | ScrapeProduct ORM model |
| `app/repositories/scrape_product.py` | Claim/release/error status machine |
| `app/models/scraper_header.py` | ScraperHeader ORM model (migration `a1b2c3d4e5f6`) |
| `app/repositories/scraper_header.py` | ScraperHeader data access |
| `app/services/scraper_header_service.py` | Header upsert/validation, `mark_ready`/`mark_error` |
| `app/api/v1/admin/scraper_headers.py` | Admin CRUD endpoints (`/admin/scraper-headers`) |
| `app/schemas/scraper_header.py` | Request/response schemas |

## Tests

| Test file | Covers |
|-----------|--------|
| `tests/test_camoufox_fetcher.py` | Challenge solving, dead-page detection, serialization semantics |
| `tests/test_scraper_dead_product.py` | Dead-product marking, canonical-id migration, duplicate handling |
| `tests/test_scrape_release_processing.py` | `__processing__` claim/release/stale-recovery rules |
| `tests/test_scraper_headers.py` | ScraperHeader model/service/API, validation, masking |
| `tests/test_zara_view_payload.py` | `viewPayload` extraction edge cases (malformed payloads, braces in names) |
| `tests/test_mapper.py` | Category/color mapping functions |
| `tests/test_scraper_home_exclusion.py` | HOME exclusion vs beach-capsule/bébé rescue rules |
