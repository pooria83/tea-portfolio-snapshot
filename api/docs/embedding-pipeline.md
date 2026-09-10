# Embedding Pipeline

How product data becomes a vector in Qdrant — from catalog row → bilingual embed text → engine embedding → webhook confirmation. Embeds are **per-model**: each product has one row per embedding model in `product_embeddings`, and the engine stores vectors in a per-model Qdrant collection.

## End-to-End Flow

```
store_products row
      │  get_product_info(en+ar) → minify
      ▼
build_embed_data: (embed_text, product_data, filters)
      │  product_embeddings row (product_id, model_name) → "pending"
      ▼
POST /embed-product  ──►  AI Engine: embed (its active model) → Qdrant collection "products-<slug>"
      │                          │
      │ webhook                  ▼
      ▼              {"status": "done", "model": ...} | {"status": "error", ...}
POST /webhook/embedding-result ──► product_embeddings.embedding_status = done/error
```

The engine **never queries the API or Postgres**; every status update is a callback. If the webhook call fails, the row stays `pending` and the recovery cron (below) re-submits it.

## Active Embedding Model

- Source of truth: `system_settings` key `embedding_provider` — either a JSON dict `{"provider": "...", "model": "...", "base_url": "...", "api_key": "..."}` or a legacy plain provider name.
- `get_active_embedding_model(db)` (`app/services/embedding_config.py`) reads the `model` key from that JSON and returns a `(model_name, dimensions)` tuple; falls back to `DEFAULT_EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"` / `DEFAULT_EMBEDDING_DIMS = 1024` when unset.
- The model name is a **snapshot** on every `product_embeddings` row, so history stays meaningful even if the `embed_models` row is removed.
- When an admin changes `embedding_provider` and the model **actually changed**, the API automatically calls `reindex_active_model()` (see below). Admins can also trigger it manually.
- **Dimensions** are resolved from the model name through `EMBEDDING_MODEL_DIMS` (`app/services/embedding_config.py`), the API-side mapping that mirrors the AI Engine's `embedding_dims_for`:
  - `Qwen3-Embedding-0.6B` → 1024, `Qwen3-Embedding-4B` → 2560, `Qwen3-Embedding-8B` → 4096, `F2LLM-v2-4B` → 2560, `jina-embeddings-v5-text-small` → 1024, `BGE-M3` → 1024, `Nomic Embed v2` → 768, `multilingual-e5-base` → 768, `multilingual-e5-large-instruct` → 1024 (bare names, matching the `embed_models` catalog; the `Qwen/` org prefix is stripped before lookup).
  - Unmapped models fall back to `DEFAULT_EMBEDDING_DIMS` with a `logger.warning`, so a misconfigured model never silently uses arbitrary dims.
  - `get_embedding_dims(model_name)` exposes the lookup for callers that only need the dimension.
- The engine (not the API) creates and validates the Qdrant collection; it derives dims from the model name itself, so the two mapping tables must stay in sync. Adding a model means: 1) enable the `embed_models` row, 2) add `<ModelName>: <dims>` to both `EMBEDDING_MODEL_DIMS` (API) and `EMBEDDING_MODEL_DIMS` (AI Engine `app/services/embedding_dims.py`).

## Per-Model Status Table (`product_embeddings`)

| Column | Meaning |
|---|---|
| `product_id` | FK → `store_products.id` (CASCADE) |
| `model_id` | FK → `embed_models.id` (SET NULL) — nullable snapshot |
| `model_name` | embedding model name snapshot (e.g. `Qwen/Qwen3-Embedding-0.6B`) |
| `embedding_status` | `pending` / `generating` / `done` / `error` |
| `embedding_error` | error message when `error` |

- `UNIQUE (product_id, model_name)` — one row per product per model.
- Migration `c1f2e3d4a5b6` created the table and **dropped** `store_products.embedding_status` / `store_products.embedding_error`.
- Insert-id convention: backfill/reindex inserts use `md5(product_id || ':' || model_name)` as the row id so they are idempotent.
- `_ensure_active_model_rows()`: before any scan the API inserts missing `pending` rows for the active model (preserves the legacy "every product is eligible" behavior).

## Status Lifecycle

| Value | Meaning |
|---|---|
| `pending` | marked for embedding, awaiting pickup |
| `generating` | **claimed/in-flight** — a worker atomically claimed the row and submitted it |
| `done` | confirmed by webhook (or by the backfill script in no-webhook mode) |
| `error` | confirmed failure (webhook reason, or build/submit failure) |

