# Testing

How the test suite works: what it requires, what gets mocked, how CI runs it, and the conventions every new test must follow.

## Requirements

- **PostgreSQL 16 is mandatory.** The session fixture builds the full schema (`Base.metadata.create_all`) plus seed rows for `countries` and `currencies` on a real PostgreSQL 16 server.
- Two ways to provide it (see `tests/conftest.py:56-75`):
  - **testcontainers** (default): when `TEST_DATABASE_URL` is unset, a `PostgresContainer("postgres:16-alpine")` is started for the whole session and torn down at the end.
  - **`TEST_DATABASE_URL` env var**: when set, no container is started and the suite connects directly to that DSN (asyncpg driver).
- `aiosqlite` remains in dev dependencies but is **legacy-only** — there is no SQLite path in the current conftest; do not rely on it.

## What's mocked

Everything except PostgreSQL is mocked in-process. The `client` fixture wires each fake into `app.state` / dependency overrides, then clears them afterwards:

| Dependency | Mechanism | Wiring |
|---|---|---|
| MongoDB | `mongomock-motor` `AsyncMongoMockClient` (session-scoped) | `app.state.mongo_db = SimpleNamespace(db=mongo_client[settings.mongo_db_name])` |
| Redis | Plain `AsyncMock` backed by an in-process dict — implements `incr`, `get`, `set(nx=…)`, `setex`, `getdel`, `delete`, `exists`, `expire`, `scan_iter`, `ping`; `eval` raises `NotImplementedError` | dependency override of `get_redis` + `app.state.redis` |
| AI Engine | `AsyncMock(spec=AIEngineClient)` with `health.return_value = True` | `app.state.ai_client` |
| RabbitMQ | `AsyncMock(spec=Broker)` with mock `channel.default_exchange` and `is_connected → True` | `app.state.broker` |
| WebSocket manager | Real `ConnectionManager()` (no external state) | `app.state.ws_manager` |
| DB session | Dependency override of `get_db` yielding the shared `db_session` | `app.dependency_overrides` |

At import time conftest also pins settings for determinism: test `api_key`/secrets, `debug=True`, empty Google client IDs, and a **fresh Fernet key per run** (`settings.llm_encryption_key = Fernet.generate_key().decode()` + `_crypto._cipher = None`) so LLM-key tests never depend on a persisted encryption key.

## Running tests

```bash
make test        # uv run pytest (785+ tests)
make test-cov    # + HTML coverage report
```

### Local fast path (mirrors CI)

CI runs on the self-hosted `tea-server` runner which already hosts Docker stacks, so default ports can't be claimed. It starts dedicated containers on the host network with non-default ports and hands the Postgres one to pytest via `TEST_DATABASE_URL` (which skips testcontainers entirely):

```bash
docker rm -f test-pg 2>/dev/null || true
docker run -d --network host --name test-pg \
  -e POSTGRES_DB=product_graph -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
  postgres:16-alpine -p 55432
for i in $(seq 1 30); do docker exec test-pg pg_isready -p 55432 -U postgres >/dev/null 2>&1 && break; sleep 1; done

export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:55432/product_graph
export DATABASE_URL=$TEST_DATABASE_URL
make test
docker rm -f test-pg   # cleanup
```

The same pattern applies to Redis in CI (`--network host`, port `56379`, exported as `REDIS_URL`) even though unit tests mock Redis internally.

### Running subsets

Plain pytest path/kwd selection works as usual:

```bash
uv run pytest tests/test_auth.py                       # single file
uv run pytest tests/test_admin_search_eval.py -k metrics
uv run pytest tests/api/v1                             # subdirectory
```

## pytest configuration (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_test_loop_scope = "session"
asyncio_default_fixture_loop_scope = "session"
testpaths = ["tests"]
addopts = "-v --cov=app --cov-report=term-missing --cov-fail-under=60"
```

- **Session-scoped event loop** for both tests and fixtures — all async fixtures/tests share one loop so the session-scoped engine/container work.
- **Coverage gate baked into `addopts`**: every bare `pytest` run measures `app` and fails under 60% (`--cov-fail-under=60`). CI re-asserts it with `uv run pytest --cov-fail-under=60`.
- No `pytest.ini`/`setup.cfg` — the block above is the only configuration source.

## CI integration (`.github/workflows/ci.yml`)

The `quality` job (self-hosted runner): install deps via `uv sync --extra dev` → start `test-pg`/`test-redis` containers with readiness polling → `ruff check` → `ruff format --check` → `mypy app/` → `pytest --cov-fail-under=60` with `TEST_DATABASE_URL`/`DATABASE_URL`/`REDIS_URL` env vars → **always** remove the test containers → generate and upload the OpenAPI schema artifact.

## Load tests (`tests/load/`)

A Locust scenario that registers (or logs into) a `load-test-user@loadtest.com` user, then exercises:

| Task | Weight | Request |
|---|---|---|
| `list_products` | 5 | `GET /api/v1/products/` (Bearer auth) |
| `health_check` | 3 | `GET /api/v1/health` |
| `get_metrics` | 2 | `GET /api/v1/metrics` |

```bash
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

## Test-writing conventions

- **Mock DB sessions with `AsyncMock(spec=AsyncSession)`** — a plain `AsyncMock` breaks synchronous calls like `.add()` because they become coroutine mocks. This is required across service/repository unit tests.
- API tests use the `client` fixture (`httpx.AsyncClient` over `ASGITransport`) with `auth_headers` / `admin_headers` fixtures minting real JWTs from `test_user` / `admin_user` rows; admin-only endpoints are verified against both roles.
- The database schema is created/dropped once per session around the whole run — tests share one schema, so avoid destructive global mutations (truncate what you seed if needed).
- Redis-dependent assertions should go through the mock's dict semantics (`set` honors `nx=True`, `scan_iter` matches prefixes) rather than assuming real TTL behavior.
