# Scraper → API Mapping Documentation

## Overview

The Zara scraper collects product data from Zara and pushes it to the Product Graph API. This document describes every transformation rule between scraped data (`scrape_products` table) and the API payload (`StoreProductCreate`).

## Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 1: fetch_sitemap.py                                          │
│  ┌──────────────────┐    ┌──────────────────┐                      │
│  │ Download gzipped  │───▶│ Parse XML,       │───▶ scrape_products  │
│  │ sitemap (11K URLs)│    │ convert to KW     │    (raw_data = {})  │
│  └──────────────────┘    └──────────────────┘                       │
│                                                                     │
│  PHASE 2: run.py                                                    │
│  ┌──────────────────┐    ┌──────────────────┐                      │
│  │ Read pending from │───▶│ ZaraScraper      │───▶ scrape_products  │
│  │ scrape_products   │    │ scrape detail     │    (raw_data filled)│
│  └──────────────────┘    │ + bilingual +     │                      │
│                          │ enrich + images   │                      │
│                          └──────────────────┘                       │
│                                                                     │
│  PHASE 2b: download_images.py                                       │
│  ┌──────────────────┐    ┌──────────────────┐                      │
│  │ Read products     │───▶│ Download images   │───▶ images_cached   │
│  │ (not cached)      │    │ to disk cache     │    = True           │
│  └──────────────────┘    └──────────────────┘                       │
│                                                                     │
│  PHASE 3: transform.py                                              │
│  ┌──────────────────┐    ┌──────────────────┐    ┌────────────────┐ │
│  │ Read products     │───▶│ ScraperAPIClient  │───▶│ POST /api/v1/ │ │
│  │ (api_product_id   │    │ - build payload  │    │ stores/{id}/  │ │
│  │ IS NULL, cached)  │    │ - upload images  │    │ products      │ │
│  └──────────────────┘    │   to MinIO        │    └────────────────┘ │
│                          │ - resolve cats    │         │            │
│                          │ - resolve attrs   │         ▼            │
│                          │ - create variants │    store_products    │
│                          └──────────────────┘    api_product_id set │
└─────────────────────────────────────────────────────────────────────┘
```

### Phase 1: Sitemap Fetch — `fetch_sitemap.py`
Downloads the Zara AE product sitemap (gzipped XML, ~11K URLs), converts URLs to the Kuwait domain, and inserts them into `scrape_products` with `raw_data={}`. Deduplicates via `(source, source_id, country)` unique constraint.

```bash
uv run scripts/scrapers/fetch_sitemap.py --cookie-file ./cookies.txt
```

### Phase 2: Scrape — `run.py`
Reads pending products from `scrape_products` (where `raw_data` is `{}`), scrapes product detail pages via the Zara scraper, and fills in `raw_data`.

```bash
uv run scripts/scrapers/run.py zara --cookie-file ./cookies.txt
```

### Phase 2b: Image Cache — `download_images.py`
Downloads product images to a local disk cache (no MinIO/API). Processes products where `images_cached = False`. Uses semaphore-based concurrency (default 10).

```bash
uv run scripts/scrapers/download_images.py --limit 100 --concurrency 20
```

### Phase 3: Transform — `transform.py`
Syncs completed scrape data (`api_product_id IS NULL`, `images_cached = True`) to the API via `ScraperAPIClient`. Creates `StoreProduct` records.

```bash
uv run scripts/scrapers/transform.py --api-key tea_xxxxxxxxxxxx
```

### Batch Runner — `run_batch.sh`
Shell loop that scrapes in batches of N products, checks pending count via `psql`, and sleeps between batches.

### Backfill Scripts
- `backfill_variant_images.py` — Duplicates images across all variants of the same color.
- `backfill_variant_sizes.py` — Links size attribute options to existing variants missing them.

### Authentication for Transform

The transform script authenticates with the API using either:
- **API key** (`--api-key`): Sent as `X-API-Key` header. Must match `settings.api_key` or a per-user `User.api_key` in the database.
- **JWT token** (`--api-token`): Sent as `Authorization: Bearer` header.

```bash
# API key auth (recommended for service-to-service)
uv run scripts/scrapers/transform.py --api-key tea_xxxxxxxxxxxx