### Atomic Claiming (`claim_row`)

Before submitting, a worker claims the row with a single conditional UPDATE: `SET embedding_status = 'generating' WHERE embedding_status IN ('pending', 'generating', 'error')` (`claim_row`, `app/repositories/embedding.py`). `error` rows are claimable so deliberate retries can resubmit them. Only one worker wins per row — a concurrent cron/backfill run logs *"row claimed by another worker"* and skips the product. When a `stale_cutoff` is passed (cron path), only rows not refreshed within the staleness window are claimable, so a row another worker just picked up is never double-submitted.

Note the asymmetry: routine recovery-cron **fetches** only `pending`/`generating` rows; `error` rows enter the pipeline again only through the manual backfill script (`--include-errors`) or a re-index.

## Re-Index (`reindex_active_model`)

`reindex_active_model(db, model_name)` marks **every product** pending for the given model with a single upsert:

```sql
INSERT INTO product_embeddings (id, product_id, model_id, model_name, embedding_status)
SELECT md5(s.id || ':' || :model), s.id, em.id, :model, 'pending'
FROM store_products s
LEFT JOIN embed_models em ON em.model_name = :model
ON CONFLICT (product_id, model_name)
DO UPDATE SET embedding_status = 'pending', embedding_error = NULL, updated_at = now()
```

Returns the number of affected rows. Used:
- **Automatically** when `embedding_provider` is updated and the model changed (in `system_settings.py`).
- **Manually** via `POST /admin/cron/embedding-products/reindex` (with an `activity_logs` `REINDEX` row).

## Embed Text Building (`build_embed_data`)

Produces a 4-tuple `(embed_text_en, embed_text_ar, product_data, filters)` —
**one monolingual passage per language** (P3 language split, so each language
is embedded with its own vector and sparse tokens, searched independently):

- `embed_text_en` / `embed_text_ar` — per-language structured text via
  `_format_embed_text(info, flagged_codes, lang)`: name, category, brand,
  attribute lines, short description, plus **localized enrichment tokens**
  (price tier, season, occasion — Arabic variants for `ar`). Concrete fields
  (name/category/brand/attributes) appear before descriptions so they carry
  more vector weight. **Only attributes flagged `is_search_affecting=true`
  are written** (`attributes.is_search_affecting`, managed globally via
  `scripts/seed_data/search_affecting_flags.json`) — this is the global
  mechanism that makes any attribute (neckline, sleeve, occasion, watch
  movement, fragrance notes, ...) searchable via vector similarity with zero
  per-attribute code. A language with no usable content yields `None` for that
  passage.

```
en:  name_en | category_en | brand_en | attribute: values_en | short_description_en | enrichment (en)
ar:  name_ar | category_ar | brand_ar | attribute: values_ar | short_description_ar | enrichment (ar)
```

- **`product_data`** (payload, stored verbatim in Qdrant): `{en: {name, brand, category, attributes, price, currency, images, sizes, ...}, ar: {...}, store_id}` — the minified bilingual dictionaries (plus `image_url` extracted before minification). The engine uses it for locale-aware chat context and sparse name-token boosts.
- **`filters`** — flat Qdrant payload metadata (see below).
- **Submission**: `_embed_single_product()` submits **one `embed_product` call per language** (en then ar, each with its own monolingual passage) → the engine stores one point per `uuid5(product_id_lang)` with per-language dense + BM25 sparse vectors. The `product_embeddings` row is marked `done` only when **all** language calls succeed (one webhook per language, both idempotent upserts of the same `(product_id, model)` row).

## Filters (`filters` dict — Qdrant metadata payload)

Flat, single-level keys for payload-based filtering:

| Filter key | Source | Normalization |
|---|---|---|
| `_color` | color attribute values (EN+AR) | color aliases mapped (e.g. `printed → Multicolor`, `مطبوع → متعدد الألوان`); also collected from variants' attribute options |
| `_material` | material attribute values (EN+AR) | raw values |
| `_category` | category chain EN+AR names | raw values |
| `_brand` | brand EN+AR names | raw values |
| `_gender` | gender attribute | **normalize map**: `men/mens→men`, `women/womens→women`, `girls→girls`, `boys→boys`, `babies/baby→babies`, `kids→kids`, `unisex→unisex`; unknown → `unisex` |
| `_color_family` | from `attribute_options.color_family` | e.g. `reds-pinks`, `blues-purples`, `greens`, `browns`, `blacks-greys-whites`, `oranges-yellows`, `multicolor`, `none` |
| `_size` | `product_sizes` rows (label + system) EN+AR | canonical lowercase tokens via `_normalize_size_tokens`: letters/words collapse (`M`/`medium`→`m`, `XL`/`extra large`→`xl`), free sizes → `one size`, numeric sizes keep the raw value plus a system-tagged token when a system is present (`42`+`EU`→`["42", "eu:42"]`); no stock gating; products with no declared sizes (perfume, jewelry, eyewear) fall back to `["one size"]`; deduped |

