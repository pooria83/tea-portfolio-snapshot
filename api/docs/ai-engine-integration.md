# AI Engine Integration

How the API talks to `product-graph-ai-engine` — every client method, the exact request/response contracts, context propagation, and the webhook callbacks. The engine is deployed as a separate service; the API is its only authenticated consumer.

## Transport & Auth

- Base URL: `AI_ENGINE_URL` (`settings.ai_engine_url`, default `http://ai-engine:8001`).
- Every request carries the header **`X-API-Key: <settings.api_key>`** (service-to-service auth, set in both `.env` files).
- Client: lazily-created `httpx.AsyncClient` with `timeout=300.0` and `trust_env=False` (no proxy interference).
- Context propagation: `_forward_headers(request_id, user_id)` adds **`X-Request-Id`** and **`X-User-Id`** when present — the engine's `LogContextMiddleware` consumes these so a single user turn is traceable across both services.

## Client Methods (`app/ai/client.py`)

All methods are `async` and used via `app.state.ai_client` (a single instance for the app lifetime; `close()` on shutdown).

| Method | Engine endpoint | Style | Purpose |
|---|---|---|---|
| `health()` | `GET /health` | sync | Readiness check in `/ready` |
| `generate_description(product_data, prompt, model)` | `POST /generate-description` | sync, soft-fail | AI description generation (cron + manual endpoint) |
| `chat(query, locale, limit)` | `POST /chat` | sync | One-shot chat (legacy) |
| `chat_conversational(query, locale, history, summary, ...)` | `POST /chat` | sync | History-aware chat (REST path) |
| `chat_conversational_stream(...)` | `POST /chat` (SSE) | stream | Streaming chat for WebSocket relay |
| `summarize(messages, previous_summary, locale)` | `POST /summarize` | sync | Rolling conversation compaction |
| `title(query, locale, prompt=None, need_title=True)` | `POST /title` | sync | Auto-title from first message; `need_title=false` short-circuits engine-side |
| `embed_product(product_id, lang, text, webhook_url, payload, filters)` | `POST /embed-product` | fire-and-forget | Product embedding (webhook callback) — one call per language |
| `embed_text(text)` | `POST /embed-text` | sync | Embedding test/admin tool |
| `eval_generate_queries(count, locales, catalog_context)` | `POST /eval/queries` | sync, soft-fail | LLM-generated search-eval queries (admin panel) |
| `eval_search(query, locale, limit)` | `POST /eval/search` | sync, soft-fail | Deterministic scored search (admin eval) |
| `similar_products(product_id, locale="en", limit=10, categories=None)` | `POST /similar` | sync, hard-fail | Similar products for a product card (bilingual category chain filter) |
| `update_config(config)` | `POST /config` | sync | Push runtime config to the engine |

### `generate_description` — request/response

Request:
```json
{
  "product": {"name_en": "...", "name_ar": "...", "brand": "...", "category_name": "...",
              "image_alt_texts": [...], "price": 99.0, "currency": "SAR", "attributes": [...]},
  "prompt": "<pre_prompt + product text + ending_prompt>",
  "model": "<optional model name override>"
}
```

Response (`dict`): `{"descriptions": {"en": "...", "ar": "..."}, "model": "...", "prompt": "..."}`.

Failure handling: non-200 or exception ⇒ returns `None` (caller decides — cron retries, the manual endpoint raises `E.DESCRIPTION_GENERATION_FAILED`).

### `chat_conversational` / `chat_conversational_stream` — request/response

Request:
```json
{
  "query": "user message",
  "locale": "en",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
  "summary": "rolling summary or empty",
  "system_prompt": "active chat_assistant template or null (engine default)",
  "parse_prompt": "active parse_query template or null (engine default)",
  "stream": true   // only for the stream variant
}
```

Sync response:
```json
{
  "answer": "assistant text",
  "products": [{"id": "...", "name": "...", "price": ..., "currency": "SAR",
                 "image_url": "...", "buy_url": "...", "store_id": "..."}],
  "search_context": {"rewritten_query": "...", "filters": {...}},
  "debug": {"prompt": {...}, "response": {...}}
}
```

