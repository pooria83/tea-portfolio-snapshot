# Chat System

The conversational AI assistant — how a user message travels from the WebSocket to the AI Engine and back, how state is stored, and how history is kept within budget.

## Architecture Overview

```
Mobile App (WebSocket)          API (FastAPI)                 AI Engine              Mongo / Postgres
       │  ws://api/v1/ws/chat/{id}    │                            │                     │
       │─────────────────────────────▶│ _authenticate_ws (JWT)     │                     │
       │ send_message                 │ claim_turn (atomic slot)   │                     │
       │                              │ (build history, prompts)   │                     │
       │                              │ chat_conversational_stream │                     │
       │                              │───────────────────────────▶│ (SSE frames)        │
       │◀─────────────────────────────│ relay frames (enriched)     │                     │
       │◀─────── message_saved ──────│ persist once post-stream    │                     │
       │                              │ maybe_compact / maybe_title │────────────────────▶│
```

Mongo is the **conversation state store**; Postgres holds the product catalog (used to enrich product cards) and prompt templates.

## WebSocket Endpoints

### `WS /ws/chat/{conversation_id}` — streaming chat

- **Auth**: the JWT travels as the **raw first `Sec-WebSocket-Protocol` value** (the accepted subprotocol is echoed back in the handshake). Fallbacks: the `access_token` cookie, `?token=` query param, or `Authorization` bearer header. Verification via `decode_token` sets `user_id_var` and `request_id_var` (`ws_{user_id}` so logs and the AI Engine share one trace id per socket); failures close the socket with code `4001`.
- Frames are JSON with a `type` field, capped at **10 KB**.

**Inbound frames**:

| Frame | Content | Meaning |
|---|---|---|
| `ping` | — | Liveness probe; answered with a `pong` frame |
| `send_message` | `{"content": "…", "idempotency_key": "…", "include_saved_message": bool}` | Run a turn. Empty content → `empty_content`. `include_saved_message=true` makes the final `message_saved` carry the full assistant + user messages |
| `similar_request` | `{"product_id": "…", "product_name"?: "…", "include_saved_message"?: true}` | Products similar to a product card — the API calls the engine's `/similar` (metadata-aware tiers), persists an assistant reply (localized "similar to X" label + product snapshots), then replies in order: `product_cards` → `assistant_end` → `message_saved`. Consumes no user message slot |

**Outbound frames** (all JSON, `type` field):

| Frame | Content | Meaning |
|---|---|---|
| `pong` | `{}` | Answer to `ping` |
| `assistant_start` | `{search_context}` | Engine began; verbatim relay of the engine frame |
| `product_cards` | `{products: […]}` | Relayed **after enrichment**: trilingual names/brands, normalized `image_url`, `buy_url` (see below) |
| `text_chunk` | `{delta}` | Streaming text chunks, relayed verbatim |
| `debug` | `{debug}` | Engine debug payload, relayed verbatim |
| `assistant_end` | — | Stream complete |
| `error` | `{code, message?}` | see error codes below |
| `message_saved` | `{conversation_id, message_id}` + optional full `message` / `user_message` | Emitted by the API after persistence (never relayed from the engine) — the client's durability signal; always the last frame of a turn |

- **Error codes** are lowercase snake_case: `conversation_not_found`; `conversation_closed` or `chat_limit_reached` (both surface as the `claim_turn` conflict — the limit variant when `userMessageCount >= chat_max_messages`); `chat_failed` (mid-stream engine failure — emitted **before** `message_saved`); `message_too_large`; `invalid_frame`; `unsupported_frame`; `empty_content`; `chat_not_available`; `missing_product_id`; `product_not_found`.
- **Serial handler**: the socket processes one turn at a time. Frames arriving during a stream queue up and are processed after it — there is no busy rejection.
- **Persistence guarantee**: nothing writes `status: "streaming"` — each message is persisted exactly once, post-stream, as `completed` or `failed` (a failed turn stores the engine error code in `message.error` plus `searchContext = {"intent": "error"}`). There is no stale-streaming finalizer because no such state is ever written; a client disconnect simply cancels the relay.

### REST endpoints

