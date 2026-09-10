# Redis Caching Layer

The API offloads hot read paths from PostgreSQL to Redis through a **key-registry-driven, write-invalidation cache**. Every cache key prefix and its TTL live in one place (`app/core/cache.py`), so the key space stays centralized and TTLs can never drift from the keys.

## Design Principles

- **One source of truth** — `CacheKeys` is a registry of `CacheKey(prefix, ttl)` dataclasses. Repositories build keys through these constants/builders; never string literals.
- **Repository-layer caching** — cache reads happen inside repositories and return **JSON-safe DTO dicts** (never ORM rows). Services orchestrate; routers wire the Redis dependency.
- **Fail-open** — every cache helper catches Redis errors, logs a warning, and falls back to the database. Caching can never break a request.
- **Whole-prefix invalidation** — writes delete every key under the prefixes their table touches (`SCAN` + `DEL`), so a single write clears all derived reads (lists, per-id keys, per-locale keys) without tracking individual keys.
- **Never cache user-scoped data** — conversations, messages, search history, activity logs, scrape state, and the seller's own product lists stay DB-only.

## The Key Registry & TTLs (`CacheKeys`)

| Constant | Prefix | TTL | Purpose |
|---|---|---|---|
| `SYSTEM_SETTINGS` | `sys:settings:` | 300s | system settings list |
| `SYSTEM_SETTING` | `sys:setting:` | 300s | single system setting by key |
| `PROMPT` | `sys:prompt:` | 600s | prompt template by type |
| `LLM_SETTING` | `llm:setting` | 300s | LLM defaults (default/user-comm model) |
| `EMBED_MODEL` | `embed:active-model` | 60s | active embedding model resolution |
| `EMBED_MODEL_BY_NAME` | `embed:model:` | 60s | embedding model row by name |
| `LLM_MODEL_CONFIG` | `llm:config:` | 120s | resolved model config for the AI engine |
| `LLM_MODELS` | `llm:models:` | 300s | LLM model catalog |
| `CAT_PRODUCT_TYPES` | `cat:product_types:` | 3600s | product types list/detail |
| `CAT_CATEGORIES` | `cat:categories:` | 3600s | category tree (`all`, `pt:{id}`) |
| `CAT_ATTRIBUTES` | `cat:attributes:` | 3600s | attributes by group / product type |
| `CAT_ATTRIBUTE_GROUPS` | `cat:attribute_groups:` | 3600s | attribute groups (`all`, `pt:{id}`) |
| `CAT_ATTRIBUTE_OPTIONS` | `cat:attribute_options:` | 3600s | attribute options by attribute |
| `CAT_BRANDS` | `cat:brands:` | 3600s | brand list |
| `CAT_IMAGE_VIEW_TYPES` | `cat:image_view_types:` | 3600s | image view types by product type |
| `CAT_STORE_TYPES` | `cat:store_types:` | 3600s | store types by locale |
| `CAT_COUNTRIES` | `cat:countries:` | 3600s | country list |
| `CAT_CURRENCIES` | `cat:currencies:` | 3600s | currency list |
| `PRODUCT_INFO` | `product:info:` | 600s | full product info by `{product_id}:{lang}` (UUID→name resolution) |
| `PRODUCT_DETAIL` | `product:detail:` | 300s | public product detail by `{store_id}:{product_id}` |
| `STORE_STATS` | `store:stats:` | 60s | seller dashboard `{total, active}` counts by store-id signature |
| `RANDOM` | `product:random:` | 3600s | public random product cards by limit |
| `SEARCH_EVAL_METRICS` | `seval:metrics:` | 300s | search-eval MRR@10/Recall@10 by signature |

TTL rationale: catalog data changes rarely (1h, invalidated on writes anyway), product info/detail sit on the hot public read path (5–10 min), store stats need freshness (60s), LLM/embedding config follows admin changes (1–5 min), random cards are public and cheap to regenerate (1h).

## Read Path (`cache_or_fetch`)

```python
value = await cache_or_fetch(
    redis, key, ttl,
    fetch,          # async callable that queries the DB and returns a DTO dict
    lock=False,     # True → stampede guard for hot single-value keys
)
```

- **Hit** → JSON-decoded value returned; the DB is never touched.
- **Miss** → `fetch()` runs, the result is JSON-encoded and stored with the TTL (`json.dumps(..., default=str)` keeps datetimes/decimals safe).
- **Fail-open** — a Redis error at any step logs `Cache read/write failed for ...` and returns the fetched value.
- **`None` results are treated as a miss** — they are stored as JSON `null` and re-fetched on the next call, so caching only applies to non-`None` values.
- **Stampede lock (`lock=True`)** — a short `SET NX EX 2` lock guards hot single-value keys (e.g. active embedding model, system settings): the lock holder fetches and stores; concurrent callers wait up to ~1s for the value before fetching directly.

Key builders (`CacheKeys.product_info(id, lang)`, `product_detail(store_id, product_id)`, `store_stats(signature)`, `random(limit)`, …) are the only way to construct keys.

## Write Path (invalidation)

Every repository declares `TOUCHES: frozenset[str]` — the tables its methods read or write. `app/core/cache.py` maps each table to the read prefixes it feeds:

