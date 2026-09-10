# Architecture

## System Overview

```
                  ┌──────────────────────────────┐
                  │      Frontends (Web/App)      │
                  │  dashboard (seller/admin)     │
                  │  consumer app (chat shopper)  │
                  └──────────────┬───────────────┘
                                 │ HTTPS / WebSocket
                                 ▼
                  ┌──────────────────────────────┐
                  │   product-graph-api (8000)    │
                  │        FastAPI (async)        │
                  │                               │
                  │  routes → services → repos    │
                  └───┬──────┬───────┬───────┬────┘
                      │      │       │       │
        ┌─────────────┘      │       │       └──────────────┐
        ▼                    ▼       ▼                      ▼
  ┌──────────┐      ┌──────────┐ ┌────────┐         ┌────────────┐
  │PostgreSQL│      │ MongoDB   │ │ Redis  │         │   MinIO    │
  │  users,  │      │ chats &   │ │ rates, │         │ images,    │
  │ stores,  │      │ messages  │ │ locks, │         │ files      │
  │ products,│      │ (Atlas)   │ │ OTPs   │         │            │
  │ llm cfg  │      └──────────┘ │ pubsub │         └────────────┘
  └──────────┘                   └────────┘
                                 │  (RabbitMQ — 2 durable queues declared, no producers yet)
        ┌─────────────────────────┴──────────────────────────┐
        ▼                                                     ▼
  ┌─────────────────────────────────────────────────────────────┐
  │             product-graph-ai-engine (8001)                  │
  │  /chat (RAG + tool calls, SSE)  /summarize  /title          │
  │  /generate-description  /embed-product  /embed-text  /config │
  │      │                │                                   │
  │      ▼                ▼                                   │
  │  Qdrant (vectors)  LLM providers (opencode_zen/OpenRouter) │
  └─────────────────────────────────────────────────────────────┘
```

## Layered Request Path

Every request flows: **middleware stack → route handler → service → repository → storage**, then back up.

```
HTTP request
  └─ ActivityLoggerMiddleware     (captures body, redacts PII, logs to activity_logs)
      └─ RequestIDMiddleware      (X-Request-Id: accept or generate, bind to log context)
          └─ PrometheusMiddleware (counters + latency histograms per endpoint)
              └─ SecurityHeadersMiddleware
                  └─ RestrictDocsMiddleware   (403 on /docs when debug=False)
                      └─ ShutdownCheckMiddleware (503 while draining)
                          └─ CORS
                              └─ router (/api/v1/...)
                                  └─ dependencies (auth, RateLimit, DB sessions)
                                      └─ service layer (business logic)
                                          └─ repositories / AI client / storage
```

Middleware order in `app/main.py`: `ActivityLogger → RequestID → Prometheus → SecurityHeaders → RestrictDocs → ShutdownCheck → CORS`.

## Application Lifecycle (`app/main.py`)

### Startup (`_startup`)
1. `setup_logging()` — Loguru JSON sink + stdlib interception.
2. **Redis** — `from_url(settings.redis_url)`, stored on `app.state.redis`.
3. **PostgreSQL** — async engine (pool 10, max_overflow 20, `pool_pre_ping`), `app.state.session_factory`.
4. **RabbitMQ** — `init_broker()`; failure is caught → `app.state.broker = None`, app runs **degraded** (broker-dependent features only). Declares 2 durable queues: `search_requests`, `web_scrape_jobs` (no producers/consumers yet — scaffolding).
5. **AI Engine client** — `AIEngineClient()` on `app.state.ai_client` (lazy httpx, `X-API-Key` header, 300s timeout).
6. **MongoDB** — optional (`MONGO_URL` empty ⇒ chat disabled). `ensure_indexes()` creates the conversations/messages indexes.
7. **MinIO** — 4 `StorageService` instances (`storage`, `temp_storage`, `profile_storage`, `store_storage`), one per bucket; `ensure_bucket()` + public-read policy; failure ⇒ degraded.
8. **Background tasks** (asyncio.create_task) — exactly 3:
   - `run_product_ai_cron` — AI description generation, 300s cycle.
   - `run_embedding_recovery_cron` — embedding retry, 60s cycle.
   - `run_activity_log_cleanup` — purges `activity_logs` older than 60 days, 24h cycle.
   - Each task gets a done-callback that logs crashes.