## Webhook (`POST /webhook/embedding-result`)

Request body: `{"product_id", "lang", "status": "done"|"error", "error"?: str, "model"?: str}`.

- `model` is optional — when omitted the API falls back to the current active model.
- The handler upserts the row in `product_embeddings` (constraint `uq_product_embedding_product_model`) and stores the error text on failure.
- **Auth**: the route is gated by `verify_webhook_secret` — callers must present the shared secret via the `X-Webhook-Secret` header or a `?token=` query parameter. Verification is disabled when `settings.webhook_secret` is unset. The cron appends `?token=<secret>` to the callback URL it builds (`build_webhook_url`).

## Cron (`run_embedding_recovery_cron`)

- Loop interval: **60s**.
- Distributed lock: Redis key `cron:embedding_recovery` with TTL **600s** (owner-token acquire via SET NX EX, atomic compare-and-del release) — only one instance runs a cycle; the others log a lock miss and skip.
- Batch size: **50** products per cycle (single DB session, sequential per batch).
- Each cycle: resolve active model → `_ensure_active_model_rows()` → `_fetch_stale_products()` → `_embed_single_product` → claim row → `embed_product(product_id, "en", embed_text_en, webhook_url=API embedding webhook, payload, filters)` + the same for `"ar"` — **one call per language**, row marked `done` only when both succeed (each language fires its own webhook).
- If building the embed data fails → row marked `error` with reason (logged).
- Writes one `activity_logs` `CRON_RUN` row per cycle (products count in `details`).

The cron touches **only Postgres + the engine** — it has no chat/message responsibilities.

## Manual Backfill (`scripts/run_embedding_backfill.py`)

`uv run scripts/run_embedding_backfill.py [--include-errors]`

- The only flag is `--include-errors` (also retry rows in `error`); there is no concurrency option — parallelism is hardcoded (`max_concurrency=5` passed to `submit_for_embedding_concurrent`, one SQLAlchemy session per worker).
- `fetch_unembedded_products(include_errors=..., limit=500)` (default fetch limit **500**) always selects `pending` + `generating` rows for the active model; `error` rows are included only with the flag. Missing rows are inserted first.
- Logging: the script calls `logger.remove()` and installs its own stderr INFO handler.
- Runs in **synchronous no-webhook mode** (`webhook_url=None`): each language's `/embed-product` call waits on the engine response and the row is marked `done`/`error` directly from that response (`embedding_cron._embed_single_product`) — no webhook reconciliation.

## Admin Surface

- `GET /admin/cron/embedding-products` — paginated per-model rows (filters: `embedding_status`, `model`). Items carry `embedding_model`, `embedding_status`, `embedding_error`, `updated_at`.
- `GET /admin/cron/embedding-products/{product_id}` — product with `embeddings[]` (one `ProductEmbeddingRow` per model: `model_name`, `model_id`, `embedding_status`, `embedding_error`, `updated_at`) + embed-text preview.
- `GET /admin/cron/embedding-products/active-model` — `{"active_model": "..."}`.
- `POST /admin/cron/embedding-products/reindex` — `reindex_active_model` for the active model; returns `{"affected", "active_model"}` and writes a `REINDEX` activity log.
- `GET /admin/cron/summary` — AI-description cron counters: `{"llm": {"total", "pending", "generated"}}`.
- `GET /admin/embed-models` — the embedding-model catalog (`embed_models` rows; active models only).

## Testing

`tests/test_cron_products_embedding.py` (list/detail/active-model/reindex, model + status filters), `tests/test_webhooks.py` (done/error/model-fallback webhook paths), `tests/test_embedding_cron.py` (fixture seeds `product_embeddings` with `DEFAULT_EMBEDDING_MODEL`). Embedding against real TEI is **not** part of the test suite.
