# API Reference

Base path: `/api/v1`. Interactive docs: `/docs` (Swagger), `/redoc`. All JSON. Every response is either a typed payload or the unified error envelope (see [Errors](#errors)).

```
GET /api/v1/health          GET /api/v1/ready      GET /api/v1/metrics (Prometheus, dev-only, rate limited 10/min)
```

`GET /health` (no auth) returns `{status, service, environment, git_sha, uptime_seconds, python_version}` — `git_sha` is baked in at Docker build time (`dev` when running locally). `GET /ready` checks Postgres/Redis/RabbitMQ/AI Engine and reports per-dependency status (`ok`/`error`, overall `ok` or `degraded`).

## Common Conventions

- **Auth**: `Authorization: Bearer <access_token>` (JWT) for user endpoints; `X-API-Key: <key>` for service-to-service (the AI Engine uses the shared secret) **or** a per-user API key (`users.api_key`, unique + indexed) which authenticates the request as that user. Browser clients can also authenticate via **httpOnly cookies** (`access_token` / `refresh_token` set by every auth flow); cookie-authenticated requests must send `X-Requested-With: XMLHttpRequest` (missing → `401 csrf_header_missing`).
- **Rate limiting**: per-user + per-route, Redis-backed (`RateLimit` DI). Exceeded → `429 RATE_LIMITED` with `X-RateLimit-Remaining: 0`. See [the table](#rate-limits).
- **Tracing**: every response has `X-Request-ID`; the AI Engine receives it as `X-Request-Id` so one user turn is traceable across both services.
- **Pagination**: `?skip=&limit=` (limit `1–100`, default 20) on list endpoints.
- **Response envelope**: error handlers always return `{success: false, error: {code, message, details, translation_key, request_id}}`. Success routes return typed models directly.

---

## 1. Authentication — `/auth`

### Register — `POST /auth/register` (5 req / 300s)

```json
{"email": "user@example.com", "username": "johndoe", "password": "StrongPass1!", "full_name": "John Doe"}
```

`ConflictError` if email/username exists (`EMAIL_OR_USERNAME_TAKEN`). Returns the token pair.

### Login — `POST /auth/login` (10 req / 60s)

```json
{"email": "user@example.com", "password": "..."}
```

**Lockout flow** (`check_login_rate_limit` in `rate_limit.py`): failed attempts are counted in Redis (`login_attempts:{email}`); after **5 consecutive failures** the account locks for `15 min × 2^(n−1)` (exponential). Correct password resets the counter. Locked → `429 ACCOUNT_LOCKED` (with retry-after). Successful login also refreshes the lockout window away.

### Refresh — `POST /auth/refresh` (5 req / 60s)

```json
{"refresh_token": "eyJ..."}
```

Body optional: when absent the token is read from the **`refresh_token` cookie** (browser flow). **Rotation protocol**: the presented token's `jti` must exist and be unrevoked; it is revoked on use and a fresh pair is minted. A **reuse** (already-revoked jti) revokes *all* of the user's refresh tokens (`REFRESH_TOKEN_REUSE`). Tokens are stored **hashed** in `refresh_tokens`.

### Logout — `POST /auth/logout` (10 req / 60s) → `204`

Body optional (`{"refresh_token": "..."}`), falls back to the cookie. Revokes the refresh token and clears both auth cookies.

### OTP — `POST /auth/send-otp`, `POST /auth/verify-otp` (10 / 10 per 60s)

`send-otp` `{"phone": "+965501234567"}` → 6-digit code via Twilio; dev mode (`twilio_bypass`) logs it instead and accepts magic code `123456`. Per-phone send cap (`otp_max_send_per_phone`). `verify-otp` `{"phone": "...", "code": "123456"}` — capped attempts (`otp_max_verify_attempts`); **auto-creates the user by phone** on success and logs them in.

### Google — `POST /auth/google`, `POST /auth/google/code`, `POST /auth/google/nonce` (10 req / 60s each)

`google` takes `{"id_token": "...", "client_type": "ios"|"android"|"web"}` — the ID token must be signed for one of the configured OAuth client ids (`auth_google_client_ids`). Existing `google_id` → login; same email → link accounts; unknown → auto-register. `google/code` exchanges an authorization code for a session (`{code, redirect_uri, state}`; redirect URI must be on the `ALLOWED_REDIRECT_URIS` allowlist, and the one-time `state` is consumed server-side); the client first fetches `POST /auth/google/nonce` for a one-time nonce that the callback must echo back (OAuth CSRF protection).

**Token pair** (all auth flows — also set as httpOnly cookies):

```json
{"access_token": "eyJ...", "refresh_token": "eyJ...", "token_type": "bearer"}
```

Access token: ~15 min, claims `sub`, `email`, `role`, `exp`. Refresh: ~30 days, includes `jti` for rotation tracking. Anon chat tokens: ~10 min, `type: "anon"`, WS-only.

---

## 2. Users — `/users`

| Endpoint | Rate | Notes |
|---|---|---|
| `GET /users/me` | 60/min | current profile |
| `PATCH /users/me` | 30/min | name, username, avatar_url (avatar URL promoted temp→profile bucket via `move_url_to_bucket`) |
| `GET /users/me/profile` | 60/min | full profile incl. `role` |
| `PATCH /users/me/profile` | 30/min | locale, notifications, etc. |
| `POST /users/me/link/phone/send-otp` | 10/min | OTP to the phone being linked |
| `POST /users/me/link/phone/verify` | 10/min | verify code → `phone` bound to current user |
| `POST /users/me/link/google` | 10/min | authorization-code exchange `{code, redirect_uri, state}` — redirect URI allowlisted (`INVALID_REDIRECT_URI`), one-time `state` consumed; binds `google_id` |
| `POST /users/me/link/google/mobile` | 10/min | ID-token link for native apps: `{"id_token": "..."}` → binds `google_id` |
| `GET /users/{user_id}` | 30/min | **admin** only |

### Favorites — `/users/me/favorites`

| Endpoint | Rate | Notes |
|---|---|---|
| `GET /users/me/favorites[?skip=&limit=]` | 60/min | paginated favorites with product snapshot (up to 100) |
| `PUT /users/me/favorites/{store_id}/{product_id}` | 60/min | `204` add favorite |
| `DELETE /users/me/favorites/{store_id}/{product_id}` | 60/min | `204` remove favorite |

---

## 3. Files — `/files` (MinIO)

| Endpoint | Rate |
|---|---|
| `POST /upload` | 30/min |
| `POST /upload/profile` | 30/min |
| `POST /upload/store` | 30/min |
| `GET /{file_name:path}` | 60/min |
| `DELETE /{file_name:path}` | 30/min |

**Validation** (same for all three): extension allowlist (`jpg jpeg png gif webp svg pdf csv json`), MIME-type allowlist, **magic-byte sniffing** (rejects renamed executables), sanitized filename (no `..`, no leading `/`, ≤ 500 chars, UUID prefix). Uploads land in `temp-files` unless a store/profile endpoint is used (`store-photos` / `profile-photos`). `GET` returns `307` to a short-lived presigned URL (`minio_public_url`).

---

## 4. Stores — `/stores`

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /stores` | user | same as `/my` — stores where the caller is owner **or** member (30/min) |
| `POST /stores` | user | max **3 active** stores per owner (`STORE_LIMIT_REACHED`); owner auto-added as member role `owner` |
| `GET /stores/my` | user | stores where caller is owner **or** member |
| `GET /stores/{id}` | user | detail + `members[]` + `my_role` |
| `PATCH /stores/{id}` | owner | `price_unit_code` **locked** once the store has products |
| `DELETE /stores/{id}` | owner | |
| `GET /stores/{id}/members` | owner/manager | |
| `POST /stores/{id}/members` | owner | `{"phone" \| "email": "...", "role": "manager"}` — resolves the user by phone or email; roles `owner`/`manager` |
| `DELETE /stores/{id}/members/{member_id}` | owner | cannot remove self or the last owner |
| `GET /stores/my/products/stats` | user | `{"total": n, "active": n}` — two `COUNT` queries, **no product rows loaded** (seller-dashboard fast path); **Redis-cached 60s** per store-id signature (`store:stats:`) |
| `GET /stores/my/products[?skip=&limit=&q=&store_id=]` | user | paginated **light card list** (`StoreProductListItem[]`, 16 fields) across the caller's stores; `q` = name search (EN/AR `ILIKE`), `store_id` filters to one store. Flat join query — **no variants/images/descriptions payload** |
| `GET /stores/countries?locale=en` / `GET /stores/currencies?locale=en` | public | |

**Data flow**: `POST /stores` → `store_service.create_store` → row + `StoreMember(owner)` row in one session. `my_role` is computed per request from `StoreMember`.

---

## 5. Product Definition (public read) — `/products/...`

Read-only catalog structure, **no auth required** (product-type/option lookups power the seller builder and attribute resolution):

| Endpoint | Notes |
|---|---|
| `GET /products/types` | all 30 product types (`athletic_sneakers`, `bags`, `dresses`, …) |
| `GET /products/types/{id}` | type + linked attribute groups |
| `GET /products/categories[?product_type_id=]` | category tree; each node carries `product_type_id` (type auto-derived from category) |
| `GET /products/attribute-groups[?product_type_id=]` | groups that have attributes linked to the type |
| `GET /products/attributes?product_type_id=&group_id=` | attributes with their options |
| `GET /products/attributes/{id}/options` | full option set (`name_*`, `color_hex`, `color_family`, images) |
| `GET /products/image-view-types?product_type_id=` | e.g. main/front/back/detail/fabric |
| `GET /products/brands` | all brands (seeded from Wikipedia SVGs) |
| `POST /products/generate-variant-combinations?product_type_id=` | cartesian product of the selected variant-defining options — the seller UI's variant pre-builder. Body: `{"selected_option_ids": {"<attribute_id>": ["<option_id>", ...]}}`; returns `[{options, price, sku, ...}]` records |

### Generic products CRUD — `/products`

The legacy/searchable `products` table (distinct from store catalog above):

| Endpoint | Auth | Rate |
|---|---|---|
| `POST /products/` | **admin** | 30/min |
| `GET /products/[?skip=&limit=&filters]` | public | 60/min |
| `GET /products/{product_id}` | public | 60/min |
| `PATCH /products/{product_id}` | **admin** | 30/min |
| `DELETE /products/{product_id}` | **admin** → `204` | 20/min |

`GET` list supports filter/sort/pagination params (`ProductFilterParams`).

---

## 6. Store Products — `/stores/{store_id}/products`

**Authorization**: all routes require store ownership except one — `GET /stores/{store_id}/products/{product_id}` is **public** (rate limited 120/min) so the chat product-view dialog works for any user; the owner check (`_verify_store_owner`) applies everywhere else.

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /stores/{store_id}/products[?skip=&limit=&q=]` | owner | paginated **light card list** (`StoreProductListItem[]`, 16 fields); `q` = name search (EN/AR `ILIKE`). Flat join query, no eager-load chains |
| `POST /stores/{store_id}/products` | owner | create (see example below) |
| `GET /stores/{store_id}/products/{product_id}` | **public** | full detail with variants, images, attribute values, brand, category, AI description versions; **Redis-cached 5 min** (`product:detail:`) |
| `PUT /stores/{store_id}/products/{product_id}` | update |
| `DELETE /stores/{store_id}/products/{product_id}` | cascade variants/images/attr values |
| `POST .../products/{product_id}/generate-descriptions` | manual AI description generation (see §6.1) |
| `POST .../products/{product_id}/images` | attach image (URL, view type, alt text, optional variant) |
| `PUT .../products/images/{image_id}` / `DELETE .../products/images/{image_id}` | |
| `PUT .../products/images/reorder` | body is a raw JSON array of image ids `["id1", "id2", ...]` — sort order reassigned in list order |
| `GET .../products/{product_id}/variants` | owner — variant rows for one product |
| `PATCH .../products/{product_id}/variants/{variant_id}` | price/quantity/active/options |
| `DELETE .../products/{product_id}/variants/{variant_id}` | |

Create body (abridged):

```json
{
  "product_type_id": "pt-clothing",
  "category_id": "cat-shirts",
  "status": "active",
  "name_en": "Cotton T-Shirt", "name_ar": "تي شيرت قطني",
  "brand_id": "...", "price": 49.99, "currency": "KWD",
  "attribute_values": [{"attribute_id": "attr-1", "value": "opt-red"}],
  "variants": [{"sku": "TS-RED-M", "price": 49.99, "quantity": 10, "is_active": true, "attribute_option_ids": ["opt-red", "opt-m"]}],
  "images": [{"image_url": "https://...", "view_type_id": "vt-main", "sort_order": 0, "alt_text_en": "..."}]
}
```

**Data flow on create/update** (`_trigger_embed`):

```
save product row → commit
      │ ensure pending row in product_embeddings (product_id, active model)  (BackgroundTasks)
      ▼
build_embed_data(product_id):  (embed_text_en, embed_text_ar, product_data, filters)   ← see embedding-pipeline.md
       ▼
AIEngineClient.embed_product(product_id, "en"|"ar", text, webhook_url, payload, filters)   // fire-and-forget, one call per language
       │  (AI Engine embeds → Qdrant upsert "products-<slug>" collection → POST webhook)
       ▼
POST /api/v1/webhook/embedding-result  →  product_embeddings.status = "done" | "error"
```

Image URLs from `temp-files` are promoted to `store-photos` inline (temp-bucket moves are transactionally safe: move first, then commit).

### 6.1 `generate-descriptions` — manual AI description

`POST .../products/{product_id}/generate-descriptions` — synchronous: builds `get_product_info(en)` → minified JSON → `pre_prompt + data + ending_prompt` → `AIEngineClient.generate_description(product, prompt, model=default)` → saves an `AIDescriptionVersion` row (en/ar text, model, prompt) → updates the product's `ai_description_en/ar`. Engine failure → `502/503 DESCRIPTION_GENERATION_FAILED`.

---

## 7. Product Info — `GET /product-info/{product_id}/{lang}`

Public, **rate limited 120/min**, no auth. Returns the product with **every UUID resolved to its display name** in the requested locale (`en`/`ar`/`fa`): brand name, category chain (walked via `parent_id`), attribute option names (including JSON values like composition `[{material, percentage}]`), image view types, variant option names, color sets. This is the payload used by AI prompts and the embedding pipeline (via `minify_product_info`). **Redis-cached 10 min** per `product_id`+lang (`product:info:`).

### Public random products — `GET /public/products/random[?limit=]`

Public, **rate limited 60/min**, no auth. `limit` 1–20 (default 20). Returns a random sample of store products as **light cards** (`StoreProductListItem[]`) — powers the home-page product sliders for guests. **Redis-cached 1h** under `product:random:{limit}` (public, fixed-limit → cacheable); invalidated on product/image writes, fail-open to the DB.

---

## 8. Chat — REST + WebSocket

Mongo-backed; every conversation state lives in Mongo (see [chat-system.md](chat-system.md)). **All chat routes 503 with `AI_ENGINE_ERROR` if `MONGO_URL` is unset.**

### REST

| Endpoint | Notes |
|---|---|
| `POST /chats` | body `{"locale": "en", "app_version": "", "create_new": false, "need_title": true}` — reuses the user's active conversation (or creates one). Returns **the conversation object only** (`201`). `need_title=false` skips LLM title generation (used by anonymous sessions) |
| `GET /chats[?skip=&limit=]` | conversation list (title, status, userMessageCount, locale, timestamps) |
| `GET /chats/{id}/messages[?cursor=&limit=]` | cursor-paginated messages |
| `POST /chats/{id}/messages` | `{"content": "...", "idempotency_key": ""}` (content ≤ 4000 chars, optional idempotency key ≤ 128 chars) — full turn, returns `201 ChatTurnResponse = {conversation, user_message, assistant_message\|null}`. Non-200 from engine → 503 `CHAT_ENGINE_FAILED` |
| `POST /chats/{id}/messages/{message_id}/feedback` | `{"rating": 1-5}` only (no comment field) — returns `{id, rating}` |
| `DELETE /chats/{id}` | close/delete conversation |
| `POST /chat/anonymous-session` | **public, no auth** (rate limited 20/60s) — `{"locale", "app_version"}` → `201 {token, conversation}`. Mints a 10-min **anon** JWT (WebSocket-only; no Postgres user) + a Mongo conversation with `need_title=false` |

### WebSocket — `GET /ws/chat/{conversation_id}`

**Handshake**: the JWT is taken from the first `Sec-WebSocket-Protocol` value (raw token string — echoed back as the accepted subprotocol), else the `access_token` **cookie**, `?token=`, or `Authorization: Bearer`. Sets `request_id = ws_{user_id}` so the engine trace carries the socket identity. Anonymous sockets authenticate with an anon token from `/chat/anonymous-session`. Auth failure → close code `4001`.

**Inbound** (≤ 10 KB, `type` field):

```json
{"type": "send_message", "content": "...", "idempotency_key": "client-unique-id", "include_saved_message": true}
{"type": "similar_request", "product_id": "...", "product_name": "", "include_saved_message": true}
{"type": "ping"}
```

`idempotency_key` is honored as the Mongo **idempotency key** (unique index) — retried sends are deduplicated. `include_saved_message=true` makes the final `message_saved` frame carry the full message docs. `similar_request` asks the engine for similar products; the reply is persisted as an assistant message and confirmed with a `message_saved` frame. Unknown types get `unsupported_frame`.

**Outbound frame sequence** per turn (no frame is emitted on connect):

| Frame | Payload | Source |
|---|---|---|
| `assistant_start` | `{search_context}` | relayed from engine (SSE `assistant_start`) — includes `intent` (greeting/search/general) for UI theming |
| `product_cards` | `{products: [...]}` | relayed, **after enrichment**: trilingual names, brand, normalized `image_url`, `buy_url`, store_id |
| `text_chunk` | `{delta}` | relayed verbatim |
| `assistant_end` | — | relayed verbatim |
| `message_saved` | `{conversation_id, message_id[, message][, user_message]}` | **API-generated** after persistence — client's durability signal; full docs included only when the inbound frame set `include_saved_message`; also confirms `similar_request` replies |
| `error` | `{code, message?}` | `conversation_not_found`, `conversation_closed`, `chat_limit_reached`, `chat_failed`, plus protocol errors (`message_too_large`, `invalid_frame`, `unsupported_frame`, `empty_content`, `missing_product_id`, `product_not_found`, `chat_not_available`) |

Turns are processed sequentially per socket (the handler relays a stream to completion before reading the next frame). On engine failure mid-stream the assistant message is persisted as `failed` and reported via an `error` frame before `message_saved`.

---

## 9. Admin — `/admin/*` (role `admin` only)

| Group | Endpoints |
|---|---|
| **LLM models** | `GET /admin/llm/models` — models with their API keys (masked) |
| **LLM API keys** | `POST /admin/llm/api-keys` — create-only, `201`, `{"model_id", "name"?, "api_key"}` (Fernet-encrypted, never returned in plaintext); `PATCH /admin/llm/api-keys/{key_id}/toggle`; `DELETE /admin/llm/api-keys/{key_id}` → `204` |
| **Embedding models** | `GET /admin/embed-models` — active embedding-model catalog |
| **Scraper headers** | `GET /admin/scraper-headers`, `GET /admin/scraper-headers/{name}`, `PUT /admin/scraper-headers/{name}` (raw header block; validated by the Zara header parser — must contain a Cookie header, else `422 scraper_header_invalid`; resets status to `ready`), `DELETE /admin/scraper-headers/{name}` (clears the stored block) |
| **LLM settings** | `GET/PUT /admin/llm/settings` — `default_llm_model_id` + `user_comm_model_id`; PUT pushes resolved model config to the engine via `/config` |
| **Prompt templates** | `GET /admin/llm/prompt-templates` (active content per type), `PUT` (deactivate-old + insert-new) |
| **System settings** | `GET/PUT /admin/system-settings` — key-value; AI-related keys (`tei_tunnel_url`, `embedding_provider`) also pushed to engine |
| **Cron reports** | `GET /admin/cron/summary`, `GET /admin/cron/products` (status filter pending/generated, searchable), `GET /admin/cron/products/{id}` (prompt, en/ar descriptions, model, timestamp) |
| **Embedding reports** | `GET /admin/cron/embedding-products[?embedding_status=&model=&skip=&limit=]` (per-model rows), `GET /admin/cron/embedding-products/{product_id}` (embeddings per model + embed-text preview), `GET /admin/cron/embedding-products/active-model`, `POST /admin/cron/embedding-products/reindex` (re-marks every product pending for the active model; returns `{affected, active_model}`) |
| **AI Engine** | `POST /admin/ai-engine/embed-text` — `{"text": "1-1000 chars"}` → `{model, dimensions, embedding[]}`; 503 `AI_ENGINE_ERROR` on engine failure |
| **Search evaluation** | `POST /admin/search-eval/queries/generate` — `{"count": 1-50, "locales": ["en","ar"]}`: builds bilingual catalog context, LLM-generates queries (source `llm`, status `pending`, deduped on text+locale); `POST /admin/search-eval/queries/import` — `{"queries": [{"text", "locale", "relevant_ids"}]}` (source `seed`, judgments created, `evaluated` when ids given); `GET /admin/search-eval/queries[?locale=&source=&status=&q=&skip=&limit=]`; `PATCH /admin/search-eval/queries/{query_id}` — update `status`/`rewritten_query`/`filters`; `PUT /admin/search-eval/queries/{query_id}/judgments` — replace-all judgments `[{"product_id", "relevant", "rank"?}]`; `GET /admin/search-eval/metrics` — MRR@10 + Recall@10 (overall + per-locale); `POST /admin/search-eval/search` — `{"query", "locale", "limit" ≤50}` proxy to engine `/eval/search` with per-hit scores |
| **Conversations** | `GET /admin/chats` — all conversations with the **user identifier resolved** (email/phone/full_name) via a batched Postgres lookup; `GET /admin/chats/{conversation_id}/messages` (cursor-paginated) |

---

## 10. Webhooks (inbound, from the AI Engine)

Both endpoints require the shared webhook secret: `X-Webhook-Secret: <secret>` header **or** `?token=<secret>` query parameter. When `webhook_secret` is unset, verification is disabled (local development).

| Endpoint | Payload | Action |
|---|---|---|
| `POST /webhook/embedding-result` | `{"product_id", "lang", "status": "done"\|"error", "error"?: str, "model"?: str}` | upsert `product_embeddings` row for `(product_id, model)` — `model` falls back to the active embedding model; sets status + `embedding_error` |
| `POST /webhook/ai-engine-bootstrap` | (none) | re-sync: reads system settings + LLM settings and pushes the full config to the engine (`/config`) — called by the engine after its restart |

---

## Rate Limits

| Route | Limit | Route | Limit |
|---|---|---|---|
| `POST /auth/register` | 5 / 300s | `POST /auth/login` | 10 / 60s (+ lockout) |
| `POST /auth/refresh` | 5 / 60s | `POST /auth/logout` | 10 / 60s |
| `POST /auth/send-otp` | 10 / 60s | `POST /auth/verify-otp` | 10 / 60s |
| `/auth/google*`, OTP link endpoints (`/users/me/link/*`) | 10 / 60s each | `GET/PATCH /users/me*` | 60 / 30 per min |
| File uploads / deletes | 30 / 60s | File `GET` | 60 / 60s |
| `GET /product-info/...`, public product detail | 120 / 60s | `/metrics` | 10 / 60s |
| Generic `/products` CRUD | 30/60/30/20 per min (see §5) | Store product mutations | none — public detail `GET` is 120/min |
| unlisted routes | no rate limit (limits are per-route, via `RateLimit(...)` dependencies only) | | |

---

## Errors

```json
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Product not found",
    "details": null,
    "translation_key": "product_not_found",
    "request_id": "a1b2c3d4-..."
  }
}
```

| HTTP | Code | Typical causes |
|---|---|---|
| 400 | `VALIDATION_ERROR` | malformed body, bad types, magic-byte rejection |
| 401 | `AUTHENTICATION_ERROR` | missing/expired/invalid JWT, WS handshake failed |
| 403 | `FORBIDDEN` | not store owner, not admin (`get_admin_user`) |
| 404 | `NOT_FOUND` | resource or conversation missing |
| 409 | `CONFLICT` | duplicate email/username/model, store limit |
| 429 | `RATE_LIMITED` / `ACCOUNT_LOCKED` | rate limit hit; brute-force lockout |
| 500 | `INTERNAL_ERROR` | unhandled (request_id for debugging) |
| 502 | `BAD_GATEWAY` / `DESCRIPTION_GENERATION_FAILED` | engine could not resolve the requested LLM model |
| 503 | `SERVICE_UNAVAILABLE` | engine down (`CHAT_ENGINE_FAILED`, `AI_ENGINE_ERROR`), Mongo disabled, server draining |

Every `translation_key` maps to `messages/{en,ar,fa}.json` in the frontend; see [error-codes.md](error-codes.md) for the contract.