- `POST /chats` — body `ConversationCreate {locale, app_version, create_new, need_title}` — **creates or reuses the active conversation only** (one active thread per user; `create_new=true` forces a fresh one) and returns the conversation alone (`201`). `need_title` (default `true`) controls LLM titling — anonymous sessions set it `false`.
- `POST /chats/{id}/messages` — body `{content ≤4000 chars, idempotency_key}` — runs a full non-streaming turn and returns `{conversation, user_message, assistant_message|null}`.
- `GET /chats` — paginated conversation list for the user.
- `GET /chats/{id}/messages` — cursor-paginated messages.
- `POST /chats/{id}/messages/{message_id}/feedback` — body `{rating: 1–5}` — star rating on an assistant message; returns `{id, rating}`.
- `DELETE /chats/{id}` — soft delete (`status: "closed"` + `deletedAt`).

No chat endpoint returns `remaining_messages`, `summary`, or `history` — those stay server-side.

### `POST /api/v1/chat/anonymous-session` — public anonymous chat

Public visitors (home-page chat, no account) get an ephemeral identity:

- Body: `ConversationCreate` — `{"locale", "app_version"}`.
- Creates a Mongo conversation with **`need_title=false`** and mints a
  **10-minute anon JWT** (`type: "anon"`, random `sub` — no Postgres user).
- Response `201`: `{"token", "conversation"}`. The token authenticates the
  WebSocket only (`_authenticate_ws`); every authenticated REST dependency
  (`get_authenticated_user`) rejects it, so anonymous conversations can never
  touch user data.
- Rate limited `20 req / 60s`.

## Conversation Lifecycle

1. **Create**: `ensure_active_conversation` — an existing `status: "active"` conversation is reused (users get one active thread).
2. **Turn**: `claim_turn` increments `userMessageCount` in a single atomic Mongo `find_one_and_update` (safe under concurrent sends). If the increment would exceed `chat_max_messages` (default **20**, `1–100`), the conversation is auto-closed (`status: "closed"`) and the turn is rejected with a conflict that surfaces as `chat_limit_reached` over WS.
3. **Close**: manual (`DELETE /chats/{id}` — soft delete) or automatic at the limit. Closed conversations stay readable.
4. **Title**: `maybe_title` — when the title is still empty, the first user message goes to engine `/title` with `{query, locale, need_title}`; the conversation's `needTitle` flag is forwarded, so conversations created with `need_title=false` (anonymous) are skipped engine-side. The result lands in `conversation.title`.
5. **Compaction**: `maybe_compact` — when unsummarized tokens exceed `chat_compact_threshold_tokens` (**default 4000**, a pydantic Settings/env value), the oldest unsummarized messages beyond the history window are sent to engine `/summarize` → `conversation.summary` is updated with the new rolling summary, `summarizedMessageCount` grows. The last `chat_history_window` (default **12**) messages are always kept raw.
6. **Locale**: `detect_locale` runs per turn and upgrades `conversation.locale` (`en`/`ar`/`fa`/`auto`).
7. **Intent round-trip**: the engine's `search_context.intent` (`greeting` / `search` / `general`, or `error` for failed turns) is persisted on the assistant message (`searchContext`) and echoed back to the client in `assistant_start` — clients theme the UI (intent bubbles, product name) from it. Similar-product replies (from `similar_request`) carry the localized "similar to X" labels set via the same flow.

## Mongo Schema

DB name is env-scoped: `tea-dev` (development) / `tea-production` (production). Collections: `conversations`, `messages`.

### `conversations`

| Field | Type | Notes |
|---|---|---|
| `_id` | `str` | UUID |
| `userId` | `str` | equals the API user id |
| `status` | `"active"` / `"closed"` | |
| `title` | `str \| null` | set by auto-titling |
| `userMessageCount` | `int` | atomic slot counter |
| `summary` | `str` | rolling compaction summary |
| `summaryTokenCount` | `int` | |
| `summarizedMessageCount` | `int` | messages absorbed into the summary |
| `locale` | `str` | `en` / `ar` / `fa` / `auto` |
| `needTitle` | `bool` | `false` for anonymous sessions — title generation skipped |
| `appVersion` | `str` | client version for feature flags |
| `lastActivityAt`, `createdAt`, `updatedAt`, `deletedAt` | `datetime` | |

