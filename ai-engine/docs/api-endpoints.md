# API Endpoints

Complete reference for every HTTP endpoint exposed by the AI Engine.

Base URL: `http://<host>:8003` (port from `AI_ENGINE_PORT`, default `8003`).
Interactive docs: `GET /docs` (FastAPI Swagger UI).

Forwarded headers:

| Header | Meaning |
|---|---|
| `X-Request-Id` | Propagated into log context and activity logs |
| `X-User-Id` | Propagated into log context; sets log source to `authenticated` |

### Authentication

Every endpoint **except `GET /health`** requires an `X-API-Key` header matching
the engine's `ENGINE_API_KEY` setting (`EngineAuthMiddleware`,
`app/core/auth.py`, wired in `app/main.py`). The comparison is constant-time
(`hmac.compare_digest`); a missing or wrong key returns
`401 {"detail": "Invalid or missing API key"}`. When `ENGINE_API_KEY` is empty
the guard is disabled entirely (local development). `/health` is exempt so the
Docker HEALTHCHECK works without a key.

---

## GET /health

Returns liveness status. Used by the Docker HEALTHCHECK.

**Response**

```json
{"status": "ok"}
```

---

## POST /config

Runtime configuration overrides. Everything is optional and applied
incrementally; the body may contain one or more keys. Persisted to the runtime
config JSON file (`AI_ENGINE_CONFIG_PATH`) and applied immediately to live
clients.

**Request** — partial config object:

```json
{
  "tei_base_url": "https://xxx.trycloudflare.com/v1",
  "embedding_provider": {"provider": "openrouter", "model": "Qwen/Qwen3-Embedding-4B", "api_key": "", "api_key_encrypted": false, "base_url": ""},
  "default_llm_model": {"model": "deepseek-v4-flash-free", "api_key": "", "provider": "opencode_zen"},
  "user_comm_model": {"model": "deepseek-v4-flash-free", "api_key": "", "provider": "opencode_zen"},
  "refresh_llm": true
}
```

| Key | Type | Effect |
|---|---|---|
| `tei_base_url` | `string` | Persists as `tei_tunnel_url`; if the active embedding model is `TEIModel`, its base URL is swapped live (`set_base_url`). |
| `embedding_provider` | `{provider, model, api_key, api_key_encrypted, base_url}` | Rebuilds the `EmbeddingClient` with a new model instance and switches to (and ensures) that model's Qdrant collection. `provider` ∈ `tei` \| `sentence_transformer` \| `openrouter`; `model` overrides the embedding model; when `api_key_encrypted` is truthy, `api_key` is Fernet-decrypted first. |
| `default_llm_model` | `{model, api_key, provider}` | Replaces `app.state.llm_client`. `provider` ∈ `opencode_zen` (default) \| `openrouter` and **pins** the base URL — a caller-supplied `base_url` is ignored (API keys must never be sent to arbitrary hosts). |
| `user_comm_model` | `{model, api_key, provider}` | Replaces `app.state.comm_llm_client`. Same `provider` semantics and base-URL pinning as above. |
| `refresh_llm` | `bool` | Re-resolves both LLM keys from PostgreSQL (`llm_api_keys`) and rebuilds both clients (uses persisted `default_llm_model` / runtime `user_comm_model` names). |

**Response**

```json
{"status": "ok", "changes": {"user_comm_model": "deepseek-v4-flash-free"}}
```

`changes` lists every key that was actually applied. An `embedding_provider`
change can additionally report `collection_error` (Qdrant ensure failed — the
previous collection is restored), plus `collection` and `embedding_model` on
success; a `refresh_llm` change reports `"refresh_llm": "ok"`.

