# Logging

The AI Engine uses **loguru** for structured logging, shares the same
architecture as the backend API, and adds request-context propagation via
middleware.

## 1. Setup — `app/core/logging.py`

`setup_logging(*, debug=False, json=False)` is called once in the lifespan:

1. `logger.remove()` — drop default sinks.
2. `logger.configure(patcher=_inject_context)` — context vars injected into every record.
3. `suppress_stdlib_logging()` — stdlib loggers are intercepted and routed
   through loguru (see §3).
4. Sink: `RichHandler` (human, default) or JSON-serialized to stderr (`json=True`).
5. `httpx`, `qdrant_client`, `sqlalchemy.engine` silenced to WARNING.

Format:

```
{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | {level:<8} | {name}:{function}:{line} | {message} | {extra}
```

## 2. Context vars & middleware

`app/core/middleware.py` — `LogContextMiddleware`:

| Header | ContextVar | Extra field |
|---|---|---|
| `X-Request-Id` | `request_id_var` | `request_id` |
| `X-User-Id` | `user_id_var` | `user_id` |
| `X-User-Id` present | `log_source_var = "authenticated"` | `source` |

The API forwards these headers on every call. When a header is **absent** the
engine now generates a fallback id (`req-<hex>` / `anon-<hex>`), so every
request always has a `request_id` and `user_id` — no more empty extras. Both
values are also stored on `scope["state"]` (`request.state.request_id` /
`request.state.user_id`) for routers that need them. Ids are **always on** and
appear in every trace line, even on raw `curl` calls.

## 3. Stdlib interception

- All stdlib loggers have their handlers removed and propagate to root.
- Root gets a single `_InterceptHandler` with a `_ContextCaptureFilter`.
- `_InterceptHandler.emit` binds request/user/source context and logs via
  loguru with `opt(depth=6, exception=record.exc_info)` so caller paths and
  tracebacks survive.
- **Known fix:** uvicorn's `logging.config.dictConfig()` resets the root level
  to WARNING and would suppress `logger.info()` — `suppress_stdlib_logging()`
  must run after engine creation (it does, in the lifespan).

## 4. PII redaction

`_pii_filter` scrubs extra keys whose **name** contains any of:
`email, password, token, secret, authorization, cookie, api_key, api-key, apikey, jwt` →
replaced with `[REDACTED]`.

Activity logs use a stronger recursive redaction (`***REDACTED***`) — see
[Activity Logging](activity-logging.md).

## 5. Always-on chat/similar trace (INFO)

Every `/chat` request (greeting, general, search) and `/similar` request emits
a full hop-by-hop trace at **INFO** (no toggle, no env flag), tagged by type
and correlated by `request_id`/`user_id`:

| Hop | Prefix | Info logged |
|---|---|---|
| Request entry | `TRACE_CHAT_START` | `request_id`, `user_id`, `query`, `locale`, `history`, `summary_len`, `stream` |
| Intent | `TRACE_CHAT intent=` | `greeting` / `general` / `search` |
| Per type | `TRACE_CHAT type=` | `greeting`, `general`, or `search` + `specs`/`tool_used`/`direct` |
| Prompt sent | `LLM_REQUEST` | full serialized, PII-redacted request payload |
| LLM reply | `LLM_RESPONSE` / `LLM_STREAM_*` | full serialized, PII-redacted response |
| Embedder | `TRACE_EMBED` | `mode` (query/passage/batch), `model`, `text_len`, `text`, `dim`, `norm`, `head` (first ~5 values) |
| Qdrant | `TRACE_QDRANT_HITS` | collection, query vector stats (`dim`/`norm`/`head` or `ref_id`), filter, requested limit, and every returned hit `id`, `name`, `brand`, `price`, `color_family`, `score` |
| Similar scroll | `TRACE_SIMILAR_SCROLL` | product_id, lang, matched points, chosen reference, categories, color families |
| Similar final | `TRACE_SIMILAR_RESULTS` | reference, product_id, count, ranked hits |
| Chat end | `TRACE_CHAT_END` | `type`, `products` count, `answer_len` |
| Similar end | `TRACE_SIMILAR_END` | `product_id`, `count` |

All hops share one `request_id`/`user_id` per request (see §2). For example a
search query yields, in order:

```
TRACE_CHAT_START request_id=... user_id=... query=red dress ...
TRACE_CHAT intent=search
TRACE_CHAT type=search specs=1 tool_used=False direct=False
LLM_REQUEST model=... payload=...
LLM_RESPONSE model=... response=...
TRACE_EMBED mode=query model=... text_len=9 text=red dress dim=1024 norm=1.0 head=[...]
TRACE_QDRANT_HITS collection=products-qwen3... query=dim=1024 ... count=3 hits=id=p1 name=... score=0.8, ...
TRACE_CHAT_END type=search products=3 answer_len=184
```

Note: this means prompts, model replies, and returned product metadata are
logged in full at INFO for every request.

## 6. Log prefixes used across the codebase

Stable prefixes make logs greppable:

| Prefix | Source |
|---|---|
| `LLM_REQUEST` / `LLM_RESPONSE` / `LLM_FAILED` / `LLM_STREAM_*` | `llm_client.py` (full request/response payloads, INFO) |
| `TRACE_CHAT_*` | `chat.py` (request/intent/type/end per chat type) |
| `ROUTER_INTENT` / `ROUTER_GREETING` | `chat.py` (conversation-router verdict) |
| `PREFLIGHT_EMBEDDER_DOWN` / `PREFLIGHT_LLM_DOWN` | `chat.py` (advisory pre-flight probes; probe failures log `ping_failed` from `core/health.py`) |
| `DIRECT_ANSWER` / `TOOL_DIRECT_ANSWER` / `PLAIN_STREAM_FAILED` | `chat.py` |
| `EVAL_QUERIES*` | `llm_client.py`, `eval.py` |
| `TRACE_SIMILAR_*` | `similar.py` + `rag.py` |
| `TRACE_EMBED` | `embedding_client.py` |
| `TRACE_QDRANT_HITS` / `TRACE_QDRANT_HITS_HYBRID` | `rag.py` (dense / hybrid prefetch pools) |
| `ENGINE_AUTH_REJECTED` | `core/auth.py` (`X-API-Key` guard, before the 401 response) |
| `CHAT START` / `CHAT END` | `chat.py` |
| `TOOL_*` / `LLM_PARSE` | `chat.py` search resolution |
| `EMBED_*` / `SEARCH_*` | `chat.py`, `rag.py` |
| `GEN_DESC` / `GEN_RAW` / `PARSE_QUERY` / `CONTEXT_CHAT` / `SUMMARIZE` / `TITLE` | `llm_client.py` retry labels |
| `RECEIVED embed request` / `Embedding product` | `embed.py` |
| `Bootstrap:` | `main.py` |
| `Config applied:` | `config.py` |

## 7. Testing

`tests/test_logging.py`, `tests/test_middleware.py`, and
`tests/test_trace_logging.py` cover context injection, stdlib interception,
the PII filter, the always-on fallback ids, and the full trace chains for
search/greeting/general/similar (see [Testing](testing.md)).
