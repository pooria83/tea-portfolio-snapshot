# Architecture

This document describes the AI Engine's position in the TEA-assist platform,
its internal components, the application lifecycle, and the end-to-end data
flows. It is the entry point for understanding how the system works.

## 1. System Position

The AI Engine is a **stateless FastAPI service** that sits behind the main
backend API (`product-graph-api`). It owns three AI responsibilities:

1. **Product description generation** — `POST /generate-description`
2. **RAG conversational product search** — `POST /chat` (non-streaming and SSE streaming)
3. **Product embedding into a vector store** — `POST /embed-product` / `POST /embed-text`
4. **Chat support endpoints** — `POST /summarize`, `POST /title` (rolling conversation summary + conversation titles)
5. **Similar products** — `POST /similar` (metadata-aware lookalikes of an indexed product)
6. **Search evaluation** — `POST /eval/queries`, `POST /eval/search` (admin search-quality measurement)

It is stateless in the product-data sense: it keeps **no product database** and
no chat history of its own. All product data arrives in request bodies, and all
persistent state lives in external systems:

| External system | Used for |
|---|---|
| **Qdrant** | Vector store for product embeddings — one collection per embedding model (`products-{slug}`, see [Embedding](embedding.md#20-collection-naming)) |
| **PostgreSQL** (shared with the API) | Read-only: LLM API keys stored encrypted in `llm_api_keys` / `llm_models` |
| **OpenCode Zen** | Default LLM provider (`https://opencode.ai/zen/v1`) |
| **OpenRouter** | Optional LLM / embedding provider |
| **TEI server** | Optional embedding provider (local container or Colab tunnel) |
| **The backend API** | Calls every AI endpoint; also serves as the bootstrap source of runtime config |

```
┌──────────────────────────┐        HTTPS / Docker network
│   product-graph-api      │───────────────────────────────┐
│  (FastAPI, PostgreSQL,   │  POST /generate-description    │
│   Redis, WS relay)       │  POST /chat (REST + SSE)       │
│                          │  POST /embed-product (+webhook)│
└──────────────────────────┘  POST /summarize, /title       │
        │                            POST /config           │
        │                                │                  │
        │                    ┌───────────▼──────────────────┴───────┐
        │                    │   Product Graph AI Engine (:8003)     │
        │   webhook:         │                                      │
        │   embedding status │  routers ──► services ──► providers  │
        │                    │     │              │                 │
        │                    │  Qdrant(6333)  OpenAI clients        │
        │                    │  PG (keys)     (Zen/OpenRouter/TEI)  │
        └────────────────────┘                                      │
                                   ┌────────────────────────────────┘
                                   ▼
                        Qdrant vector DB (products-qwen-... per model)
                        PostgreSQL llm_api_keys / llm_models
```

## 2. Component Overview

### 2.1 Application entry — `app/main.py`

- Builds the `FastAPI` app and registers middleware (outermost first —
  `add_middleware` prepends): `ActivityLoggerMiddleware` →
  `EngineAuthMiddleware` → `LogContextMiddleware`. `EngineAuthMiddleware`
  guards every route except `/health` with the `X-API-Key` header
  (`ENGINE_API_KEY` setting; disabled when empty).
- The `lifespan` handler initializes everything on `app.state`:
  - `db_engine` — async SQLAlchemy engine (PostgreSQL, for LLM key resolution only)
  - `llm_client` — the default (non-conversational) LLM client
  - `comm_llm_client` — the conversational/comm LLM client (may differ from `llm_client`)
  - `embedding_client` — wraps the active `EmbeddingModel`
  - `rag_service` — `RAGService` bound to Qdrant
  - `config_manager` — runtime config file reader/writer
  - `settings` — the `Settings` object
- Resolves API keys from the DB at startup (`resolve_active_api_key`), falling back to env vars.
- Honors persisted runtime config **before** building clients:
  `embedding_provider`, `embedding_model`, `embedding_base_url` pick the
  embedding model; `default_llm_model` and `user_comm_model` name both LLM
  clients.
- Creates the embedding model via `create_embedding_model(settings)` (sentence_transformer default; TEI and OpenRouter also supported), then binds the RAG service to the model's collection: `set_collection(collection_name_for(model.model_name), model.dimensions)`.
- If runtime config contains a `tei_tunnel_url` and the active model is `TEIModel`, applies it (`set_base_url`).
- Ensures the Qdrant collection exists (`rag_service.ensure_collection()`) — failure here only logs "running in degraded mode", the app still boots.
- Starts the **bootstrap loop** (see [Configuration](configuration.md#4-bootstrap-flow)) — it **always runs** (idempotent): a persisted config file only means *some* config was saved, not that LLM models/keys are still current. Retries with backoff 5s doubling to a 60s cap, giving up after 12 attempts.
- On runtime config changes (`POST /config`) the client is rebuilt and the RAG service switches to the new model's collection before `ensure_collection()`; `refresh_llm` rebuilds both LLM clients from DB/env-resolved keys using the persisted `default_llm_model`/`user_comm_model` names too.

### 2.2 The two LLM clients

The engine holds **two** `LLMClient` instances, configurable independently:

| `app.state` key | Purpose | Model source |
|---|---|---|
| `llm_client` | Default LLM: description generation, query parsing | `LLM_MODEL` env / DB key |
| `comm_llm_client` | Conversational LLM: chat answers, tool calling, summaries, titles | `USER_COMM_MODEL` env / DB key / runtime config |

Rationale: the "communication" model used to answer users can be a different
(possibly more capable or cheaper) model than the internal parsing/generation
model. Both can be swapped at runtime via `POST /config`.

### 2.3 Routers

| Router | Path | Responsibility |
|---|---|---|
| `chat.py` | `POST /chat` | Full RAG chat pipeline, non-streaming or SSE streaming (see [Chat Flow](chat-flow.md)) |
| `description.py` | `POST /generate-description` | Product description generation with per-request model override |
| `embed.py` | `POST /embed-product` | Embed a product passage → Qdrant → webhook back to the API |
| `embed_text.py` | `POST /embed-text` | Embed free text and return the raw vector (admin/debug) |
| `summarize.py` | `POST /summarize` | Rolling conversation summary `S2 = f(S1, new messages)` |
| `title.py` | `POST /title` | Short conversation title from the first user message |
| `similar.py` | `POST /similar` | Metadata-aware similar-product search for an indexed product |
| `eval.py` | `POST /eval/queries`, `POST /eval/search` | Admin search-eval: LLM query generation + deterministic scored search |
| `config.py` | `POST /config` | Runtime overrides: embedding provider, LLM models, TEI tunnel URL, LLM refresh |

### 2.4 Services

| Service | Responsibility |
|---|---|
| `LLMClient` | All OpenAI-compatible chat completions; JSON-mode parsing; tool calling; streaming; retries; debug capture |
| `EmbeddingClient` | Thin facade over the active `EmbeddingModel` (`embed_query`, `embed_passage`, `embed_batch`) |
| `embedding/` package | Provider implementations behind the `EmbeddingModel` ABC — `sentence_transformer` (in-process, default), `tei` (live base-URL swap), `openrouter` (prefixed query/passage) — created via the `registry.create_embedding_model` factory |
| `embedding_dims` | `embedding_dims_for(model_name)` — vector dimensions per known embedding model, settings fallback for unmapped names |
| `RAGService` | Qdrant operations: collection bootstrap/validation, upserts, filtered/unfiltered vector search, **hybrid dense+sparse search (RRF fusion, `query_text`)** with model-aware score thresholds, `prefer_lang` dedupe, similar-product tiers, prompt context formatting |
| `key_service` | Read + decrypt active API keys from PostgreSQL (`llm_api_keys` joined with `llm_models`) |
| `ConfigManager` | JSON-file-backed runtime config (`/data/engine-config.json` in Docker, `./engine-config.json` local) |
| `lang_detect` | Script-based locale detection (ar/fa/en) and "respond in X" hints for the LLM |
| `search_tools` | The `search_products` tool schema + filter normalization shared by tool-calling and parse paths |
| `prompts` | All prompt templates (description, parse, chat assistant, summarize, title) |

## 3. Application Lifecycle

```
startup
  ├─ setup_logging(debug=settings.debug)
  ├─ create async db engine
  ├─ read persisted runtime config (ConfigManager)
  ├─ resolve llm/embedding keys (DB → env fallback)
  ├─ create embedding model — persisted embedding_provider/model/base_url override env defaults
  ├─ create LLMClient (default) + LLMClient (comm) — persisted default_llm_model/user_comm_model override env defaults
  ├─ create EmbeddingClient, RAGService, ConfigManager
  ├─ apply runtime tei_tunnel_url (if TEI provider + config)
  ├─ start bootstrap loop (always runs — idempotent config sync;
  │   backoff 5s → 60s cap, max 12 attempts)
  └─ ensure Qdrant collection (degraded mode on failure)

request flow (per request)
  ├─ ActivityLoggerMiddleware  captures request/response bodies, writes JSONL (outermost)
  ├─ EngineAuthMiddleware      X-API-Key guard (401 on mismatch; /health exempt)
  ├─ LogContextMiddleware      reads X-Request-Id / X-User-Id headers → contextvars
  └─ router handler            e.g. chat / embed / generate-description

shutdown
  ├─ cancel bootstrap loop
  ├─ rag_service.close()  (closes Qdrant client)
  └─ db_engine.dispose()
```

## 4. End-to-End Data Flows

### 4.1 Product embedding flow (`/embed-product`)

Triggered by the API whenever a product is saved/updated. The AI Engine is
stateless here: it embeds, writes to Qdrant, and reports back via webhook.

```
API                       AI Engine                     Qdrant
 │  POST /embed-product     │                            │
 │  {product_id, lang,      │                            │
 │   text, webhook_url,     │                            │
 │   payload, filters}      │                            │
 ├─────────────────────────►│ embed_passage(text)        │
 │                          ├───────────────────────────►│  vector
 │                          │  point_id = uuid5(product_id_lang)
 │                          │  upsert into active        │
 │                          │  collection (products-{slug})
 │                          │  (product_id, lang,        │
 │                          │   text, product_data,      │
 │                          │   filters)                 │
 │                          ├───────────────────────────►│
 │  POST webhook            │                            │
 │  {status: done|error,    │                            │
 │   model}                 │                            │
 │◄─────────────────────────┤                            │
 │  {"status": "ok"}        │                            │
 │◄─────────────────────────┤                            │
```

Key points:

- The upsert targets the **active model's collection** (`collection_name_for`
  → `products-{slug}`); switching models creates a fresh collection, never
  touches old ones.
- `point_id` is a **deterministic UUID5** of `"{product_id}_{lang}"`, so
  re-embedding the same product+language overwrites the same point (idempotent).
- The webhook is retried up to 3 attempts with exponential backoff (1s, 2s)
  and always includes `model` so the API can update the right per-model row.
- On embedding failure or Qdrant failure the webhook receives
  `{"status": "error", "error": "..."}` and the API records the row's
  `embedding_status`/`embedding_error`.
- If the embedding service is unavailable the request returns
  `{"status": "skipped"}` **without** calling the webhook.

See [Embedding](embedding.md) and [API Endpoints](api-endpoints.md#post-embed-product).

### 4.2 Chat flow (`/chat`)

The core RAG flow. A single user message goes through: locale detection →
conversation assembly → **conversation routing** (LLM intent classification →
greeting / search / general) → for search: **search resolution** (tool calling
first, LLM parse as fallback, possibly direct answer) → embedding → Qdrant
search (filtered + fallback) → LLM answer (streaming or one-shot). Fully
detailed in [Chat Flow](chat-flow.md).

```
user message
   │ detect_locale(query) → effective locale
   │ build messages (system + summary + history + query)
   ▼
conversation router: comm_llm.classify_intent(query, history)
   ├─ greeting → chat_plain reply (no search, products=[])
   ├─ general  → chat_plain answer (no search, products=[])
   └─ search ▼
_resolve_search
   ├─ try: comm_llm.chat_with_tools([search_products tool])
   │    ├─ tool call(s) → search spec(s)          (tool_used=true)
   │    └─ direct answer → return without search
   └─ fallback: llm.parse_search_query → rewritten query + filters
   ▼
_run_search_specs (one or more specs, merged, deduped by id)
   │ embed_query(query) → vector
   │ rag.search(vector, limit, filters, query_text=augmented query)
   │    ├─ hybrid: dense + sparse (text_bm25) prefetch, RRF fusion (k=60),
   │    │   wider pool (limit × 3, capped 100); dense-only without query_text
   │    ├─ score threshold (model-aware: 1024→0.3, 2560→0.25)
   │    ├─ filtered search (FieldCondition + MatchAny)
   │    └─ fallback to unfiltered if < limit (dedupe)
   │ dedupe by product_id, prefer_lang (detected locale) wins
   ▼
no products → localized "no results" hint
   ▼
format_products_for_prompt(products, locale)
   ▼
comm_llm.chat_with_context | chat_stream → answer
   ▼
ChatResponse (REST) | SSE frames (stream=true)
```

### 4.3 Description generation flow (`/generate-description`)

```
POST /generate-description
  │ body.model? ──no──► use default llm_client
  │                 └─yes─► resolve_model_info(db, model) → dedicated LLMClient (502 if unresolvable)
  ▼
body.prompt? ──no──► build product text (name/brand/category/images/attributes/price)
  │                 └─yes─► raw prompt passthrough
  ▼
LLM call (JSON mode, temp 0.7, retries)
  ▼
DescriptionResponse {descriptions: {en, ar, fa}, model, tokens_used, prompt}
```

### 4.4 Summary / title flows

`/summarize` — takes `messages` + optional `previous_summary`, runs
`SUMMARIZE_PROMPT` on the comm LLM (temp 0.2), returns the merged rolling
summary and token count. Empty message list short-circuits to the previous
summary (0 tokens).

`/title` — takes the first user `query`, runs `TITLE_PROMPT` (temp 0.2,
max_tokens 512), returns a 2–6 word title.

## 5. Design Invariants

1. **Stateless** — no product/chat DB; everything needed for a request arrives
   in the request body (product data, conversation history, summary).
2. **Filtered search with fallback** — exact filters never silently reduce
   recall: filtered results below `limit` are padded with an unfiltered search.
3. **Tool calling first, parsing as fallback** — when the comm model supports
   tools, `search_products` is called directly; the JSON parse path exists for
   models that do not.
4. **Deterministic point IDs** — `uuid5(product_id_lang)` makes embedding
   idempotent (upsert = replace).
5. **Per-model collections** — each embedding model owns its Qdrant collection
   (`products-{slug}`); switching models never touches old vectors and the
   API drives a re-embed (re-index) for the new model.
6. **No env proxies** — every outbound HTTP client is built with
   `trust_env=False` (`app/core/http_client.py`) so host proxy variables cannot
   break LLM/Qdrant/webhook calls.
7. **Bilingual payloads** — Qdrant payloads carry `product_data` for both `en`
   and `ar` so prompt context can be formatted per locale.
8. **Hybrid search is additive** — dense search without `query_text` is
   byte-identical to pre-hybrid behavior; sparse vectors are engine-side
   (BM25 tokenizer, no external encoder) with graceful dense-only fallback.
9. **Language-aware dedupe** — `prefer_lang` (detected locale) replaces a
   kept point when a same-product point in the target language ranks later.
10. **Runtime configurability** — models/providers can be swapped live via
   `POST /config` without restart; persisted in a JSON file.