See [Configuration](configuration.md#3-runtime-config-endpoint) for details.

---

## POST /generate-description

Generates EN/AR (and optionally FA) product descriptions.

**Request** — `GenerateDescriptionRequest`:

```json
{
  "product": {
    "name_en": "Silk Dress",
    "name_ar": "فستان حريري",
    "name_fa": "لباس ابریشمی",
    "brand": "Zara",
    "category_name": "Dresses",
    "image_alt_texts": ["Front view", "Back view"],
    "attributes": [{"name": "color", "value": "red"}],
    "price": 99.99,
    "currency": "SAR"
  },
  "prompt": null,
  "model": null
}
```

| Field | Description |
|---|---|
| `product` | `ProductData` — all fields optional except the (possibly empty) structure itself |
| `prompt` | Custom raw prompt. When present, sent verbatim to the LLM (bypasses product-text building). |
| `model` | Model override. If it differs from the default, the engine resolves its API key from PostgreSQL (`llm_api_keys`/`llm_models`) and creates a dedicated client. |

**Flow** (see [Architecture](architecture.md#43-description-generation-flow)):

1. Resolve model: default client, or per-model client from DB.
2. Either `_build_product_text(product)` → `DESCRIPTION_SYSTEM_PROMPT`, or the raw custom `prompt`.
3. LLM call with `response_format={"type": "json_object"}`, temperature 0.7, up to 3 attempts (1s/2s backoff).
4. Parse JSON → `{"en": "...", "ar": "..."}`.

**Response** — `DescriptionResponse`:

```json
{
  "descriptions": {"en": "...", "ar": "..."},
  "model": "deepseek-v4-flash-free",
  "tokens_used": 245,
  "prompt": "the prompt that was sent"
}
```

**Errors**

| Code | Condition |
|---|---|
| 502 | LLM failed after retries, model could not be resolved from DB, or no DB connection |

---

## POST /chat

RAG conversational product search. One endpoint, two response modes:

- `stream: false` (default) → JSON `ChatResponse`.
- `stream: true` → SSE stream of JSON frames.

**Request** — `ChatRequest`:

```json
{
  "query": "red dress",
  "locale": "en",
  "limit": 10,
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
  "summary": "previous conversation summary...",
  "stream": false,
  "parse_prompt": null,
  "system_prompt": null
}
```

| Field | Default | Description |
|---|---|---|
| `query` | — (required) | The user's new message |
| `locale` | `"en"` | Requested response locale; overridden by script-detection of `query` |
| `limit` | `10` | Max products returned (per search spec) |
| `history` | `[]` | Prior conversation messages (`role` ∈ `user`\|`assistant`, content ≤ 8000 chars) |
| `summary` | `""` | Rolling conversation summary, injected as a system message before history |
| `stream` | `false` | `true` → SSE streaming response |
| `parse_prompt` | `null` | Custom prompt for the query-parse fallback path |
| `system_prompt` | `null` | Custom system prompt replacing the default fashion-assistant prompt |

**Behavior summary**

1. `detect_locale(query)` overrides `locale` when the query script is conclusive (fa > ar > en).
2. Build messages: system prompt (+ optional summary system message) + history + query.
3. **Search resolution** (`_resolve_search`):
   - Try tool calling on the comm LLM with the `search_products` tool.
   - Tool call(s) → one or more search specs `(query, filters)`, executed and merged.
   - Model answers without a tool call → **direct answer**, no search performed.
    - Tool calling unavailable/unsupported → `parse_search_query` fallback → `(rewritten_query, filters)`; when the rewrite differs from the raw query, the raw query is also searched verbatim as an extra spec (attribute words can never be lost).
4. Each spec: embed query → Qdrant search (filtered + unfiltered fallback).
5. No products → localized no-results hint (`_NO_RESULTS_HINTS` for ar/fa/en).
6. Answer via comm LLM with product context.

**Non-streaming response** — `ChatResponse`:

```json
{
  "answer": "Here is a red cotton dress that fits your request...",
  "products": [{
    "id": "p1", "name": "Red Cotton Dress", "price": 150.0,
    "currency": "SAR", "brand": "Zara", "image_url": "https://...",
    "store_id": "s1", "product_data": {"en": {...}, "ar": {...}}
  }],
  "search_context": {
    "rewritten_query": "red dress",
    "filters": {"color": ["Red", "red", "Red", "RED"]},
    "tool_used": false,
    "specs": [{"query": "red dress", "filters": {"color": [...]}}]
  },
  "tokens_used": null,
  "debug": {"prompt": {...}, "response": {...}}
}
```

| Field | Notes |
|---|---|
| `answer` | The assistant's reply; for a direct-answer turn there are no products and `search_context` is `null` |
| `products` | `ProductRef[]` — normalized from Qdrant payload (see [Embedding](embedding.md#5-payload-schema-and-parsing)) |
| `search_context` | `rewritten_query`/`filters` mirror the first spec (backward compat); `specs` lists every executed spec; `tool_used` tells whether the tool path was taken |
| `tokens_used` | Always `null` in the current implementation (reserved) |
| `debug` | Present when the LLM call captured debug (only when a tool/parse call succeeded and capture was enabled) |

**Streaming response** (`stream: true`) — `Content-Type: text/event-stream`.
Each **line** is a standalone JSON object (newline-delimited, not `data:`
prefixed). Frame types, in order:

```
{"type": "debug", "debug": {...}}                    ← optional, first (parse/tool debug)
{"type": "assistant_start", "search_context": {...}} ← always
{"type": "product_cards", "products": [...], "locale": "en"}   ← cards (or empty + no-results text)
{"type": "text_chunk", "delta": "Here "}             ← repeated, answer tokens
{"type": "text_chunk", "delta": "is ..."}
{"type": "assistant_end"}                            ← always last on success
{"type": "error", "code": "embedding_failed"}        ← instead of the above on failure
{"type": "error", "code": "chat_failed"}             ← stream failed AND fallback failed
```

Error codes: `embedding_failed` (embedding unavailable/failed), `chat_failed`
(stream broke and non-streaming fallback also failed). On `embedding_failed`
the stream ends immediately — no `assistant_start`/`assistant_end` frames are
sent. On `chat_failed` the error frame replaces the final `assistant_end`
(after `assistant_start` + `product_cards` were already delivered).

**Errors (non-streaming)**

| Code | Condition |
|---|---|
| 502 | Embedding failed (`EMBED_FAILED`), or LLM answer generation failed |

See [Chat Flow](chat-flow.md) for the full pipeline.

---

## POST /embed-product

Stateless product embedding: embed → Qdrant upsert → webhook callback. The
upsert targets the **active model's collection** (`collection_name_for`
→ `products-{slug}`); the webhook payload includes the model name so the API
can update the right `product_embeddings` row.

**Request** — `EmbedProductRequest`:

```json
{
  "product_id": "9a3b...",
  "lang": "en",
  "text": "Red silk dress for summer...",
  "webhook_url": "https://api.example.com/webhook/embedding-result",
  "payload": {"en": {...}, "ar": {...}, "store_id": "..."},
  "filters": {"_color": ["red"], "_material": ["cotton"], "_category": ["Dresses"], "_brand": ["Zara"]}
}
```

| Field | Description |
|---|---|
| `product_id` | Product UUID (uniqueness key with `lang`) |
| `lang` | `en` or `ar` — each language is a separate Qdrant point |
| `text` | The passage to embed |
| `webhook_url` | Where the API gets the result; optional |
| `payload` | Bilingual `product_data` stored verbatim in the Qdrant payload |
| `filters` | Flat filter fields, merged into the payload as-is |

**Flow:**

1. `embed_passage(text)` (no prefix for Qwen3/SentenceTransformer; `passage:` prefix for OpenRouter).
2. `point_id = uuid5(NAMESPACE_DNS, f"{product_id}_{lang}")` — deterministic, idempotent upsert.
3. `rag_service.upsert_embedding(...)` → Qdrant.
4. Webhook (retry 3 attempts on 5xx/network failures with backoff 1s/2s —
   client 4xx errors are never retried) — every payload carries
   `"model": embedding_client.model_name`:
   - success: `{"product_id", "lang", "status": "done", "model": "..."}`
   - embedding None: `{"status": "error", "error": "embedding returned None", "model": "..."}`
   - Qdrant failure: `{"status": "error", "error": "qdrant_upsert_failed", "model": "..."}`
5. Response `{"status": "ok"}`.

**Responses**

| Status | Body | Meaning |
|---|---|---|
| 200 | `{"status": "ok"}` | Embedded + upserted (+ webhook fired) |
| 200 | `{"status": "error", "reason": "embedding failed"}` | `embed_passage` returned None |
| 200 | `{"status": "error", "reason": "qdrant upsert failed"}` | Qdrant upsert threw |
| 200 | `{"status": "error", "reason": "webhook delivery failed"}` | Embedded + upserted, but the success webhook could not be delivered |
| 200 | `{"status": "skipped", "reason": "embedding service not available"}` | `embedding_client`/`rag_service` missing on `app.state` (no webhook fired) |

**Webhook SSRF guard** — every webhook URL passes `is_safe_webhook_url`
(`app/core/ssrf.py`, called inside `_send_webhook`): HTTPS-only scheme, no
userinfo component, and the host must resolve to a public IP — re-resolved
immediately before delivery as a DNS-rebinding guard. Redirects are never
followed. An unsafe URL is rejected before any request is made (logged and
skipped), which on the success path surfaces as the
`webhook delivery failed` response above.

Note: the endpoint never returns non-200 for these cases — the API tracks
success/failure via the webhook.

---

## POST /embed-text

Admin/embedding test utility: embed a free text and return the raw vector
(no Qdrant interaction).

**Request** — `EmbedTextRequest`:

```json
{"text": "passage to embed"}
```

`text` length: 1–1000 chars.

**Response**

```json
{"status": "ok", "model": "Qwen/Qwen3-Embedding-0.6B", "dimensions": 1024, "embedding": [0.1121, ...]}
```

**Errors**

| Status | Body | Condition |
|---|---|---|
| 200 | `{"status": "error", "reason": "embedding failed"}` | `embed_passage` returned None |
| 200 | `{"status": "error", "reason": "embedding service not available"}` | no `embedding_client` on state |

---

## POST /summarize

Rolling conversation summary. `S2 = f(S1, new_messages)` — the model merges
the previous summary with new messages rather than re-summarizing from scratch.

**Request** — `SummarizeRequest`:

```json
{
  "messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
  "previous_summary": "Previous summary...",
  "locale": "en",
  "prompt": null
}
```

**Behavior**

- Empty/whitespace-only messages → returns `previous_summary` unchanged with `tokens_used: 0` (no LLM call).
- Otherwise runs `SUMMARIZE_PROMPT` on the comm LLM (temperature 0.2, retries).

**Response** — `SummarizeResponse`:

```json
{"summary": "Merged summary...", "tokens_used": 120}
```

**Errors**

| Code | Condition |
|---|---|
| 502 | LLM returned None after retries |

---

## POST /title

Short conversation title (2–6 words) from the first user message.

**Request** — `TitleRequest`:

```json
{"query": "show me red dresses under 200 SAR", "locale": "en", "need_title": true, "prompt": null}
```

`query` length: 1–4000 chars.

**Behavior**

- Runs `TITLE_PROMPT` on the comm LLM (temperature 0.2, `max_tokens=512`).
- Result is stripped of quotes/whitespace; empty result counts as failure (retried).
- `need_title: false` skips the LLM entirely — the title is cut from the first words of the query.
- LLM failure after retries (or `need_title: false`) → title is the first ~50 chars of the query (never a 5xx).

**Response** — `TitleResponse`:

```json
{"title": "Red dresses"}
```

**Errors**

| Code | Condition |
|---|---|
| — | LLM failure after retries → first-words fallback title (200), no 502 |

---

## POST /eval/queries

Search-eval tooling: generate a batch of diverse, catalog-realistic shopper
queries with the conversational LLM, for the admin eval panel.

**Request** — `EvalQueriesRequest`:

```json
{
  "count": 10,
  "locales": ["en", "ar"],
  "catalog_context": "Dresses, Watches, Perfumes — brands: Zara, H&M"
}
```

| Field | Default | Description |
|---|---|---|
| `count` | `10` | Number of queries to generate (1–50) |
| `locales` | `["en", "ar"]` | Distribute generated queries across these locales |
| `catalog_context` | `""` | Grounding context (categories, brands, attributes, sizes) for realistic queries |

**Behavior**

- Runs `EVAL_QUERIES_PROMPT` on the comm LLM (temperature 0.8, JSON mode).
- Queries are validated (`text` non-empty, `locale` ∈ `en`\|`ar`), deduplicated
  by `(text, locale)` and trimmed to `count`.

**Response** — `EvalQueriesResponse`:

```json
{
  "queries": [
    {"text": "red lace dress", "locale": "en"},
    {"text": "فستان دانتيل أحمر", "locale": "ar"}
  ]
}
```

**Errors**

| Code | Condition |
|---|---|
| 502 | LLM call failed after retries or returned an unparsable/bad-shape payload |

---

## POST /eval/search

Search-eval tooling: deterministic parse-path search that returns each hit
with its raw vector score, for measuring search quality (MRR/Recall).

**Request** — `EvalSearchRequest`:

```json
{"query": "red lace dress", "locale": "en", "limit": 10}
```

| Field | Default | Description |
|---|---|---|
| `query` | — (required) | The search query to evaluate |
| `locale` | `"en"` | Request locale (drives parse hints) |
| `limit` | `10` | Max results returned (1–50) |

**Behavior**

- Resolves the query via `_resolve_search(..., use_tools=False)` — the
  **parse path only** (rewritten query + normalized filters + raw-query dual
  spec), **no tool-calling variance**, so evals are reproducible.
- Each spec is embedded and searched with `rag.search_scored` (same tiering as
  `rag.search` but keeps the raw score).
- Results are merged/deduped by product id.
- If resolution yields a direct answer or no specs at all, the response is
  `rewritten_query: null`, `filters: null`, `specs: []`, `results: []`
  (logged `EVAL_SEARCH_NO_SPECS`).

**Response** — `EvalSearchResponse`:

```json
{
  "query": "red lace dress",
  "locale": "en",
  "rewritten_query": "red lace dress",
  "filters": {"color_family": ["reds-pinks"], "category": ["Dresses", "dresses", "DRESSES"]},
  "specs": [{"query": "red lace dress", "filters": {...}}],
  "results": [
    {"rank": 1, "score": 0.91, "product": {"id": "p1", "name": "Red Dress", ...}},
    {"rank": 2, "score": 0.87, "product": {"id": "p2", "name": "Lace Dress", ...}}
  ]
}
```

**Errors**

| Code | Condition |
|---|---|
| 502 | Embedding failed |

---

## POST /similar

Find products similar to an already-indexed product — powers the "similar
products" section in the web/mobile apps.

**Request** — `SimilarRequest`:

```json
{"product_id": "p123", "lang": "en", "limit": 10, "categories": [["Dresses"]]}
```

| Field | Default | Description |
|---|---|---|
| `product_id` | — (required) | Reference product to find lookalikes of |
| `lang` | `"en"` | Preferred language for the reference point |
| `limit` | `10` | Max results (1–50) |
| `categories` | `null` | Ordered category chain to constrain candidates to (leaf → parent → root) |

**Behavior** (metadata-aware, dense-only — see [Search Quality](search-quality.md#24-what-stays-dense-only))

1. **Scroll** the reference point by `product_id`; when several points share
   the id (one per language), prefer the point whose payload `lang` matches
   the request so the query vector is in the caller's language.
2. **Tiered candidate search**, each tier filled with `_query_hits` on the
   reference vector, deduped by `product_id`, reference excluded:
   - category chain from the request (+ the reference payload's own
     `_category` values as a guaranteed non-empty fallback) → hard
     `_category` filter;
   - if short: relaxed to the reference's `_color_family` (ANDed with the
     category chain, so off-category lookalikes can't leak in);
   - if still short: unfiltered vector search.
3. **Final ranking**: `score + SIMILAR_COLOR_FAMILY_BONUS × family_overlap`
   — same-color-family products outrank closer vector hits of a different
   color.
4. Returns `product_id`, `name`, `price`, `currency`, `brand`, `image_url`,
   `store_id` per hit.

**Response** — `SimilarResponse` (schemas in `app/models/similar.py`): `{"products": [...]}`

**Errors**

| Code | Condition |
|---|---|
| 404 | `product_id` not found in the index (no point scrolled) |

---

## Endpoint Summary

| Method | Path | Body | Response | Streaming |
|---|---|---|---|---|
| GET | `/health` | — | `{"status": "ok"}` | no |
| POST | `/config` | partial config | `{"status", "changes"}` | no |
| POST | `/generate-description` | `GenerateDescriptionRequest` | `DescriptionResponse` | no |
| POST | `/chat` | `ChatRequest` | `ChatResponse` \| SSE frames | optional (`stream: true`) |
| POST | `/embed-product` | `EmbedProductRequest` | `{"status": ...}` | no |
| POST | `/embed-text` | `EmbedTextRequest` | `{"status", "model", "dimensions", "embedding"}` | no |
| POST | `/summarize` | `SummarizeRequest` | `SummarizeResponse` | no |
| POST | `/title` | `TitleRequest` | `TitleResponse` | no |
| POST | `/eval/queries` | `EvalQueriesRequest` | `EvalQueriesResponse` | no |
| POST | `/eval/search` | `EvalSearchRequest` | `EvalSearchResponse` | no |
| POST | `/similar` | `SimilarRequest` | `SimilarResponse` | no |
