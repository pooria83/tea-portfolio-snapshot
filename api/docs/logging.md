# Logging Architecture

## Overview

Both the API and AI Engine use **Loguru + Rich** for structured logging with automatic **context var injection** (`request_id`, `user_id`, `source`) on every log line. All stdlib loggers (SQLAlchemy, uvicorn, httpx, etc.) are intercepted and routed through Loguru — no raw stdlib format output escapes.

## Shared Pattern

Both projects share the same logging architecture (`app/core/logging.py`):

| Component | Purpose |
|---|---|
| `request_id_var` | `ContextVar[str]` — correlation ID per request/task |
| `user_id_var` | `ContextVar[str]` — authenticated user ID |
| `log_source_var` | `ContextVar[str]` — source tag: `"anonymous"`, `"authenticated"`, `"system"` |
| `_pii_filter()` | Loguru filter — redacts PII fields (`email`, `password`, `token`, `secret`, `authorization`, `cookie`, `api_key`, `api-key`, `apikey`, `jwt`) from `record["extra"]` |
| `_inject_context()` | Loguru patcher — injects current context vars into every Loguru record's `extra` dict |
| `_ContextCaptureFilter` | Logging Filter — captures context vars onto `LogRecord.__dict__` before the handler runs, providing a fallback for context loss scenarios |
| `_InterceptHandler` | Logging Handler — routes all stdlib `LogRecord`s through Loguru with context fallback |
| `suppress_stdlib_logging()` | Clears handlers from ALL existing loggers, sets `propagate=True`, adds `_InterceptHandler` + `_ContextCaptureFilter` to root |
| `setup_logging()` | One-time init: removes default Loguru handler, configures patcher, calls `suppress_stdlib_logging()`, adds RichHandler (dev) or JSON handler (prod) |

### Log Format

All log lines follow this layout:

```
{time} | {level} | {name}:{function}:{line} | {message} | {extra}
```

The `{extra}` field contains the bound context vars:

```json
{"request_id": "abc-123", "user_id": "user-uuid", "source": "authenticated"}
```

### Setup Modes

```python
setup_logging(debug=True)   # RichHandler — colorful, human-readable (development)
setup_logging(json=True)    # JSON lines, single-line per record (production / Loki)
```

## Context Var Lifecycle

### Per-Request (HTTP)

```
uvicorn creates asyncio task
    │
    ▼
RequestIDMiddleware.__call__        ← prefers inbound X-Request-Id header,
    ├── request_id_var.set(inbound or new uuid)   else generates a UUID
    ├── user_id_var.set("")
    ├── log_source_var.set("anonymous")
    │
    ▼
[inner app runs... eventual route handler]
    │
    ▼
Auth dependency (get_current_user / get_jwt_user / get_api_key_user)
    ├── user_id_var.set(user.id)
    ├── log_source_var.set("authenticated")
    │
    ▼
[response flows back]
    │
    ▼
PrometheusMiddleware.on_start()     ← fires inside send() wrapper
    ├── logger.info("http_request", ...)  ← sees user_id + source="authenticated"
    │
    ▼
uvicorn.access logger               ← fires inside send()
    ├── sees user_id + source="authenticated"
```

**Key invariant**: Because all middlewares are raw ASGI (no `BaseHTTPMiddleware`), the entire request-response cycle runs in a **single asyncio task**. Context vars set anywhere in the chain are visible everywhere, including `send()` callbacks and the uvicorn access log.

### Background Tasks (System)

```python
# In product_ai_cron.py and embedding_cron.py:
log_source_var.set("system")
```

System processes set `source="system"` at the start of their main loop. All subsequent logs inherit this tag.

### WebSocket

```python
# In ws.py handler:
user_id_var.set(payload.sub)
log_source_var.set("authenticated")
request_id_var.set(f"ws_{payload.sub}")
```

WebSocket connections set context vars at connection time. All logs during the WebSocket session inherit the user context.

## Stdlib Interception

### How It Works

1. `suppress_stdlib_logging()` clears all handlers from every registered stdlib logger and sets `propagate=True`
2. A single `_InterceptHandler` is added to `logging.root`
3. A `_ContextCaptureFilter` is attached to the handler — it runs in the caller's task context, so it captures the correct context vars onto each `LogRecord`
4. In `_InterceptHandler.emit()`, context vars are read: first from `contextvars` (current task), then falling back to `getattr(record, ...)` (captured by the filter)
5. All loggers (SQLAlchemy, uvicorn, httpx, etc.) propagate to root → intercepted handler → Loguru

