# Search Evaluation Admin Panel

The admin tool for **measuring and tuning product-search quality** at
`/admin/search-eval` — part of the search-quality plan (engine hybrid
dense+sparse search, per-language passages, golden set).

## Page (`src/app/[locale]/(dashboard)/admin/search-eval/page.tsx`)

Four areas, top to bottom:

### 1. Metric cards

`useGetEvalMetricsQuery` → `GET /admin/search-eval/metrics` →

| Card    | Content                                             |
| ------- | --------------------------------------------------- |
| Overall | `mrr_10` + `recall_10` across all evaluated queries |
| EN      | per-locale metrics (index 0)                        |
| AR      | per-locale metrics (index 1)                        |

Metrics update automatically after generation/import/judging (RTK Query
invalidates `EvalMetrics`).

### 2. Query generation

`useEvalGenerateQueriesMutation` → `POST /admin/search-eval/queries/generate`
with `{count, locales[]}` — the API builds a bilingual catalog context
(product types + `is_search_affecting` attributes + major option values) from
the DB and asks the engine's `/eval/queries` for diverse, catalog-realistic
shopper queries. Generated rows are persisted with `source=llm`,
`status=pending`.

### 3. Golden-set import

`useEvalImportQueriesMutation` → `POST /admin/search-eval/queries/import`
with `{queries: [{text, locale, relevant_ids[]}]}` — paste the golden set
JSON (e.g. from the API repo's `scripts/seed_data/search_eval_golden.json`,
**166 queries: 124 en / 42 ar**). Import creates `source=seed` rows plus
`relevant=true` judgments for the given ids; rows are `evaluated` when ids
were provided. Invalid JSON → inline error (`invalidJson`).

### 4. Queries table + judge dialog

`useGetEvalQueriesQuery` — filters: `locale` (en/ar), `source`
(manual/llm/seed), `status` (pending/evaluated/skipped), `q` (text ilike),
paginated.

Each row's **Judge** action opens the judge dialog:

1. **Search auto-runs on open** — there is no manual "Run search" button; as
   soon as the dialog opens, `useEvalSearchMutation` fires →
   `POST /admin/search-eval/search` with `limit: 20`
   (proxy to engine `/eval/search`: deterministic parse-path, per-hit raw
   scores, normalized image URLs). Results render rank, score, product name/
   brand/price, thumbnail.
2. **Judge** — toggle `relevant` on hits; `useSaveEvalJudgmentsMutation`
   (`PUT /admin/search-eval/queries/{id}/judgments`) replaces all judgments;
   the query becomes `evaluated` when at least one hit is relevant.
3. **Skip** — mark the query `skipped` (no judgments).

`useUpdateEvalQueryMutation` (`PATCH .../queries/{id}`) is wired ONLY to that
Skip action (`status: "skipped"`) — there is no UI for editing
`rewritten_query`/`filters`; a saved `rewritten_query` is display-only in the
table.

## API Surface (proxied through `/admin/search-eval/*`)

| Endpoint                                        | Backend                                                 |
| ----------------------------------------------- | ------------------------------------------------------- |
| `POST /admin/search-eval/queries/generate`      | `admin/search_eval.py` + engine `/eval/queries`         |
| `POST /admin/search-eval/queries/import`        | admin router (persists rows + judgments)                |
| `GET /admin/search-eval/queries`                | admin router (filters + pagination)                     |
| `PATCH /admin/search-eval/queries/{id}`         | admin router                                            |
| `PUT /admin/search-eval/queries/{id}/judgments` | admin router                                            |
| `GET /admin/search-eval/metrics`                | admin router (MRR@10 + Recall@10, overall + per-locale) |
| `POST /admin/search-eval/search`                | proxy → engine `/eval/search`                           |

## Types (`src/types/search-eval.ts`)

`EvalQueryItem` (id, text, locale, source, status, rewritten_query?, filters?,
created_by?, timestamps), `EvalQueriesGenerateRequest`, `EvalQueriesImportRequest`,
`EvalImportResult`, `EvalJudgmentsRequest`, `EvalSearchRequest`,
`EvalSearchResultItem` (rank, score, id, name?, price?, currency, brand?,
image_url?, store_id?, product_data?), `EvalSearchResponse` (query, locale,
rewritten_query?, filters?, specs[], results[]), `EvalMetricItem` (locale,
query_count, mrr_10, recall_10), `EvalMetricsResponse` (overall?,
per_locale[] — index 0 = en, 1 = ar).

## RTK Query Hooks (`src/store/api/adminApi.ts`)

`useGetEvalQueriesQuery`, `useEvalGenerateQueriesMutation`,
`useEvalImportQueriesMutation`, `useUpdateEvalQueryMutation`,
`useSaveEvalJudgmentsMutation`, `useGetEvalMetricsQuery`,
`useEvalSearchMutation` — tags: `EvalQueries`, `EvalMetrics` (generation/
import/update/judging invalidate metrics so cards refresh).

## i18n

`admin.searchEval` namespace in `messages/{en,ar,fa}.json` — all labels above
(generate/import/judge/metrics/table/filters/statuses).

## Tuning workflow (recommended)

1. Import the golden set → verify a sample of judgments.
2. Generate extra `llm` queries per locale and judge them.
3. Read `mrr_10` / `recall_10` per locale — **tune separately for en and ar**
   (AR stresses the engine stemmer/stopwords + the AR indexing strategy).
4. Adjust engine knobs (score thresholds per vector dim, `hybrid_pool_*`)
   in `product-graph-ai-engine` and re-measure here.
5. Remember: sparse-vector content changes (engine items 4–6) require a
   **re-index** of the active model (`/admin/cron/embedding-products/reindex`)
   before eval numbers reflect them.