### `messages`

| Field | Type | Notes |
|---|---|---|
| `_id` | `str` | UUID |
| `conversationId` | `str` | index + query pattern |
| `role` | `"user"` / `"assistant"` | |
| `content` | `str` | |
| `status` | `"completed"` / `"failed"` | written once post-stream; the schema keeps a `"streaming"` literal but nothing writes it |
| `feedback` | `object \| null` | subdocument `{rating, comment?, createdAt}` from the 1–5 star rating endpoint (assistant messages) |
| `tokenCount` | `int` | |
| `productSnapshots` | `list[dict]` | id, trilingual name/brand, price, currency, image_url (MinIO-normalized), buy_url, store_id |
| `searchContext` | `dict` | `{rewritten_query, filters, intent}` from the engine (intent round-trip) |
| `debug` | `dict` | engine debug payload |
| `error` | `str` | error code when failed |
| `locale` | `str` | per-message locale |
| `createdAt` | `datetime` | |
| `idempotencyKey` | `str` | **unique index** — client-supplied message id; deduplicates double-sends |

## History Budgeting (`chat_service._build_history`)

- Take the last `chat_history_window` messages from Mongo.
- Budget = **`max(2000, context_window * 0.5)`** where `context_window` comes from the active communication model (`llm_settings.user_comm_model_id`); when the setting/model/window is unavailable the fallback budget is `_DEFAULT_CONTEXT_BUDGET = 12000` tokens. Cost per message estimated as `len(content)/4`.
- Walk newest → oldest, accumulating until the budget is exhausted (only the current user message is guaranteed in).
- Return `(history, summary, locale)` for the engine call — the summary carries everything older.

## Product Card Enrichment

The engine returns products by catalog id. The API's `enrich_product_names` fetches `store_products` + `brands` in one batched query and attaches:

- trilingual names (`name_en`, `name_ar`, `name_fa`),
- trilingual brands (`brand_en`, `brand_ar`, `brand_fa`),
- `image_url` normalized via `_normalize_image_url` (MinIO public prefix; storage-dev host swapped for the public URL — **the storage account is irrelevant to the client**),
- `buy_url`, `price`, `currency`, `store_id`.

Failures here are logged, never raised — the chat still completes.

## Limits & Controls

| Setting | Default | Effect |
|---|---|---|
| `CHAT_MAX_MESSAGES` (`1–100`) | 20 | max user messages per conversation, then auto-close (`chat_limit_reached`) |
| `CHAT_HISTORY_WINDOW` (`1–100`) | 12 | raw messages kept for the engine |
| `CHAT_COMPACT_THRESHOLD_TOKENS` (`ge=500`, pydantic Settings/env) | 4000 | unsummarized token count that triggers rolling compaction |
| History-budget fallback | 12000 | `_DEFAULT_CONTEXT_BUDGET` used when no comm model/context window resolves; a resolved window floors at 2000 tokens via `max(2000, context_window * 0.5)` |
| Mongo unset (`MONGO_URL` empty) | — | chat endpoints return `503 ServiceUnavailableError`, translation key `E.CHAT_NOT_AVAILABLE` (`"chat_not_available"`) |

## Admin

`GET /admin/chats` — paginated list of all conversations, each with the user behind it resolved to an identifier (email → phone → full_name). `GET /admin/chats/{id}/messages` — cursor-paginated messages of one conversation. Both are read-only — there is no admin delete/purge endpoint.

## Tests

`tests/api/v1/test_chat_ws.py` (WebSocket protocol), `tests/api/v1/test_chats.py` (REST create/turns/list), `tests/api/v1/test_admin_chats.py`, `tests/test_chat_service_stream.py` (stream relay + persistence), `tests/test_chat_service_lang.py` (locale detection), `tests/test_chat_service_similar.py` (similar-products flow), `tests/test_anonymous_chat.py` (anon token isolation), `tests/test_ws.py` (auth failures, invalid frames).