### Affected Loggers

**API** (`suppress_stdlib_logging()` + silenced to WARNING):
- `httpx`, `httpcore`, `aiormq`, `aio_pika`, `sqlalchemy.engine`

**AI Engine** (`suppress_stdlib_logging()` + silenced to WARNING):
- `httpx`, `qdrant_client`, `sqlalchemy.engine`

### Double-Logging Prevention

`suppress_stdlib_logging()` is called **after** `create_async_engine(echo=True)` to catch lazy `sqlalchemy.engine.Engine` loggers that are created on first connection. The call:
- Clears all existing logger handlers
- Sets `propagate = True` on all loggers
- Removes all handlers from `logging.root`
- Adds the single `_InterceptHandler`

This ensures only Loguru outputs log messages — never raw stdlib formatting.

## Middleware Stack (API)

The middleware order (outermost first) ensures context vars are set before any downstream code runs:

```
ActivityLoggerMiddleware   ← outermost: captures bodies, fires log_activity()
  └── RequestIDMiddleware    ← sets request_id (inbound X-Request-Id or new uuid), user_id="", source="anonymous"
        └── PrometheusMiddleware  ← on_start logs http_request with context vars
              └── SecurityHeadersMiddleware
                    └── RestrictDocsMiddleware
                          └── ShutdownCheckMiddleware
                                └── CORSMiddleware
                                      └── app (routes, auth, services)
```

**Critical design note**: `@app.middleware("http")` decorators create `BaseHTTPMiddleware` instances which spawn the inner app in a **separate anyio task**. Context vars set inside this subtask do NOT propagate back to the outer task where `send()` fires. We therefore replaced all `@app.middleware("http")` decorators with raw ASGI middleware classes (`ShutdownCheckMiddleware`, `RestrictDocsMiddleware`) to keep everything in a single task.

## Middleware Stack (AI Engine)

```python
LogContextMiddleware       ← reads X-Request-Id / X-User-Id from forwarded headers
  └── app (routers)
```

## Cross-Service Context Propagation

```
API Request
    │
    ▼
RequestIDMiddleware         ← generates request_id
Auth dependency             ← sets user_id + source="authenticated"
    │
    ▼
AIEngineClient.chat_conversational_stream(query, request_id=..., user_id=...)
    │
    ▼
_forward_headers()          ← adds X-Request-Id, X-User-Id headers
    │
    ▼
HTTP POST to AI Engine /chat
    │
    ▼
LogContextMiddleware         ← reads X-Request-Id → request_id_var
                              reads X-User-Id → user_id_var + source="authenticated"
```

The `AIEngineClient` forwards context headers on every outbound request. All AI Engine routers pass `request_id` through to the client methods. The AI Engine's `LogContextMiddleware` consumes these headers and sets local context vars.

## Log File Locations

| Environment | Config | Format | Target |
|---|---|---|---|
| Development | `debug=True` | Rich (colorized) | stderr via RichHandler |
| Production | `json=True` | Single-line JSON | stderr (collected by Docker/journald → Loki) |

## Log Levels Per Component

| Logger | Level (dev) | Level (prod) |
|---|---|---|
| App code (Loguru) | DEBUG | INFO |
| SQLAlchemy engine | DEBUG (echo=True) | WARNING |
| httpx | WARNING | WARNING |
| httpcore | WARNING | WARNING |
| aiormq / aio_pika | WARNING | WARNING |
| qdrant_client (AI Engine) | — | WARNING |

## Common Gotchas

### Double Logging

If you see log lines in both Loguru's format AND raw stdlib format (e.g., `2026-07-30 09:05:35 INFO sqlalchemy.engine.Engine ...`), `suppress_stdlib_logging()` is running too early — before lazy loggers are created.

**Fix**: Move `suppress_stdlib_logging()` to after `create_async_engine(echo=True)`:

```python
engine = create_async_engine(url, echo=True)
suppress_stdlib_logging()  # catches sqlalchemy.engine.Engine created lazily
```

### Missing Context Vars in Access Log

