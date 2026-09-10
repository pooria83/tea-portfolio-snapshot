# Activity Logging (JSONL)

The AI Engine writes a per-day JSONL audit/activity log for every HTTP request
— no database involved. Bodies are only persisted for failing requests and are
PII-redacted.

## 1. Architecture — `app/core/activity_logger.py`

`ActivityLoggerMiddleware` is an ASGI middleware registered in `main.py`
**last**, and Starlette's `add_middleware` **prepends**, so the effective
onion (outermost first) is:

```
ActivityLoggerMiddleware        ← outermost user middleware: captures bodies, writes JSONL
  └── EngineAuthMiddleware      ← X-API-Key guard (its 401 responses ARE captured)
        └── LogContextMiddleware ← reads X-Request-Id / X-User-Id into contextvars
              └── app (routers)
```

(Registration order in `main.py` is LogContext → EngineAuth → ActivityLogger;
each `add_middleware` call wraps everything registered before it.)

Behavior:

1. Wraps `receive`/`send` to capture request + response body chunks in memory.
2. Times the request (`time.monotonic`).
3. On normal completion writes one JSONL line **fire-and-forget**
   (`asyncio.ensure_future(_write_jsonl(...))`) — the executor does the sync
   file write, so request latency is unaffected.
4. **Unhandled exceptions produce NO JSONL line**: the middleware's
   `except BaseException` sets a fallback status and marks the request as
   logged, then re-raises *before* any write — Starlette's
   `ServerErrorMiddleware`, which sits above this middleware, converts the
   exception into the 500 response. Only responses that flow back through the
   middleware (including EngineAuth's 401s) are captured.

## 2. Sensitive data handling

| Layer | Rule |
|---|---|
| Log names | `_pii_filter(record)` in `core/logging.py` — redacts extras by key name |
| Activity bodies | `_pii_filter(body)` here — if the body contains a sensitive keyword, it is parsed and **recursively** redacted: every dict key matching `SENSITIVE_KEYWORDS` becomes `"***REDACTED***"`. Non-JSON bodies that trip a keyword are replaced entirely. |

`SENSITIVE_KEYWORDS`: `password, token, secret, authorization, api_key,
api-key, apikey, jwt, refresh_token, access_token, webhook_url, webhook-url`.

Bodies are **only** written when `status_code >= 400`.

## 3. Entry structure

```json
{
  "timestamp": "2026-07-30T12:00:00.000Z",
  "request_id": "req-...",
  "user_id": "usr-...",
  "method": "POST",
  "path": "/chat",
  "status_code": 200,
  "duration_ms": 1234,
  "resource_type": "chat",
  "action": "CREATE",
  "error_code": null,
  "error_message": null,
  "ip_address": "192.0.2.10",
  "user_agent": "Mozilla/5.0 ..."
}
```

For `status_code >= 400` the entry additionally includes:

```json
{
  "request_body": "{\"query\": \"...\"}",
  "response_body": "{\"detail\": \"...\"}"
}
```

## 4. Resource types & actions

`infer_resource_type(path)` maps by prefix:

| Path prefix | Resource type |
|---|---|
| `/generate-description` | `description` |
| `/chat` | `chat` |
| `/embed-product` | `embed` |
| `/config` | `config` |
| `/health` | `health` |
| anything else | `null` |

Actions come from the HTTP method: `GET → READ`, `POST → CREATE`,
`PUT/PATCH → UPDATE`, `DELETE → DELETE` (unknown methods fall back to
`"UNKNOWN"`). Routers can override the inferred values per request by writing
`scope["_activity"]` (`action`, `resource_type`, `error_code`,
`error_message`) before returning — explicit entries win, and for
`status_code >= 400` an empty `error_message` falls back to the captured
response body.

## 5. File layout

| Setting | Default | Meaning |
|---|---|---|
| `ACTIVITY_LOG_DIR` | `./logs` | Directory (auto-created, mode `0o700`; files opened mode `0o600` via a restricted opener) |
| file name | `ai_engine_activity_{YYYY-MM-DD}.jsonl` | One file per UTC date |

Docker: mount `/data/logs` or a persistent volume so logs survive restarts.
**Known limitation: there is no retention/cleanup job** — the directory grows
unbounded (one new file per UTC day, nothing ever deleted); rotate or prune
externally.

## 6. Notes

- Non-HTTP scopes (websockets) are passed through untouched.
- Write failures are logged as `jsonl_write_failed` and never crash the request.
- The client IP is taken from the **first hop** of `X-Forwarded-For`
  (comma-split, leftmost entry) when present, else the ASGI `client` address;
  `user_agent` comes from the request header verbatim.
- Tests: `tests/test_activity_logger.py` — PII filter, resource-type inference,
  middleware integration (17 tests).