Stream response (SSE): one JSON object per line with a `type` field:
- `{"type": "assistant_start", "search_context": {...}}`
- `{"type": "product_cards", "products": [...]}`
- `{"type": "text_chunk", "delta": "..."}`
- `{"type": "assistant_end"}`
- `{"type": "chat_failed", ...}` (on engine-side failure — replaces `assistant_end`)

The API relays these frames **verbatim** over the WebSocket after enriching `product_cards` (trilingual names + URL normalization).

### `summarize` / `title`

- `summarize`: `{"messages": [{"role", "content"}, ...], "previous_summary": "...", "locale": "en"}` → `{"summary": "...", "tokens_used": N}`.
- `title`: `{"query": "...", "locale": "en", "need_title": bool}` (+ optional `"prompt"`) → `{"title": "..."}`.

Both accept an optional `prompt` override (active `summarize`/`title` templates). For `title`, the API forwards the conversation's `needTitle` flag from `chat_service.maybe_title`; when it is `false` (anonymous sessions) the **engine skips titling** and no title is generated.

### `embed_product` — request/response

Request (one call **per language** — `embed_text_en` then `embed_text_ar`, each a monolingual passage):
```json
{
  "product_id": "uuid",
  "lang": "en",
  "text": "<monolingual embed text for lang>",
  "webhook_url": "https://api.../api/v1/webhook/embedding-result",
  "payload": {"en": {...minified...}, "ar": {...minified...}, "store_id": "..."},
  "filters": {"_color": ["Red"], "_material": ["Cotton"], "_category": ["Dresses"],
               "_brand": ["Zara"], "_gender": ["women"], "_color_family": ["reds-pinks"]}
}
```

The engine: embeds `text` (dense + BM25 sparse tokens) → Qdrant upsert into the per-model collection (with `payload` and flat `filters` as the vector payload for metadata filtering) → POSTs the webhook with `{"status": "done", "lang": "..."}` or `{"status": "error", "reason": "..."}`. The API marks the `product_embeddings` row `done` only when **both** language webhooks arrive.

The API treats this as **fire-and-forget**: `embed_product` returns `None` on transport errors (logged as warning). The status is reconciled asynchronously via the webhook.

### `eval_generate_queries` / `eval_search` — search evaluation

- `eval_generate_queries(count, locales, catalog_context)` → `POST /eval/queries` — LLM-generated diverse shopper queries for the admin search-eval panel.
- `eval_search(query, locale, limit)` → `POST /eval/search` — deterministic parse-path search returning per-hit raw scores (MRR/Recall measurement against the golden set).

### `embed_text` — request/response

`{"text": "1-1000 chars"}` → `{"status": "ok", "model": "...", "dimensions": N, "embedding": [...]}`. Non-`ok` or `None` ⇒ admin endpoint raises `E.AI_ENGINE_ERROR`. Used by the admin "embedding test" page and in tests.

### `update_config` — runtime config push

`POST /config` with a partial config object. The API pushes:

| Config key | Source | When |
|---|---|---|
| `default_llm_model` | `llm_settings.default_llm_model_id` → resolved `{model, api_key (decrypted), base_url}` | admin PUT `/admin/llm/settings`, bootstrap webhook |
| `user_comm_model` | `llm_settings.user_comm_model_id` | same |
| `tei_base_url` | system setting `tei_tunnel_url` | admin PUT `/admin/system-settings`, bootstrap |
| `embedding_provider` | system setting `embedding_provider` | same |

Provider base URLs are mapped in the API: `opencode_zen → https://opencode.ai/zen/v1`, `openrouter → https://openrouter.ai/api/v1`.

