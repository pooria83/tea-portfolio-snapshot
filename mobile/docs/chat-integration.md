# Chat Integration (AI Chat)

How the mobile app talks to the TEA-assist chat API: the HTTP conversation endpoints, the WebSocket streaming protocol, and the find-similar-products flow.

Related: [component-map.md](component-map.md) for where each piece lives, [error-handling.md](error-handling.md) for the error pipeline.

## Architecture

```
HomeScreen
├── useChatWebSocket({conversationId, onMessageSaved})   # WebSocket → /ws/chat/{id} (streaming)
├── useChatMutations                   # HTTP → /chats, /chats/{id}/messages
└── chatStreamReducer                  # ChatStreamState: start/debug/chunk/products/completed/failed/reset
```

Messages stream over a single WebSocket; conversations and persisted history go over HTTP (Axios, `src/services/api/client.ts`). The server is the source of truth — every message is persisted by the API and re-synced via `GET /chats/{id}/messages`.

Two layers with distinct vocabularies — don't conflate them:

- **Wire frames** travel over the socket and are mapped in `useChatWebSocket.ts`: `assistant_start`, `debug`, `text_chunk`, `product_cards`, `assistant_end`, `error`, `message_saved`.
- **Reducer actions** (`chatStream.ts`) are internal state transitions dispatched by the hook: `start`, `debug`, `chunk`, `products`, `completed`, `failed`, `reset`. They never appear on the wire.

## HTTP endpoints (`src/features/chat/useChatMutations.ts`)

The chat feature reads `response.data` directly as raw arrays/objects — it does **not** go through `unwrapEnvelope` (that helper serves auth/profile/favorites/product detail, not chat).

| Hook                                  | Method | Path                    | Notes                                        |
| ------------------------------------- | ------ | ----------------------- | -------------------------------------------- |
| `useGetConversationsQuery`            | GET    | `/chats`                | React Query key `['chats']`                  |
| `useCreateConversationMutation`       | POST   | `/chats`                | Body `{locale, create_new}`; returns conversation id |
| `useGetConversationMessagesQuery`     | GET    | `/chats/{id}/messages`  | Loads persisted history (messages normalized by `normalize.ts`) |
| `useDeleteConversationMutation`       | DELETE | `/chats/{id}`           | Deletes conversation + messages              |

## WebSocket (`src/features/chat/useChatWebSocket.ts`)

- Hook signature: `useChatWebSocket({conversationId, onMessageSaved})` (options object)
- URL: `ws(s)://{apiHost}/ws/chat/{conversationId}?token={token}` (scheme mirrors `API_BASE_URL`; token is the JWT from the auth store)
- Ping every 30 s (`{type: 'ping'}`); exponential backoff reconnect, max 30 s, max 5 attempts
- Pending messages live in a **single-slot ref** (`pendingMessageRef`), overwritten per turn — one unsent frame at most (message or similar request), flushed on `open`. Not a queue.
- Close code `4001` means intentional close (auth rejected server-side): no reconnect, status goes `closed`. Any other close schedules a retry.
- Reconnect paths besides backoff: an `AppState` listener reconnects when the app returns to the foreground with a dead socket (attempts reset), and `retryConnect()` is exposed for manual retry (used by the connection-lost banner).
- A stored JWT is required — without one the hook sets status `closed` and never connects. Anonymous sessions exist server-side (`POST /chat/anonymous-session`, 10-minute token) but this app does not support them.

### Client → server frames

| Frame             | Payload                                                                     | Purpose                                  |
| ----------------- | --------------------------------------------------------------------------- | ---------------------------------------- |
| `send_message`    | `{content, idempotency_key, include_saved_message: true}`                   | Send a user message (built by `sendMessageFrame`) |
| `similar_request` | `{product_id, product_name, idempotency_key, include_saved_message: true}`  | Ask for similar products (built by `sendSimilarRequestFrame`) |
| `ping`            | —                                                                           | Keepalive (30 s)                         |

Frames carry **no locale field** — locale travels only in the `POST /chats` HTTP body.

### Server → client frames (handled in `useChatWebSocket.ts`)