### Shutdown (`_shutdown`)
1. Set shutdown event → 2s drain (in-flight requests finish; ShutdownCheckMiddleware returns 503 meanwhile).
2. Cancel the 3 background tasks: `product_ai_cron` → `embedding_cron` → `activity_cleanup`.
3. `drain_activity_tasks()` — flush any pending activity-log writes.
4. `ws_manager.close()` — close every tracked WebSocket (code 1001) and clear the registry.
5. AI client close → Mongo close → broker close → Redis close → SQLAlchemy engine dispose.

## The Three Persistent Stores

| Store | Owner | Purpose | Notes |
|---|---|---|---|
| PostgreSQL | catalog/auth | users, stores, products, attributes, variants, LLM config, prompt templates, system settings, activity logs, AI description versions | SQLAlchemy 2.0 async, Alembic migrations |
| MongoDB (Atlas) | chat | conversations, messages | motor/async; `MONGO_URL` empty ⇒ chat 503s |
| MinIO | files | product images, temp uploads, profile/store photos | 4 buckets, public-read |

Plus: **Redis** (rate limits, login lockout, OTPs, cron locks, Pub/Sub, **response cache**) and **RabbitMQ** (declared queues — currently no active producers).

## Redis Caching Layer

Hot read paths are cached in Redis through a **key-registry-driven, write-invalidation** design (`app/core/cache.py`):

- **`CacheKeys`** — single registry pairing every key prefix with its TTL (`CacheKey(prefix, ttl)`), e.g. catalog `cat:*` 1h, `product:info:` 10 min, `product:detail:` 5 min, `store:stats:` 60s, `product:random:` 1h, `llm:config:` 2 min, `seval:metrics:` 5 min.
- **Repository-layer reads** — repositories call `cache_or_fetch(redis, key, ttl, fetch)` and return **JSON-safe DTO dicts** (never ORM rows); the DB is hit only on a miss. Everything is **fail-open**: Redis errors log and fall back to the database.
- **Whole-prefix invalidation** — every table maps to the read prefixes it feeds (`PREFIX_BY_TABLE`); writes call `invalidate_tables(redis, {tables})` after commit, which `SCAN`+`DEL`s all affected keys (a product write clears detail, info, stats, and random cards in one shot).
- **Stampede guard** — hot single-value keys use a short `SET NX EX 2` lock so concurrent callers wait for the value instead of hammering the DB.
- **Scope** — catalog, product info/detail, store stats, public random cards, LLM/embedding config, system settings, prompt templates, search-eval metrics. User-scoped data (chats, messages, search history, activity logs, seller product lists) is never cached.
- **Lightweight lists** — product list endpoints return `StoreProductListItem` from flat join queries (no eager-load chains); `random` is Redis-cached, seller/store lists are DB-only.

Full contract, TTL table, and the table→prefix invalidation map: [Caching](caching.md).

## Background Tasks Summary

| Task | Cycle | Work |
|---|---|---|
| `product_ai_cron` | 300s | Generate missing AI descriptions via AI Engine `/generate-description`, in batches of 10, guarded by a Redis lock |
| `embedding_recovery_cron` | 60s | Find stale `product_embeddings` rows for the **active model** (`pending`/`generating`, `updated_at < now−2min`), rebuild embed text, submit to AI Engine `/embed-product` with webhook callback |
| `activity_log_cleanup` | 24h | Delete `activity_logs` older than 60 days |

Detailed mechanics in [Background Tasks](background-tasks.md).

## AI Engine Interaction Model

The API is a **stateless HTTP client** of the AI Engine (`app/ai/client.py`). Two integration patterns exist:

1. **Synchronous request/response** — `generate_description`, `chat`, `chat_conversational`, `summarize`, `title`, `embed_text`, `eval_generate_queries` (`/eval/queries`), `eval_search` (`/eval/search`), `health`, `update_config`. The API waits for the full response.
2. **Streaming relay** — `chat_conversational_stream` consumes the engine's SSE lines and relays them frame-by-frame over the WebSocket (`/ws/chat/{id}`).
3. **Fire-and-forget with webhook callback** — `embed_product`: the API submits text + a `webhook_url`; the engine embeds, upserts to the per-model Qdrant collection, then POSTs `{status: "done"|"error", model}` back to `/api/v1/webhook/embedding-result`, which upserts the row in `product_embeddings` for that model.