```python
"store_products": ("product:detail:", "store:stats:", "product:info:", "product:random:"),
"product_images": ("product:info:", "product:random:"),
"product_variants": ("product:info:",),
"product_sizes":   ("product:info:",),
"product_pieces":  ("product:info:",),
"system_settings": ("sys:settings:", "sys:setting:", "embed:active-model"),
"prompt_templates":("sys:prompt:",),
"llm_settings":    ("llm:setting",),
"llm_models":      ("llm:config:", "llm:models:"),
"llm_api_keys":    ("llm:config:", "llm:models:"),
"embed_models":    ("embed:model:", "embed:active-model"),
"product_types":   ("cat:product_types:", "cat:categories:"),
"categories":      ("cat:categories:",),
"attributes":      ("cat:attributes:", "cat:attribute_groups:", "cat:attribute_options:"),
"attribute_groups":("cat:attribute_groups:", "cat:attributes:"),
"attribute_options":("cat:attribute_options:", "cat:attributes:"),
"brands":          ("cat:brands:",),
"product_type_image_view_types": ("cat:image_view_types:",),
"store_types":     ("cat:store_types:",),
"countries":       ("cat:countries:",),
"currencies":      ("cat:currencies:",),
"product_embeddings": ("product:info:", "embed:model:"),
"search_eval_queries": ("seval:metrics:",),
"search_eval_judgments": ("seval:metrics:",),
```

After a write commits, the service calls:

```python
await invalidate_tables(redis, {"store_products", "product_images", ...})
```

which `SCAN`s and `DEL`s every key under each mapped prefix (deduplicated per prefix). Invalidation runs **after** `flush()`/commit so the DB is consistent before the cache empties; the next read repopulates it. A failed invalidation is logged and never blocks the request (stale entries expire via TTL).

### Automatic invalidation via `BaseRepository`

`BaseRepository` (`app/repositories/base.py`) makes this automatic for simple CRUD: every repository declares `TOUCHES`, and the generic `add()`/`delete()` methods call `_invalidate()` → `invalidate_tables(self.redis, self.TOUCHES)` right after `flush()`. Repos constructed with a Redis client therefore keep their table's derived keys fresh with zero extra code; repos without Redis (or with an empty `TOUCHES`) skip invalidation silently.

## Undocumented Key Variants

Besides the registry prefixes, three composite keys are built inline from registry constants — all share the prefix TTL:

| Pattern | Built by | Purpose |
|---|---|---|
| `sys:settings:bykeys:{signature}` | `SystemSettingRepository.list_by_keys` | batched multi-key settings fetch (signature = comma-joined sorted requested keys) |
| `cat:attribute_options:major:{id}:{limit}` | `AttributeOptionRepository.list_major_by_attribute_dto` | "major" attribute options per attribute, capped |
| `cat:product_types:detail:{id}` | `product_definition_service.get_product_type_detail` | full product-type detail payload incl. attributes |

## Where Caching Lives

| Layer | Responsibility |
|---|---|
| `app/core/cache.py` | `CacheKeys` registry, `cache_get/set`, `invalidate_prefix/tables`, `cache_or_fetch`, stampede lock |
| Repositories | `BaseRepository(db, redis=None)`; catalog/reference repos call `cache_or_fetch` internally and return DTO dicts |
| Services | Decide cache vs DB, resolve relative image URLs after reads, call `invalidate_tables` after writes |
| Routers | Wire `redis: AsyncRedis = Depends(get_redis)` on endpoints that read or write cached data |

Catalog DTOs are **dicts, not ORM rows** — services never leak ORM instances out of cached paths.

## Cached Endpoints (by phase)

- **Phases 1–2 (system/config)**: system settings list/single, prompt templates, LLM settings, LLM model config + models, active embedding model + by-name.
- **Phase 3 (catalog)**: product types, categories, attributes (+groups/options), brands, image view types, store types, countries, currencies.
- **Phase 4 (products)**: `GET /stores/{store_id}/products/{product_id}` (detail, 300s), `GET /product-info/{product_id}/{lang}` (600s), `GET /stores/my/products/stats` (60s), write invalidation on every product/image/variant/size/piece mutation.
- **Phase 5 (LLM + eval)**: resolved model config for the engine (120s), search-eval metrics (300s).
- **Phase 6 (seeds)**: `scripts/seed_cache_invalidation.py` clears the affected prefixes after bulk seeding (called from `seed.py`, `seed_product_definitions.py`, `seed_stores.py`).

## Lightweight Product Lists

`GET /stores/my/products`, `GET /stores/{store_id}/products` (list), and `GET /public/products/random` return `StoreProductListItem` — a 16-field card (id, store_id, store_name, product_type_id, trilingual names, brand_name, status, prices, currency, quantity, has_variants, `image_url` = first image, resolved to full MinIO URL).

They use **flat queries** (`StoreProductRepository.list_by_store_ids_light` / `search_by_name_light` / `random_light`): one join to Brand + Store, plus one first-image query — no `selectinload` chains, no variants/descriptions payloads.

- Seller/store lists are **user-scoped** → never cached (skip/limit/q/store_id vary per request).
- `random` is **public and fixed-limit** → Redis-cached 1h under `product:random:{limit}` and invalidated on `store_products`/`product_images` writes.

The heavy `get_store_product_response` (full `StoreProductResponse`) remains only for the detail endpoint; the web UI's product-view modal fetches it on demand.