| Frame            | Payload                                                    | Effect                                        |
| ---------------- | ---------------------------------------------------------- | --------------------------------------------- |
| `assistant_start`| `{search_context}`                                         | Dispatches reducer `start` — sets intent, drives bubble theming |
| `debug`          | `{…}`                                                      | Attaches debug trace (chat debug view); stashed so it survives until `assistant_start` |
| `text_chunk`     | `{delta}`                                                  | Appends to assistant message content (reducer `chunk`) |
| `product_cards`  | `{products, locale?}`                                      | Replaces the product grid (reducer `products`) |
| `message_saved`  | persisted `message` (normalized)                           | Calls `onMessageSaved` and dispatches reducer `completed`; it does **not** clear the pending slot (that happens on the send success paths) |
| `assistant_end`  | —                                                          | Marks message complete (reducer `completed`)  |
| `error`          | `{code, message?}`                                         | Marks stream failed with the error code (reducer `failed`); **unknown codes fall back to `chat_failed`** |

There is **no `failed` wire frame** — failure derives from the `error` frame. Backend `error` frames may carry an optional human-readable `message` next to `code`; the app currently ignores it and relies on the `CHAT_ERROR_CODES` map plus the `chat_failed` fallback.

Error codes come from `CHAT_ERROR_CODES` (`src/features/chat/chatStream.ts`) — 13 codes matching the web UI (`chat_failed`, `chat_limit_reached`, `conversation_closed`, `conversation_not_found`, `chat_not_available`, `embedding_failed`, `product_not_found`, `chat_engine_failed`, `empty_content`, `message_too_large`, `missing_product_id`, `invalid_frame`, `unsupported_frame`).

## Error intent & retry

- The server can stream an `error` frame (e.g. `embedding_failed` when the embedder pre-flight fails, or `chat_failed` when the engine stream dies). The stream is marked `failed` with the error code (unknown codes become `chat_failed`) and the bubble shows the localized failure text from the `error` namespace — it stays visible even after `message_saved` for the failed turn.
- Failed turns are persisted by the API with the error code and `search_context.intent = "error"`; history renders them as error bubbles (`MessageBubble` shows the localized error text + a retry button when `message.error` is set or the intent is `error`).
- `onMessageSaved` (HomeScreen) invalidates the `['chats']` and messages queries, so each saved message merges into history and the stream bubble retires once history shows it.
- **Retry semantics** (matches web UI):
  - Live failed turn (stream bubble): retry re-sends the **same frame kind with the SAME idempotency key** for messages (the API dedupes via `find_by_idempotency_key` and re-runs the engine without duplicating the user message); similar requests retry with a fresh key.
  - History-loaded failed turns: the API does not expose `idempotency_key` on saved messages, so retry re-sends the preceding user message content as a new turn with a fresh key.

## Find-similar products

1. User taps the "similar" action on a product card in the grid (`ProductGrid`).
2. `useChatWebSocket.sendSimilarRequest(productId, idempotencyKey, productName)` builds a `similar_request` frame with its own `idempotency_key` (sent immediately, or parked in the pending slot if the socket is down).
3. Server answers by streaming a new assistant message: `assistant_start` → `text_chunk`s → `product_cards` (the similar items) → `assistant_end` / `message_saved`. The result appears as a normal message bubble with its own product grid.

## Intent theming (`src/features/chat/intent.ts`)

`intentTheme(intent)` maps the server-provided `search_context.intent` (`greeting` / `search` / `general` / `error`) to colors used by `MessageBubble` and the "thinking" indicator. The `error` intent uses the theme's error container colors with an alert icon. The bubble also shows a product-name chip when the message carries one (locale-aware via `locale.ts`).

## Locale & idempotency (`src/features/chat/locale.ts`)

- `localeValue()` picks the localized product **name** for outgoing similar requests — HomeScreen feeds it `name_ar`/`name_fa`/`name_en` (falling back to `name`) based on the active i18n language. Outgoing WS frames carry no locale themselves.
- `newIdempotencyKey()` returns a `randomUUID()` — one per send, so reconnects never double-post.

## Testing chat code

- Reducer tests: `src/features/chat/__tests__/chatStream.test.ts` (frame → state transitions).
- WS hook tests: `__tests__/` RNTL suites mock the `WebSocket` global and drive frames through `onMessage`.