**Context propagation**: every engine call forwards `X-Request-Id` + `X-User-Id` (from `_forward_headers`) so the engine's logs line up with the API's.

**Config push**: the API pushes runtime config to the engine via `update_config` (`/config`) — LLM model+key+base_url, TEI tunnel URL, embedding provider — whenever an admin changes `llm_settings`, `system_settings`, or hits the bootstrap webhook.

Full contract in [AI Engine Integration](ai-engine-integration.md).

## Chat Data Flow (end-to-end)

Two entry points — authenticated (JWT/cookie) and **anonymous** (public):

```
Authenticated client          API (FastAPI)                   AI Engine
   │  WS /ws/chat/{id}            │                               │
   │──send_message───────────────▶│ claim_turn (atomic slot)      │
   │                              │  persist user msg (Mongo)     │
   │                              │  detect locale                │
   │                              │  build history (window+budget)│
   │                              │──chat_conversational_stream──▶│ (RAG: parse query →
   │                              │                               │  Qdrant hybrid search →
   │  ◀─assistant_start───────────│◀─SSE frames───────────────────│  LLM with product
   │  ◀─product_cards (enriched   │                               │  cards; intent in
   │     w/ trilingual names,     │                               │  search_context)
   │     normalized URLs)─────────│                               │
   │  ◀─text_chunk──────...───────│                               │
   │  ◀─assistant_end─────────────│                               │
   │                              │ persist assistant msg +       │
   │                              │   product snapshots (Mongo)   │
   │  ◀─message_saved─────────────│ maybe_compact (summary)       │
   │                              │ maybe_title (first message)   │
   │──similar_request────────────▶│ /similar (engine) → saved     │
   │  ◀─message_saved─────────────│   assistant reply w/ snapshots│

Guest (no account)
   │  POST /chat/anonymous-session → {anon token (10 min, WS-only), conversation}
   │  WS /ws/chat/{id} with anon token in subprotocol / cookie
   │  (same frames as above; no title generation; need_title=false)
```

Details: [Chat System](chat-system.md).

## Embedding Data Flow (end-to-end)

```
New/updated product (or model switched / re-index requested)
   │
   ▼
embedding recovery cron (60s)  ── or ──  backfill script  ── or ── reindex_active_model
   │  ensure pending row (product_id × active model) in product_embeddings
   │  fetch stale (pending/generating, updated_at < now-2min)
   ▼
build_embed_data(product_id, db)
   │  1. get_product_info(db, pid, "en"|"ar")   (UUID→names resolution)
   │  2. _format_embed_text: ONE MONOLINGUAL passage per language (en, ar)
   │     (name/category/brand/attributes/description + localized enrichment)
   │  3. product_data: minified bilingual dict + store_id + image_url
   │  4. filters: _color, _material, _category, _brand, _gender, _color_family
   │     (from attributes + variants + color families, normalized, deduped)
   ▼
AIEngineClient.embed_product(product_id, "en", embed_text_en, webhook_url, payload, filters)
AIEngineClient.embed_product(product_id, "ar", embed_text_ar, webhook_url, payload, filters)
   ▼
AI Engine: embed → Qdrant upsert into "products-<slug>" collection
(dense + BM25 sparse vectors per language point) → webhook back per language
   ▼
POST /api/v1/webhook/embedding-result {status: done|error, model}
   ▼
product_embeddings.status = done | error (+embedding_error)   [row for (product_id, model)]
```

Details: [Embedding Pipeline](embedding-pipeline.md).

## Security Model