**Model → dimensions**: `embedding_provider.model` is the active embedding model. Vector dims are resolved on both sides from the model name — API `EMBEDDING_MODEL_DIMS` (`app/services/embedding_config.py`) and engine `EMBEDDING_MODEL_DIMS` (`app/services/embedding_dims.py`) — so switching models switches collection dims (identical mappings keyed by bare name; the `Qwen/` org prefix is stripped: 0.6B→1024, 4B→2560, 8B→4096, F2LLM-v2-4B→2560, jina-v5-text-small→1024, BGE-M3→1024, Nomic Embed v2→768, e5-base→768, e5-large-instruct→1024). The API does **not** forward `dimensions`; the engine derives them itself.

## Webhook Callbacks (engine → API)

The API exposes two webhook receivers. Both are gated by `verify_webhook_secret` (`app/core/security.py`): the engine must present the shared secret via the **`X-Webhook-Secret`** header or a **`?token=`** query parameter. Verification is disabled when `settings.webhook_secret` (`WEBHOOK_SECRET` env) is unset — configure it in both services' `.env` files; the embedding cron already appends `?token=` to its callback URL.

| Endpoint | Payload | Action |
|---|---|---|
| `POST /api/v1/webhook/embedding-result` | `{"product_id", "lang", "status": "done"\|"error", "error"?: str, "model"?: str}` | Upserts the `product_embeddings` row for `(product_id, model)` — status `done`/`error` (+ `embedding_error`). `model` is the embedding model that produced the vector (falls back to the API's active model) |
| `POST /api/v1/webhook/ai-engine-bootstrap` | (no body) | Reads `tei_tunnel_url`, `embedding_provider`, `default_llm_model`, `user_comm_model` from Postgres and pushes them to the engine via `/config` — used to re-sync the engine after a restart |

## Error Semantics

- **Hard-fail** methods (`chat*`, `summarize`, `title`, `update_config`, `similar_products`): `response.raise_for_status()` → non-2xx propagates as an httpx error; chat paths convert to `ServiceUnavailableError` (`E.CHAT_ENGINE_FAILED` / `E.AI_ENGINE_ERROR`). `similar_products` additionally maps a **404 to `NotFoundError`** (`E.PRODUCT_NOT_FOUND`) before raising on any other non-200.
- **Stream path**: non-200 ⇒ `ServiceUnavailableError` with the engine's status + body snippet in `extra`.
- **Soft-fail** methods (`generate_description`, `embed_product`, `embed_text`, `eval_generate_queries`, `eval_search`, `health`): return `None`/`False`; callers decide (retry, degrade, or raise a domain error with the right translation key).
- **502 from engine** = requested model could not be resolved (engine-side contract).

## Callers of Each Method

| Method | Called from |
|---|---|
| `health` | `/ready` readiness check |
| `generate_description` | `product_ai_cron` (batch), `POST /stores/{store_id}/products/{product_id}/generate-descriptions` (manual) |
| `chat_conversational` | `chat_service.send_message` (REST `POST /chats/{id}/messages`) |
| `chat_conversational_stream` | `ws.py` `_relay_chat_stream` (WS `/ws/chat/{id}`) |
| `summarize` | `chat_service.maybe_compact` |
| `title` | `chat_service.maybe_title` |
| `embed_product` | `embedding_cron._embed_single_product` (recovery cron + backfill script) |
| `embed_text` | admin `POST /admin/ai-engine/embed-text` |
| `eval_generate_queries` | admin `POST /admin/search-eval/queries/generate` |
| `eval_search` | admin `POST /admin/search-eval/search` |
| `similar_products` | `chat_service.find_similar` (WS `similar_request` frame) |
| `update_config` | admin LLM settings, admin system settings, bootstrap webhook |

## Operational Notes

- The engine is **stateless for embedding**: it never touches PostgreSQL; all status updates flow back through the webhook (per-model rows). This is why the API's `api_base_url` setting must be reachable from the engine (tunneled in dev via `tei_tunnel_url` for TEI).
- Both services must share `LLM_ENCRYPTION_KEY` if the engine resolves API keys (currently key decryption happens in the API and plaintext keys are pushed over `/config`).
- Engine-side docs live in the `product-graph-ai-engine` repo (`docs/`).
