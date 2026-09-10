# Data Stores

Which data lives where — PostgreSQL, MongoDB, Redis, MinIO, RabbitMQ — and the rules that keep them consistent.

## PostgreSQL — source of truth for everything except chat state

Async SQLAlchemy 2.0 (`asyncpg`), engine pool size 10 / overflow 20, `pool_pre_ping`. Migrations via Alembic (38 version files). 42 mapped model classes; `app/models/__init__.py` exports 40 of them (`EmbedModel` is imported directly from its module).

### Core tables

| Table | Purpose | Notable columns |
|---|---|---|
| `users` | accounts | email, username, password_hash, phone, google_id, role (`user`/`admin`), api_key (unique per-user service key) |
| `refresh_tokens` | refresh rotation | user_id, token_hash, revoked, expires_at |
| `stores` | stores | owner_id → users, name, price_unit_code, status |
| `store_team_members` | store membership | store_id, user_id, role (`owner`/`manager`) |
| `product_types` / `categories` / `attributes` / `attribute_groups` / `attribute_options` / `brands` | catalog definition (EAV) | option: color_hex, color_family, images |
| `store_products` | the real product catalog | trilingual names, price, currency, status, `ai_description_en/ar` — embedding status **moved out** to `product_embeddings` (migration `c1f2e3d4a5b6`) |
| `product_embeddings` | per-model embedding status | `product_id` (FK CASCADE), `model_id` (FK `embed_models` SET NULL), `model_name` snapshot, `embedding_status` (`pending`/`generating`/`done`/`error`), `embedding_error`; `UNIQUE (product_id, model_name)` |
| `embed_models` | embedding-model catalog (migration `a3f9b7c1e2d5`) | model_name (unique), display_name, is_active |
| `user_favorites` | favorited products per user/store (migration `d996c5e6f593`) | user_id/store_id/product_id FKs CASCADE; `UNIQUE (user_id, store_id, product_id)` |
| `scraper_headers` | per-scraper raw request header block (Cookie + browser headers) (migration `a1b2c3d4e5f6`) | name (unique), header (raw multi-line block, NULL = unconfigured), status (`ready`/`error`), error_message |
| `product_variants` / `product_images` / `product_attribute_values` / `product_sizes` / `product_pieces` / `product_color_sets` / `variant_attribute_options` / `product_outfits` | product parts | variant: sku, price, quantity; image: view_type, sort_order |
| `products` | legacy generic products (list view) | kept for admin listing |
| `ai_description_versions` | AI description history | en/ar text, model, prompt, created_at (FK cascade on product) |
| `llm_models` / `llm_api_keys` / `llm_settings` | LLM runtime config | api key: `encrypted_key` (Fernet); settings: single row (id=1) with `default_llm_model_id`, `user_comm_model_id` |
| `prompt_templates` | versioned prompts | type, content, is_active (deactivate+insert history) |
| `system_settings` | key-value config | e.g. `product_ai_generation_cron`, `tei_tunnel_url`, `embedding_provider` |
| `activity_logs` | audit trail | action, resource_type, resource_id, user_id, body/response snapshots, created_at (60-day retention) |
| `search_history` | search results archive | user_id, query, response, source, latency_ms — no writer since the search consumer was removed |
| `scrape_products` | scraper pipeline state | |
| `store_types` / `countries` / `currencies` / `working_hours` | store setup data | |

### Consistency rules

- Store product mutations are transactional per request; image URL promotion (temp→store bucket) happens before commit.
- **`product_outfits` FK is `NO ACTION`** — delete those rows before `store_products` during DB resets.
- Embedding/description status is written by the API only (webhook receivers) — the AI Engine never opens this DB.

## MongoDB — chat conversation state

- Optional: `MONGO_URL` empty ⇒ chat routes 503. DB name env-scoped: `tea-dev` / `tea-production`.
- Collections: `conversations`, `messages` — full schema in [Chat System](chat-system.md).
- `messages.idempotencyKey` has a unique index (dedupe of retried sends).
- Motor async driver, `maxPoolSize=10`, `serverSelectionTimeoutMS=5000`.

## Redis — ephemeral state + response cache

| Key pattern | Purpose | TTL |
|---|---|---|
| `rl:{user_id}:{route}` | per-route rate limits | window |
| `login_attempts:{email}` | brute-force lockout counter | 15min×2ⁿ |
| `otp:{phone}` / `otp_send:{phone}` / `otp_verify:{phone}` | OTP code + attempt caps | 600s / shorter |
| `cron:product_ai_generation` | description-cron distributed lock (`NX EX`, owner-token release) | 600s |
| `cron:embedding_recovery` | embedding-recovery cron distributed lock (`NX EX`) | 600s |
| `cat:product_types:` / `cat:categories:` / `cat:attributes:` / `cat:attribute_groups:` / `cat:attribute_options:` / `cat:brands:` / `cat:image_view_types:` / `cat:store_types:` / `cat:countries:` / `cat:currencies:` | catalog reads (DTO dicts) | 1h |
| `sys:settings:` / `sys:setting:` / `sys:prompt:` | system settings + prompt templates | 5–10 min |
| `llm:setting` / `llm:config:` / `llm:models:` | LLM defaults, resolved engine config, model catalog | 2–5 min |
| `embed:active-model` / `embed:model:` | embedding model resolution | 60s |
| `product:info:{product_id}:{lang}` | full product info (UUID→names) | 10 min |
| `product:detail:{store_id}:{product_id}` | public product detail (modal payload) | 5 min |
| `store:stats:{signature}` | seller dashboard `{total, active}` counts | 60s |
| `product:random:{limit}` | public random product cards | 1h |
| `seval:metrics:{signature}` | search-eval MRR@10/Recall@10 | 5 min |

Cache mechanics: `cache_or_fetch` (fail-open, DB fallback, stampede `SET NX` lock for hot keys), whole-prefix invalidation via `PREFIX_BY_TABLE` (`SCAN`+`DEL` after writes), TTLs centralized in `CacheKeys`. User-scoped data (chats, search history, activity logs, seller product lists) is never cached. See [Caching](caching.md).

Also `get_redis` (pooled) helper. (`publish_json` exists in `core/redis.py` but has zero callers since the search fan-out was removed.)

## MinIO (S3-compatible) — files

4 buckets, created + set public-read at startup:

| Bucket | Contents | Promoted from temp via |
|---|---|---|
| `temp-files` | any `/files/upload` | — |
| `profile-photos` | avatars | `PATCH /users/me`, link flows |
| `store-photos` | store logos, product images | `PATCH /stores`, store-product create/update |
| `product-graph` | legacy generic-product files | — |

Public URLs are served through `minio_public_url` (e.g. `https://portfolio.example.invalid/...`); the storage account is irrelevant to clients — every response resolves relative paths to that prefix.

## RabbitMQ — job messaging

Two durable queues declared by the broker: `search_requests`, `web_scrape_jobs` (potential scraper orchestration). The former `search_results` queue and its consumer (`app/services/consumer.py`) were **removed entirely** — nothing consumes search results anymore.

## Cross-store invariants

- One user turn in chat reads: Mongo (conversation + history) → Postgres (prompts, product enrichment) → engine (inference) → Mongo (persist). Postgres is never written during a chat turn.
- Embedding: Postgres row → engine (no DB) → webhook → Postgres status. The webhook is the only writer of `embedding_status` besides the build-time `pending` set.