# JWT auth (requires a valid user token)
uv run scripts/scrapers/transform.py --api-token <jwt_string>
```

If a user exists in the database with `api_key` set to the same value as `settings.api_KEY`, the API will authenticate as that user (bypassing the store ownership check). Otherwise, the master key returns `None` (unauthenticated service access — sufficient for search/AI endpoints where user_id is nullable, but not store product creation).

---

## 1. Category Mapping

### Resolution Strategy

Category resolution is a 3-level process, defined in `scripts/scrapers/mapper.py`:

1. **Keyword override** — Check `KEYWORD_OVERRIDE_RULES` for the source category (e.g., `woman/shoes` → keyword "heel" → `Heels & Dress Shoes` / `High Heels` / `heels_dress_shoes`)
2. **Direct lookup** — Check `CATEGORY_MAP` for `(root_en, child_en, pt_code)`
3. **Child keyword resolution** — If child is `None`, check `CHILD_KEYWORD_RULES` for the root (e.g., `Tops & Blouses` + keyword "blouse" → `Blouses`)
4. **Default child** — If no keyword matches, use `DEFAULT_CHILD` for the root

### Zara Category → System Root + Child + Product Type

| Zara Path | Root | Child | Product Type |
|---|---|---|---|
| `woman/dresses` | Dresses | keyword → Evening/Casual/Wedding/Modest | `dresses` |
| `woman/tops` | Tops & Blouses | keyword → Blouses/T-Shirts/Formal Shirts/etc. | `tops` |
| `woman/shirts` | Tops & Blouses | Blouses | `tops` |
| `woman/trousers` | Pants & Bottoms | Pants | `bottoms` |
| `woman/shorts` | Pants & Bottoms | Shorts | `bottoms` |
| `woman/lingerie` | Lingerie & Sleepwear | Lingerie | `lingerie_sleepwear` |
| `woman/jeans` | Pants & Bottoms | Jeans | `bottoms` |
| `woman/jumpsuits` | Dresses | keyword → Casuals | `dresses` |
| `woman/jackets` | Outerwear | Jackets | `outerwear` |
| `woman/loungewear` | Outerwear | keyword → Coats/Jackets/Blazers/Gilets/Puffer | `outerwear` |
| `woman/shoes` | keyword override | keyword → all shoe types | *dynamic* |
| `woman/accessories` | keyword override | keyword → all accessory types | *dynamic* |
| `woman/new_in` | keyword override | keyword → multiple | *dynamic* |
| `man/t-shirts` | Tops & Blouses | T-Shirts | `tops` |
| `man/coats` | Outerwear | Coats | `outerwear` |
| `man/jackets` | Outerwear | Jackets | `outerwear` |
| `man/trousers` | Pants & Bottoms | Pants | `bottoms` |
| `man/shirts` | Tops & Blouses | Formal Shirts | `tops` |
| `man/accessories` | keyword override | keyword → tops/outerwear/accessories | *dynamic* |
| `man/jeans` | Pants & Bottoms | Jeans | `bottoms` |
| `man/shoes` | keyword override | keyword → all shoe types | *dynamic* |
| `man/sweatshirts` | Tops & Blouses | Sweatshirts | `tops` |
| `man/polos` | Tops & Blouses | Polos | `tops` |
| `man/suits` | Suits & Formalwear | keyword → Waistcoats/Blazers | `suits_formalwear` |
| `kids/boy` | keyword override | keyword → multiple | *dynamic* |
| `kids/new_in` | keyword override | keyword → multiple | *dynamic* |

### Keyword Override Mappings

The following additional keyword-to-category mappings are defined in `KEYWORD_OVERRIDE_RULES` (`mapper.py`):

| Category Path | Keyword | Root | Child | Product Type |
|---|---|---|---|---|
| `woman/accessories` | `cap` / `skullcap` | Head Accessories | Caps | `head_accessories` |
| `woman/accessories` | `beanie` | Head Accessories | Beanies | `head_accessories` |
| `woman/accessories` | `headpiece` | Head Accessories | Headpieces | `head_accessories` |
| `woman/accessories` | `edp` / `perfume` | Fragrance & Perfume | Perfumes | `fragrance` |
| `woman/accessories` | `minaudière` / `minaudiere` | Bags & Handbags | Clutches | `bags` |
| `woman/accessories` | `tote` / `bucket` | Bags & Handbags | Handbags | `bags` |
| `woman/accessories` | `crossbody` | Bags & Handbags | Crossbody Bags | `bags` |
| `woman/accessories` | `bg` | Bags & Handbags | Handbags | `bags` |
| `woman/accessories` | `shldr` | Bags & Handbags | Shoulder Bags | `bags` |

### Product Types (30 total)

Product type is now **dynamic** — determined by the resolved category, not hardcoded. Each of the 30 root categories maps to a distinct `product_type_code`, which determines the attribute set for that product.

### Category ID Resolution

`_resolve_category_id` in `api_client.py`:
1. If a child category name is resolved, look it up by `name_en` (must have `parent_id` non-null)
2. Otherwise, look up the root by `name_en`
3. Fallback: first root category matching the `product_type_id`

---

## 2. Color Mapping

### Pipeline
1. **Normalize**: `strip().lower().replace(" ", "-").replace("_", "-")`
2. **Exact match**: Normalized name matched against normalized option codes (both use hyphens, so `navy_blue` → `navy-blue` matches)
3. **Split multi-colors**: Colors like `"Offwhite/Cream"` are split on `/` and each part matched independently
4. **Value match fallback**: If exact match fails, try matching raw name against option `value_en` (case-insensitive contains)
5. **Code fragment fallback**: Try matching option code fragments within the normalized name
6. **Alias map**: `COLOR_ALIASES` handles common Zara spellings (e.g., `grey` → `gray`, `offwhite` → `off-white`)
7. **Color family fallback**: No explicit last resort — unmatched colors are silently skipped

### Color Aliases
| Zara Name | System Code |
|---|---|
| `grey` | `gray` |
| `navy` | `navy-blue` |
| `taupe` | `beige` |
| `offwhite` | `off-white` |
| `multicolour` | `multi` |
| `nude` | `beige` |

---

## 3. Attribute Mapping

### 3.1 Per-Type Attribute Routing

Attributes are routed to type-specific codes via `TYPE_SPECIFIC_ATTR_MAP`. For example:

| Generic Attr | Dresses | Tops | Outerwear |
|---|---|---|---|
| `sleeve` | `sleeve_style` | `top_sleeve_style` | `sleeve_style` |
| `neckline` | `neckline` | `top_neckline` | `neckline` |
| `fit` | `fit_type` | `top_fit_type` | `fit_type` |
| `hem` | `dress_skirt_length` | `top_length` | — |
| `pattern` | `pattern` | `pattern` | `pattern` |

### 3.2 Always-Mapped Attributes

| Attribute | Code | Source | Notes |
|---|---|---|---|
| Target Customer | `target_customer` | category prefix | **Multi-select**: woman→women+girls, man→men, kids→boys |
| Modesty Level | `modesty_level` | category keywords | lingerie/swimwear→revealing, shorts/skirts→minimal, etc. |
| Main Material | `main_material` | `json_ld.material` (string) + `json_ld.additionalProperty` | First known material match |
| Fabric Composition | `fabric_composition` | `json_ld.additionalProperty` array | Free-text composition string |
| Primary Color | `primary_color` | `raw_data.colors[]` | Multi-select, with fallback matching |

### 3.3 Conditional Attributes (Keyword-Matched)

Extracted from product name — routed to type-specific code:

- **Sleeve style**: short/long/sleeveless/cap/puff/3/4/balloon/raglan
- **Pattern**: striped/floral/printed/checked/polka/sequin/embroidered/lace/solid/animal print/geometric/abstract
- **Fit type**: regular/slim/loose/oversize/relaxed/tailored/bodycon/a-line/empire waist/high waist/wide leg/straight leg/skinny
- **Neckline**: v-neck/round/collar/turtleneck/halter/off-shoulder/high-neck/mock neck/square/sweetheart
- **Hem length**: mini/midi/maxi/crop/floor-length/ankle

### 3.4 Material Extraction

**Source priority**:
1. `json_ld.material` (string) — e.g., `"100% sheep leather"`
2. `json_ld.additionalProperty` — composition breakdown array
3. `extra_detail.materials` (legacy, often empty)

The first known material keyword found in any source is used as `main_material`. The full composition string (from `additionalProperty`) is stored as `fabric_composition`.

---

## 4. Sizes & Variants

### Size Extraction
Sizes are extracted from `json_ld.hasVariant[].size`:
```python
{"size_label": "35", "size_system": "EU", "sort_order": 0}
```

### Variant Creation
Each `hasVariant` entry becomes a variant. Color assignment to variants uses positional alignment: when `has_multiple_colors` is true, colors are distributed across variants by dividing the variant list by the number of colors.

---

## 5. Data Flow

```
fetch_sitemap.py  →  scrape_products (URLs inserted)
                            ↓
