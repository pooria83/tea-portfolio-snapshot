# Search Quality

How the AI Engine's product search finds the right products: the dense +
sparse hybrid pipeline, language preference, query augmentation, score
thresholds, and the admin evaluation workflow used to measure and tune it.

This document covers the **search quality plan** implemented on top of the
classic dense vector search (described in [Embedding](embedding.md#4-search)
and [Chat Flow](chat-flow.md)). It is the reference for *why* the search
behaves the way it does and *how to evaluate and tune it*.

## 1. The pipeline at a glance

```
user query
   │
   ▼
intent routing / search resolution (tool-calling or parse path — see chat-flow.md)
   ▼
search spec(s): (search_query, filters)
   │
   ├─ dense vector: embed_query(search_query)          ─┐
   │                                                   │  merged with
   ├─ sparse vector: BM25-style term-frequency tokens   │  Fusion.RRF (k=60)
   │   from the raw query text (query_text)             │  over a wider pool
   │                                                   ─┘
   ▼
fused hits → score threshold (model-aware) → tiered filter fallback
   ▼
dedupe by product_id with prefer_lang (detected locale)
   ▼
results (ranked, scored)
```

Two search entry points consume this pipeline:

- `rag.search` — the chat path (`/chat`), returns ranked products only.
- `rag.search_scored` — the eval path (`/eval/search`), returns the same
  rankings but keeps each hit's raw score for offline metrics.

Both are byte-identical in behavior when `query_text` is absent — hybrid mode
is purely additive.

## 2. Hybrid dense + sparse search

Implemented in `app/services/rag.py` (`_query_hits`) and enabled per
collection when the Qdrant collection carries the named sparse vector
`text_bm25` (`_sparse_enabled`).

### 2.1 The sparse vector (`text_bm25`)

Every collection is created with a named sparse vector config. The engine
writes the sparse vector **client-side** at embed time — no external sparse
encoder, no new infrastructure:

- **Tokenizer** (`_tokenize`): NFKD normalization, then split on EN/Arabic
  letters and digits (keeps `ساعة` intact, splits `dress-123`).
- **Light stemming**: EN and Arabic suffix stripping (plurals, verb endings).
- **Stopwords dropped** (EN + Arabic lists).
- **Term frequencies** as raw counts hashed to indices with `_fnv1a` (stable,
  not model-dependent).
- **Name-token boost ×2**: tokens present in the product's `product_data`
  name (en + ar) get doubled TF so the product name carries more lexical
  weight than the description body.
- **`Modifier.IDF`** is applied by Qdrant from collection stats, so the sparse
  score is true BM25-style TF·IDF.

### 2.2 When hybrid runs

`search` / `search_scored` accept `query_text` (the raw search query). Hybrid
runs only when **all** of:

1. `query_text` is non-empty (and differs from empty/whitespace),
2. the collection has the sparse config (`_sparse_enabled`), and
3. the sparse vector was actually stored for points (graceful dense-only
   fallback if any of the above fails).

`ensure_collection()` sets up the sparse config on new collections and calls
`update_collection` on existing ones to add it — if the operation fails the
engine logs and keeps running in dense-only mode.

### 2.3 Query shape

When hybrid is active, `_query_hits` runs a **prefetch query** instead of a
plain dense query:

| Prefetch branch | Vector | Filters | Notes |
|---|---|---|---|
| dense | `using=""` (dense vector) | full filters | `score_threshold = self.score_threshold` (model-aware) |
| sparse | `using="text_bm25"` | full filters | same filters applied to the sparse branch |

Both branches search a **wider pool** than the requested limit:

- pool size = `limit × hybrid_pool_multiplier` (default **3**), capped at
  `hybrid_pool_max` (default **100**).
- The two result lists are fused with
  `FusionQuery(Fusion.RRF)` — reciprocal rank fusion — so a lexical match
  that the dense path missed (rare brand spelling, product code, Arabic
  short-form) can still surface. k stays at Qdrant's server default **60**:
  the installed `qdrant-client` rejects a `k` argument, so it is intentionally
  not passed.

Constructor knobs on `RAGService`:

| Knob | Default | Meaning |
|---|---|---|
| `hybrid_pool_multiplier` | `3` | Pool = `limit × multiplier` per branch |
| `hybrid_pool_max` | `100` | Hard cap on the pool size |
| `fusion` | `Fusion.RRF` | Fusion strategy for the prefetch |

### 2.4 What stays dense-only

- **No `query_text`** (e.g. `/similar`): plain dense path, byte-identical to
  pre-hybrid behavior.
- `similar()` always uses the dense vector of the reference point.

## 3. Score thresholds

Dense scores are gated by a model-aware minimum so garbage-vector matches
never surface. The threshold comes from the **vector dimension**, not the
model name:

`SCORE_THRESHOLDS_BY_DIM` in `app/services/rag.py`:

| Dimensions | Threshold |
|---|---|
| 1024 | 0.30 |
| 2560 | 0.25 |
| anything else | 0.30 (default) |

Rationale: 4B/8B (2560/4096-dim) embeddings distribute cosine scores
differently than 0.6B (1024-dim); the 0.25 threshold for 2560-dim was the
initial guess from manual inspection and is **awaiting verification against
eval metrics** — see §6.

`RAGService.set_collection(name, dimensions)` selects the threshold from the
active collection's dimensions, so switching embedding models picks the right
cut automatically.

## 4. `prefer_lang` — language-aware dedupe

Products are indexed once per language (points share `product_id`, one point
per `lang`). Without extra care, the dense search could return the *en* point
of a product the user is asking about in Arabic.

`search` / `search_scored` accept `prefer_lang` (the detected locale, passed
by `/chat` and `/eval/search`):

- During per-tier dedupe by `product_id`, if a same-product point in the
  target language ranks later, it **replaces** the kept point — so the result
  carries the payload language the user is most likely reading.

## 5. `augment_query_text` — filter-value augmentation

The search filters (color, category, ...) are applied as Qdrant field
conditions, but the raw query text embedded for the sparse branch may not
contain the exact tokens the filter matches on (e.g. filter
`color_family = reds-pinks` while the query says "scarlet").

`augment_query_text(search_query, filters)` (defined in
`app/routers/chat.py`; eval imports it from there) appends
the filter's canonical value tokens to the query text used for the sparse
vector, so the sparse branch agrees with the filters:

- Appends: color-family tokens (expanded color names), category tokens,
  brand tokens — whatever the filters carry.
- **Dedupe at stemmed-token level** — already-present tokens are not
  duplicated.
- **`size` is skipped** (size tokens are notoriously noisy for lexical
  matching).
- Called by `_run_search` (chat) and `_run_search_scored` (eval) before
  building `query_text`.

## 6. Evaluation workflow

Search quality is measured with deterministic, repeatable evals — no
tool-calling variance, no LLM randomness in the ranking path.

### 6.1 Golden set (API side)

The API repo owns the golden set:
`product-graph-api/scripts/seed_data/search_eval_golden.json` — **166
queries** (124 en / 42 ar) drawn from real, indexed product ids in the dev
catalog (4B model). Each entry: `{id, query, locale, product_ids}`.

- Judgments are **relevance judgments per product** (`relevant`, `partial`,
  `irrelevant`), maintained through the admin search-eval panel in
  product-graph-web-ui.
- 3 candidate queries were dropped at seed time because none of their
  candidate products had completed indexing (`bodycon dress`, `قلادة`,
  `أقراط`) — nothing to judge against.

### 6.2 Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /eval/queries` | LLM-generate diverse catalog-realistic queries (admin panel) |
| `POST /eval/search` | Deterministic parse-path search with per-hit raw scores |

Both documented in [API Endpoints](api-endpoints.md). Eval runs go through
`_resolve_search(..., use_tools=False)` — the **parse path only** — so results
reproduce across model versions and runs.

### 6.3 Metrics

The admin panel computes standard retrieval metrics over the golden set:

- **MRR** — mean reciprocal rank of the first relevant hit.
- **Recall@k** — fraction of judged-relevant products retrieved in the top k.

The eval endpoints return scores as raw dense/sparse scores (pre-RRF);
ranking is what the chat path sees.

### 6.4 Tuning checklist

1. **Re-index requirement**: items 4–6 of the search-quality plan changed the
   **stored sparse vector content** (tokenizer, boosts) and the **AR index
   strategy** (item 9). Collections built before those commits must be
   **re-embedded** (delete + re-index via the API) for hybrid/eval numbers to
   reflect current behavior.
2. **Thresholds**: if recall@10 is low with acceptable precision, lower the
   dimension bucket's threshold; if irrelevant hits appear, raise it. Start
   with the eval numbers, not manual inspection.
3. **Pool knobs**: `hybrid_pool_multiplier` / `hybrid_pool_max` trade recall
   (bigger pool) against latency (bigger prefetch).
4. **Per-language numbers**: evaluate en and ar separately — AR queries stress
   the stemmer/stopwords and the AR indexing strategy differently.

## 7. Related documents

- [Embedding](embedding.md) §4 — Qdrant search mechanics, filters, tiered
  fallback, payload schema.
- [Chat Flow](chat-flow.md) — where search fits in the `/chat` pipeline.
- [API Endpoints](api-endpoints.md) — `/eval/queries` and `/eval/search`
  contracts.
- `product-graph-api` docs — embedding pipeline (per-language passages,
  `product_embeddings` table), golden set seeding.
- `product-graph-web-ui` docs — admin search-eval panel.