- **Users**: JWT access (15 min, HS256, `sub`, `role`) + refresh (30 days, `jti`, hashed at rest). Refresh reuse detection revokes **all** user sessions.
- **Transport**: httpOnly `access_token`/`refresh_token` cookies (SameSite=Lax) for browser clients + `Authorization: Bearer` for native clients; cookie-authenticated requests require the `X-Requested-With: XMLHttpRequest` header (missing → `401 csrf_header_missing`).
- **Services**: `X-API-Key` header (`settings.api_key`) for service-to-service calls, plus per-user `User.api_key`.
- **OTP**: 6-digit, stored in Redis with TTL, per-phone send/verify caps, exponential login lockout (5 attempts → 15min × 2^n).
- **Google**: ID-token verification against configured web/android/iOS client IDs; authorization-code exchange restricted to an allowlist of redirect URIs and protected by a one-time nonce (`POST /auth/google/nonce`).
- **Anonymous chat**: 10-minute `type="anon"` JWTs — accepted only by the WebSocket handshake, rejected by every authenticated REST dependency; conversations are created with `need_title=false` and can never touch user data.
- **RBAC**: `user.role == "admin"` gates `/admin/*`; store scoping uses owner/member roles (`owner`/`manager`).
- **LLM keys**: Fernet-encrypted at rest (`LLM_ENCRYPTION_KEY`), masked in responses, never returned in full.

Details: [Authentication](authentication.md).

## Error Handling

- Typed domain exceptions in `app/core/exceptions.py` (`AppError` base → `NotFoundError`, `AuthenticationError`, `AuthorizationError`, `ConflictError`, `ValidationError`, `ServiceUnavailableError`). Routes never raise raw `HTTPException`.
- Global handlers map them to the unified envelope with a `translation_key` for frontend i18n (see [Error Codes](error-codes.md)).
- `RateLimit` DI raises 429 with `X-RateLimit-Remaining` header.

## Observability

- **Logs**: Loguru JSON; request ID, user ID, source context vars; PII redaction; engine-side logging mirrors the same fields. See [Logging](logging.md).
- **Metrics**: `/metrics` (Prometheus, dev-only) — request count/latency/error count per endpoint+method+status.
- **`/health`** returns `{status, service, environment, git_sha, uptime_seconds, python_version}`; `git_sha` is baked in at Docker build time (`app/core/config.py`, default `dev`).
- **Activity log**: every HTTP request writes an `activity_logs` row (action inferred from method or set explicitly by the route) with redacted request/response bodies on errors. Background tasks log `CRON_RUN` entries too.

## Module Map (what lives where)

| Layer | Location | Responsibility |
|---|---|---|
| Routes | `app/api/v1/*.py`, `app/api/v1/admin/*.py` | HTTP/WS interface, DI wiring, activity metadata |
| Services | `app/services/*.py` | Business logic, raises typed exceptions |
| Repositories | `app/repositories/*.py` | Data access (Postgres repos + Mongo repos) |
| Core | `app/core/*.py` | Config, auth, DI, middleware, brokers, metrics |
| AI client | `app/ai/client.py` | Single HTTP client to the AI Engine |
| Schemas | `app/schemas/*.py` | Pydantic v2 contracts (request/response) |
| Models | `app/models/*.py` | SQLAlchemy ORM (42 mapped classes across 38 modules) |
| DB | `app/db/mongo.py` | Mongo connection wrapper |
| Scrapers | `app/scrapers/*.py` | Zara pipeline |

## Project Structure

```
product-graph-api/
├── app/
│   ├── ai/                # AIEngineClient — HTTP client to product-graph-ai-engine
│   ├── api/v1/            # Route handlers (auth, users, products, stores, chats, files, admin, ws)
│   │   └── admin/         # Admin-only routers (llm, prompt_templates, system_settings, ai_engine, cron, conversations)
│   ├── core/              # Config, auth primitives, DI, exceptions, error codes, middleware, broker, redis, metrics
│   ├── db/                # MongoDB (Atlas) connection for chat history
│   ├── models/            # SQLAlchemy ORM models (42 mapped classes)
│   ├── repositories/      # Data-access layer (BaseRepository[T] + Mongo repos)
│   ├── schemas/           # Pydantic v2 request/response schemas
│   ├── scrapers/          # Zara scraper pipeline
│   └── services/          # Business logic: auth, user, product, store, chat, cron, embedding, storage, sms, ws, llm config, search-eval
├── scripts/               # Seeds, cron runner, embedding backfill, cleanup, scrapers
├── tests/                 # 862 tests, ~75% coverage
├── alembic/versions/      # DB migrations
├── docs/                  # This documentation set
├── docker-compose.yml     # Profiles: minimal (postgres, redis, rabbitmq, minio), full (+ api)
├── pyproject.toml         # Dependencies + tool configs
└── Makefile               # dev, test, lint, typecheck, format, migrate, seed
```