If uvicorn access logs show `{}` or missing `request_id`/`user_id`, the context vars are being set in a different task than where `send()` fires. This happens when `BaseHTTPMiddleware` (from `@app.middleware("http")`) is between `RequestIDMiddleware` and the app.

**Fix**: Use raw ASGI middlewares instead of `@app.middleware("http")` decorators. Ensure `RequestIDMiddleware` is the outermost middleware (registered last via `add_middleware`, which uses `insert(0, ...)`).

### Context Vars After `finally` Reset

Context vars persist for the lifetime of the asyncio task. Do NOT reset them in a `finally` block — each request runs in its own task, so old values are overwritten at the start of the next request.

## Testing Logging

The test suite validates:
1. `setup_logging()` initializes without errors
2. `suppress_stdlib_logging()` captures stdlib loggers
3. PII redaction (`_pii_filter`) masks sensitive fields
4. Context vars are injected into log records
5. JSON mode produces valid single-line JSON

Key test file: `tests/test_logging.py`

---

## Activity Logging System

The API includes an optional **activity logging subsystem** that records every HTTP request, background cron cycle, and script execution to a dedicated `activity_logs` PostgreSQL table, and simultaneously emits the same data as structured Loguru log lines for Grafana/Loki ingestion.

### Architecture

```
HTTP Request / Cron / Script
        │
        ▼
ActivityLoggerMiddleware  (or direct log_activity() call)
        │
        ├── Captures request body + response body (ASGI receive/send wrappers)
        ├── PII-filters bodies (redacts api_key, token, password, etc.)
        ├── Reads _activity dict from scope (set by routes/exception handlers)
        │
        ├──▸ loguru.log(level, "activity_log", ...)    ← console → stderr → Loki
        │     17 structured fields bound as extra
        │     Level: INFO (<400), WARNING (400-499), ERROR (500+)
        │
        └──▸ asyncio.ensure_future(log_activity(...))  ← fire-and-forget DB write
               INSERT INTO activity_logs (...)
```

### Components

| File | Purpose |
|---|---|
| `app/core/activity_logger.py` | `ActivityLoggerMiddleware`, `log_activity()` function, PII filter, helpers |
| `app/models/activity_log.py` | `ActivityLog` SQLAlchemy model (20 columns + `TimestampMixin`) |
| `app/services/activity_log_cleanup.py` | `cleanup_activity_logs()` — deletes rows older than 60 days |
| `app/api/v1/*.py` (routes) | Set `scope["_activity"]` with `action`, `resource_type`, `resource_id`, `message` |
| `app/core/exception_handlers.py` | All 4 handlers (`app_error_handler`, `auth_error_handler`, `validation_error_handler`, `global_exception_handler`) call `_get_activity()` to populate `_activity` with error details |

### ActivityLog Model (`app/models/activity_log.py`)

Column layout (20 data columns + `created_at`/`updated_at`):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `actor_type` | str | `user`, `system`, `script` |
| `actor_id` | str | nullable |
| `action` | str | `CREATE`, `UPDATE`, `DELETE`, `READ`, etc. |
| `resource_type` | str | nullable — `store`, `product`, `user`, `auth`, `file`, etc. |
| `resource_id` | str | nullable |
| `message` | str | nullable — human-readable description |
| `details` | JSONB | nullable — arbitrary metadata |
| `status_code` | int | HTTP status or 0 for non-HTTP |
| `error_code` | str | nullable — `UNKNOWN` or domain error code |
| `translation_key` | str | nullable — i18n key for frontend |
| `error_message` | str | nullable |
| `request_body` | text | nullable — only stored when `status_code >= 400` |
| `response_body` | text | nullable — only stored when `status_code >= 400` |
| `ip_address` | str | nullable |
| `request_id` | str | nullable — correlation ID |
| `user_agent` | str | nullable |
| `duration_ms` | int | nullable |
| `path` | str | nullable |
| `method` | str | nullable |

### Migration

File: `alembic/versions/569ab8dcb5ee_add_activity_logs_table.py`

```python
op.create_table("activity_logs", ...)
```

Migration has been applied to the dev database.

### Middleware: ActivityLoggerMiddleware

Registered in `main.py` after `RequestIDMiddleware`:

```python
app.add_middleware(ActivityLoggerMiddleware)
```

Behaviour:

1. Wraps `receive` to capture request body chunks (capped at 64 KiB per direction via `BODY_CAPTURE_LIMIT`)
2. Wraps `send` to capture response body chunks and status code
3. Initialises `scope["_activity"] = {}` for route/exception handler enrichment
4. After response: decodes bodies, applies PII filter, resolves the client IP (first hop of the `X-Forwarded-For` header, falling back to the ASGI `client`), calls `log_activity()` (fire-and-forget)
5. On exception: sets `status_code = 500` if not set, then re-raises (no log — exception handler logs instead)

### Middleware Stack

`ActivityLoggerMiddleware` is registered last in `main.py`, which makes it the **outermost** middleware (see [Middleware Stack (API)](#middleware-stack-api) above for the full order).

### Exception Handler Integration

All four exception handlers (`app/core/exception_handlers.py`) use the `_get_activity()` helper to populate `scope["_activity"]` with `error_code`, `error_message`, and `status_code`:

```python
def _get_activity(request: Request) -> dict[str, object]:
    scope = getattr(request, "scope", {}) or {}
    activity: dict[str, object] = scope.get("_activity", {})
    return activity
```

This ensures that when the middleware fires `log_activity()` in the `finally` block, it sees the error details set by the exception handler.

### Route Enrichment Pattern

Mutating endpoints set human-readable activity metadata directly on `scope["_activity"]`:

```python
activity = request.scope.get("_activity")
if isinstance(activity, dict):
    activity["action"] = "UPDATE"
    activity["resource_id"] = product.id
    activity["resource_type"] = "store_product"
    activity["message"] = f"user {user.id} update product {product.id}"
```

Enriched routes:
- `stores.py` — CRUD, member management
- `product_definition.py` — product CRUD, image management
- `users.py` — profile updates
- `auth.py` — login, registration, OTP
- `files.py` — file upload
- `admin/llm.py` — API key management
- `admin/prompt_templates.py` — prompt template updates
- `admin/system_settings.py` — settings updates

### Cron / Script Logging

Non-HTTP activity is logged via `log_activity()` calls in:

- `product_ai_cron.py` — after each 300s cycle
- `embedding_cron.py` — after each 60s cycle
- `scripts/run_cron.py` — at end of manual run
- `scripts/run_embedding_backfill.py` — at end of backfill

### Console Log Integration

Every `log_activity()` call also emits a structured Loguru log line:

```python
logger.opt(depth=1).log(
    log_level,
    "activity_log",
    actor_type=actor_type,
    actor_id=actor_id,
    action=action,
    resource_type=resource_type,
    resource_id=resource_id,
    message=message,
    details=details,
    status_code=status_code,
    error_code=error_code,
    translation_key=translation_key,
    error_message=error_message,
    ip_address=ip_address,
    request_id=request_id,
    user_agent=user_agent,
    duration_ms=duration_ms,
    path=path,
    method=method,
)
```

Log level depends on `status_code`:
- `< 400` → `INFO`
- `400–499` → `WARNING`
- `500+` → `ERROR`

When `json=True` (production), these appear as single-line JSON in stderr with all 17 fields in the `extra` dict, queryable in Grafana/Loki via log label matchers.

### Cleanup Task

A background task `run_activity_log_cleanup()` runs every 24 hours (registered in `main.py` `_startup()`):

```python
async def run_activity_log_cleanup(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(86400)  # 24h
        async with async_sessionmaker(...)() as db:
            await cleanup_activity_logs(db, retention_days=60)
```

Deletes rows where `created_at < now() - interval '60 days'`.

### AI Engine — JSONL Logger

The AI Engine does not have access to the PostgreSQL `activity_logs` table. Instead, it has its own JSONL-based logger (`app/core/activity_logger.py`):

- `ActivityLoggerMiddleware` — same ASGI body capture pattern, but writes to a per-day JSONL file instead of DB
- Config: `ACTIVITY_LOG_DIR` env var (default `./logs`)
- File: `{log_dir}/ai_engine_activity_{YYYY-MM-DD}.jsonl`
- One JSON object per line, same structure as the DB model minus DB-specific fields
- Bodies included only for status >= 400
- Registered in `main.py`: `app.add_middleware(ActivityLoggerMiddleware, log_dir=settings.activity_log_dir)`
