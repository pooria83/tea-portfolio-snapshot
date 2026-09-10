# Search Evaluation (`/admin/search-eval`)

Golden-set evaluation for hybrid product search. Admins curate a set of queries with known-relevant product IDs, run searches, and track **MRR@10** and **Recall@10** — overall and per locale (en/ar). Query rows can be hand-written, imported from a reviewed JSON file (`source=seed`), or LLM-generated against a live catalog summary (`source=llm`).

## Data model

Two tables created by migration `700234efae53` (`app/models/search_eval.py`):

### `search_eval_queries`

| Column | Type | Notes |
|---|---|---|
| `id` | String(36) PK | uuid4 |
| `text` | Text | query text |
| `locale` | String(5) | indexed; `en` / `ar` |
| `source` | String(10) | indexed; `manual` \| `llm` \| `seed` |
| `status` | String(12) | indexed; `pending` \| `evaluated` \| `skipped` |
| `rewritten_query` | Text, nullable | optional engine-style rewrite |
| `filters` | JSON, nullable | dict of filter values |
| `created_by` | FK → `users.id`, nullable | admin who created it |

`UNIQUE (text, locale)` (`uq_search_eval_query_text_locale`) — dedup anchor for both generation and import. Timestamps via `TimestampMixin`.

### `search_eval_judgments`

| Column | Type | Notes |
|---|---|---|
| `id` | String(36) PK | uuid4 |
| `query_id` | FK → `search_eval_queries.id` **CASCADE**, indexed | |
| `product_id` | String(36) | store product UUID |
| `relevant` | Boolean | import always writes `True`; manual sets can mark non-relevant |
| `rank` | Integer, nullable | observed rank in results (schema validates 1–100) |

`UNIQUE (query_id, product_id)` — one judgment per product per query. Only `created_at` (no update tracking).

## Endpoints

All routes live under `/api/v1/admin/search-eval` (router prefix `admin/search-eval`) and require **admin auth** (`Depends(get_admin_user)`).

| Method | Path | Description |
|---|---|---|
| POST | `/admin/search-eval/queries/generate` | LLM-generates candidate queries from a bilingual catalog context (`count` 1–50, default 10; `locales` default `["en","ar"]`) |
| POST | `/admin/search-eval/queries/import` | Imports golden-set items `[{text, locale, relevant_ids}]` (max 500) as `source=seed` |
| GET | `/admin/search-eval/queries` | Paginated list; filters `locale`, `source`, `status`, `q` (text ilike); newest first |
| PATCH | `/admin/search-eval/queries/{id}` | Updates `status`, `rewritten_query`, and/or `filters` |
| PUT | `/admin/search-eval/queries/{id}/judgments` | Replace-all judgments for one query (max 200 items) |
| GET | `/admin/search-eval/metrics` | MRR@10 + Recall@10, overall + per-locale (cached 300s) |
| POST | `/admin/search-eval/search` | Proxy to AI Engine `/eval/search` with per-hit scores |

Failures talking to the engine raise `ServiceUnavailableError` with `translation_key=E.AI_ENGINE_ERROR`.

## Workflow

### 1. Import the golden set (`POST /queries/import`)

Body: `{"queries": [{"text": "floral midi dress", "locale": "en", "relevant_ids": ["<uuid>", …]}]}`.

- Existing `(text, locale)` pairs are **skipped** (counted in the result).
- New queries get `source="seed"` and `status="evaluated"` when `relevant_ids` is present, otherwise `"pending"`.
- Each ID creates a `relevant=True` judgment (deduped per query+product).
- Response: `{created, skipped, judgments_created}`.
- Writes invalidate the cache prefixes of both tables (see below).

See [the golden-set file](#golden-set-file) below — review before importing.

### 2. LLM-generated candidates (`POST /queries/generate`)

`build_catalog_context()` compacts the catalog into ≤8000 chars: every product type as `name_en (name_ar)`, then each attribute flagged `is_search_affecting=true` with a sample of its major option values (up to 8 fetched, first 4 shown). The context is sent to AI Engine `POST /eval/queries` (`AIEngineClient.eval_generate_queries`). Returned rows are sanitized (non-empty text, locale ∈ {en, ar}), deduped against existing `(text, locale)` pairs, and persisted with `source="llm"`, `status="pending"`.

Because the context is built from `is_search_affecting` attributes only, the generated queries stay aligned with what vector search can actually match — the same flags that feed embed text (see [Embedding Pipeline](embedding-pipeline.md) and [Product Definition System](product-definition-system.md)).

### 3. Curate

- `GET /queries?locale=ar&status=pending&q=dress&skip=0&limit=20` to triage.
- `PATCH /queries/{id}` to mark `skipped`/`evaluated` or attach `rewritten_query`/`filters`.
- `PUT /queries/{id}/judgments` replaces the full judgment list (delete + insert) and flips the query to `evaluated` when any judgment is relevant.

### 4. Measure (`GET /metrics`)

Loads all `evaluated` queries + all judgments and computes:

- **MRR@10** — mean over evaluated queries of `1/best_rank` where best_rank is the minimum rank among relevant judgments, counted only when ≤10 (otherwise contributes 0).
- **Recall@10** — mean of `|relevant judgments with rank ≤ 10| / |relevant judgments|`.
- Reported as `overall` (locale key `"all"`) plus one item per locale in `per_locale` (`en`, `ar`); values rounded to 4 decimals; `query_count` counts queries that have at least one relevant judgment.

Result is cached through `cache_or_fetch` under `seval:metrics:all` — `CacheKeys.SEARCH_EVAL_METRICS = CacheKey("seval:metrics:", 300)` in `app/core/cache.py`. Both tables map to that prefix in `PREFIX_BY_TABLE`, so any write (import/PATCH/judgments) invalidates it immediately.

### 5. Probe ranking (`POST /search`)

Body `{query, locale, limit (1–50, default 10)}` proxies straight to AI Engine `/eval/search` — the deterministic parse/scoring path used for evaluation, with `rewritten_query`, `filters`, `specs`, and per-hit `rank`/`score` returned. Image URLs are normalized to absolute form before responding, so hits can be eyeballed directly in an admin UI.

## Golden set file

`scripts/seed_data/search_eval_golden.json`:

```json
{
  "description": "Search evaluation golden set. relevant_ids reference store_products …review before importing…",
  "queries": [
    { "text": "floral midi dress", "locale": "en", "relevant_ids": ["146f1725-…", "…"] }
  ]
}
```

- **166 queries** (124 en / 42 ar); `relevant_ids` reference `store_products` in the dev DB (embedded, `done` status).
- **Review-before-import policy**: the IDs were drafted from the dev catalog and are user-curated — read the file and adjust before pushing it through `POST /admin/search-eval/queries/import`.