run.py  →  ZaraScraper  →  scrape_products (raw_data filled)
                            ↓
download_images.py  →  scrape_products (images_cached = True)
                            ↓
transform.py  →  api_client.py  →  POST /api/v1/stores/{id}/products
                                         ↓
                                  api_product_id stored back
```

### Transform Script
```bash
uv run scripts/scrapers/transform.py                                # sync all pending
uv run scripts/scrapers/transform.py --limit 10                     # sync first 10
uv run scripts/scrapers/transform.py --limit 10 --dry-run           # count only
uv run scripts/scrapers/transform.py --source-id 12345678           # specific product
uv run scripts/scrapers/transform.py --api-key tea_xxxxxxxxxxxx     # with API key auth
uv run scripts/scrapers/transform.py --source zara --limit 50       # filter by source
```

### Batch Scraping
```bash
# Run batches of 50 products with auto-check of pending count
./scripts/scrapers/run_batch.sh
```

### Image Cache
```bash
# Cache images to disk before transform (required if not scraped with run.py)
uv run scripts/scrapers/download_images.py --limit 100 --concurrency 20
```

### Backfill
```bash
# Duplicate images across color variants
uv run scripts/scrapers/backfill_variant_images.py

# Link size options to existing variants
uv run scripts/scrapers/backfill_variant_sizes.py
```

### Key Design Changes from v1
- **Dynamic product types**: No longer hardcoded to `"fashion"` — resolved per product
- **Multi-value target_customer**: Woman's products tagged as both `women` and `girls`
- **Material from json_ld**: Uses `json_ld.material` and `additionalProperty` instead of broken `extra_detail.materials`
- **Color fallback chain**: 5-level matching with alias map
- **Child category resolution**: Products assigned to specific child categories (not just roots)
- **Per-type attribute routing**: Same keyword extraction yields different attribute codes by product type
