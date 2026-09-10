# Getting Started

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- Docker & Docker Compose (for PostgreSQL, Redis, RabbitMQ, MinIO)
- `psql` + `pg_dump` (PostgreSQL client) — for backup/restore scripts

## Setup

1. **Clone and navigate**

```bash
cd product-graph-api
```

2. **Configure environment**

```bash
cp .env.example .env
# Defaults work for local dev — edit if needed
```

3. **Install dependencies**

```bash
uv sync
```

4. **Start infrastructure**

```bash
docker compose --profile minimal up -d
```

This starts PostgreSQL, Redis, RabbitMQ, MinIO, and pgAdmin. The API runs on your host for hot-reload.

5. **Run migrations**

```bash
make migrate
```

6. **Seed sample data**

```bash
make seed
```

7. **Start development server**

```bash
make dev
```

## Verify

- API: [http://localhost:8000](http://localhost:8000)
- Swagger docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Health check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
- Readiness check: [http://localhost:8000/api/v1/ready](http://localhost:8000/api/v1/ready)
- Prometheus metrics: [http://localhost:8000/api/v1/metrics](http://localhost:8000/api/v1/metrics) (only when `DEBUG=true`)

All responses include `X-Request-ID` header for request tracing.

---

## Docker Compose Profiles

| Profile | Services | Use Case |
|---|---|---|
| `minimal` | postgres, redis, rabbitmq, minio, pgadmin, redisinsight, caddy, dnsproxy | API runs locally via `make dev` |
| `full` | Everything above + api | Fully containerized |
| `cloudflared` | dnsproxy + cloudflared | Expose local dev services via the Cloudflare Tunnel (`*.dev.portfolio.example.invalid`) |

See [Cloudflare Tunnel for Development](cloudflare-tunnel-dev.md) for the tunnel setup, adding subdomains, and troubleshooting.

### Minimal Profile (recommended for development)

```bash
docker compose --profile minimal up -d
docker compose ps                    # verify health
make migrate                         # apply migrations
make seed                            # seed sample data
make dev                             # start API with hot-reload
```

### Tunnel Profile (expose local services)

```bash
docker compose --profile minimal --profile cloudflared up -d
# API is then reachable at https://portfolio.example.invalid/api/v1
```

### Full Profile

Everything runs in Docker. Useful for integration testing or reproducing production behavior.

```bash
docker compose --profile full up -d
docker compose logs -f api           # follow logs
docker compose exec api uv run alembic upgrade head
docker compose exec api uv run scripts/seed.py
```

---

## Services Map

| Service | Port (minimal) | Port (full) | Notes |
|---|---|---|---|
| API | `8000` (host) | `8000` | FastAPI |
| PostgreSQL | `5432` | `5432` | — |
| Redis | `6379` | `6379` | — |
| RabbitMQ | `5672` / `15672` | `5672` / `15672` | Management UI on 15672 |
| MinIO API | `9000` | `9000` | S3-compatible |
| MinIO Console | `9002` | `9002` | Web UI |
| pgAdmin | `5050` | `5050` | `admin@example.com` / `admin` |
| RedisInsight | `5540` | `5540` | Redis GUI |
| Caddy | `80` / `443` | `80` / `443` | Reverse proxy |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://<REDACTED>@localhost/portfolio | Async DB connection |
| `DATABASE_URL_SYNC` | `postgresql://<REDACTED>@localhost/portfolio | Sync DB (for pg_dump, psql) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `RABBITMQ_URL` | `amqp://<REDACTED>@localhost/portfolio | RabbitMQ connection |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO endpoint |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `SECRET_KEY` | `dev-secret-key` | API secret (change in production!) |
| `MONGO_URL` | *(empty)* | MongoDB Atlas connection string for chat history — empty disables chat (503) |
| `MONGO_DB_NAME` | `tea-dev` | Mongo database name (`tea-dev` locally, `tea-production` in CI/production) |
| `LLM_ENCRYPTION_KEY` | *(empty)* | Fernet key encrypting LLM API keys at rest — must match the AI Engine's key |
| `AI_ENGINE_URL` | `http://ai-engine:8001` | AI Engine service URL |
| `MINIO_PUBLIC_URL` | `https://portfolio.example.invalid` | Public base URL prepended to relative image URLs |
| `ZARA_SCRAPER_API_BASE_URL` | `http://localhost:8000` | API base URL used by the scraper transform script |
| `ZARA_SCRAPER_STORE_ID` | — | UUID of the Zara store products are synced into |
| `ZARA_SCRAPER_API_TOKEN` | — | Long-lived JWT used by the transform script to call the API |

---

## Commands

```bash
make dev             # Start dev server (hot reload on port 8000)
make run             # Run production-style server (fastapi run --proxy-headers)
make test            # Run all tests
make test-cov        # Run tests with coverage report
make lint            # Ruff lint check
make lint-fix        # Auto-fix lint issues
make format          # Format code with ruff
make format-check    # Check formatting (CI)
make typecheck       # Mypy static type checking
make migrate         # Apply pending migrations
make migration message="description"   # Auto-generate migration
make seed            # Seed sample data
make setup           # One-time bootstrap: copy .env, install deps, migrate, seed users
make ts-types        # Generate TypeScript client types from the OpenAPI schema
make docker-build    # Build full stack via compose
make docker-build-prod  # Build production Docker image
make security        # Run pip-audit
make coverage-html   # Coverage HTML report
make precommit       # Run pre-commit hooks on all files
make clean           # Remove cache/build artifacts
```

## Testing

- **Framework**: pytest + httpx.AsyncClient (`pytest-asyncio`, `asyncio_mode = auto`)
- **Database**: real PostgreSQL 16 — required. `tests/conftest.py` starts a [testcontainers](https://testcontainers.com/) `postgres:16-alpine` container automatically; set `TEST_DATABASE_URL` to point at an existing server instead (e.g. CI does this). No SQLite.
- **MongoDB**: mocked in-process via `mongomock-motor` (`AsyncMongoMockClient`) — no Atlas needed
- **Redis**: mocked with an in-process dict-backed store built on `AsyncMock` (implements get/set/incr/delete/scan semantics)
- **Coverage gate**: `--cov-fail-under=60` is baked into the pytest `addopts` in `pyproject.toml` — any test run below 60% coverage fails

Run specific test file:

```bash
uv run pytest tests/test_auth.py -v
```

See [docs/testing.md](testing.md) for fixtures, conventions, and how to run tests against an external database.

---

## Backup & Restore

### PostgreSQL

**Backup:**

```bash
# Interactive — prompts for output path (defaults to ./backups)
bash dev-tools/backup_postgres.sh

# Non-interactive with custom path
bash dev-tools/backup_postgres.sh /path/to/output
```

Output: `./backups/product_graph_api_db_2026-07-29_120000.sql.gz`

> Uses `pv` for progress display if available.

**Restore:**

```bash
# Interactive — prompts for backup file path
bash dev-tools/restore_postgres.sh

# Non-interactive
bash dev-tools/restore_postgres.sh /path/to/backup.sql.gz
```

The script will:
1. Terminate active connections to the database
2. Drop and recreate the database
3. Restore from the compressed SQL dump

### MinIO

**Backup:**

```bash
# Interactive
bash dev-tools/backup_minio.sh

# Non-interactive with custom path
bash dev-tools/backup_minio.sh /path/to/output
```

Output: `./backups/minio_2026-07-29_120000/` with one subdirectory per bucket.

> Auto-downloads `mc` (MinIO Client) if not installed. Buckets are auto-detected.

**Restore:**

```bash
# Interactive — prompts for backup directory path
bash dev-tools/restore_minio.sh

# Non-interactive
bash dev-tools/restore_minio.sh /path/to/minio_backup_dir
```

### MongoDB Atlas (Chat History)

Requires [MongoDB Database Tools](https://www.mongodb.com/docs/database-tools/installation/) (`mongodump`/`mongorestore`). The scripts read `MONGO_URL` + `MONGO_DB_NAME` from `.env`. M0 free tier has no native backups — run the backup cron on the VPS daily.

**Backup:**

```bash
# Interactive — prompts for output path (defaults to ./backups)
bash dev-tools/backup_mongo.sh

# Non-interactive with custom path
bash dev-tools/backup_mongo.sh /path/to/output
```

Output: `./backups/tea-dev_2026-08-04_120000.archive.gz` (mongodump archive + gzip).

**Restore:**

```bash
# Interactive — prompts for backup file path + confirmation
bash dev-tools/restore_mongo.sh

# Non-interactive
bash dev-tools/restore_mongo.sh /path/to/backup.archive.gz
```

> Restores into `MONGO_DB_NAME` on the cluster in `MONGO_URL`. Requires interactive `RESTORE` confirmation.

### Qdrant

Snapshots every Qdrant collection (creates + downloads snapshots over the HTTP API) into `backups/qdrant_<timestamp>/<collection>.snapshot`. Reads `QDRANT_BACKUP_URL`/`QDRANT_URL` (default `http://localhost:6333`) and optional `QDRANT_API_KEY` from `.env`.

```bash
bash dev-tools/backup_qdrant.sh [output-dir]
```

### Local MinIO → Server Sync

Mirrors the local MinIO buckets to the server MinIO (`mc mirror`). Requires `SERVER_MINIO_ENDPOINT`, `SERVER_MINIO_ACCESS_KEY`, and `SERVER_MINIO_SECRET_KEY` in `.env`.

```bash
bash dev-tools/sync_minio_server.sh
```

### Quick Reference

| Action | Command |
|---|---|
| Backup PostgreSQL | `bash dev-tools/backup_postgres.sh` |
| Restore PostgreSQL | `bash dev-tools/restore_postgres.sh` |
| Backup MinIO | `bash dev-tools/backup_minio.sh` |
| Restore MinIO | `bash dev-tools/restore_minio.sh` |
| Backup MongoDB Atlas | `bash dev-tools/backup_mongo.sh` |
| Restore MongoDB Atlas | `bash dev-tools/restore_mongo.sh` |
| Backup Qdrant | `bash dev-tools/backup_qdrant.sh` |
| Sync local MinIO → server | `bash dev-tools/sync_minio_server.sh` |

> The full ops runbook (schedules, retention, restore drills) lives in [docs/backups-and-restore.md](backups-and-restore.md).

---

## Full Production-Like Stack

To run the full stack including the AI Engine and Web UI locally:

```bash
# Clone all repos
git clone https://github.com/TEA-assist/product-graph-api.git
git clone https://github.com/TEA-assist/product-graph-ai-engine.git
git clone https://github.com/TEA-assist/product-graph-web-ui.git

# Start infra
cd product-graph-api
docker compose --profile minimal up -d

# Start AI Engine (separate terminal)
cd product-graph-ai-engine
make dev

# Start Web UI (separate terminal)
cd product-graph-web-ui
npm run dev
```

For the full Docker Swarm deployment, see the [deployment guide](deployment.md).

---

## Code Style

- **Ruff** for linting and formatting (line length: 200)
- **Mypy strict** mode for type checking — zero errors, zero disabled error codes
- **Pydantic v2** with `ConfigDict(from_attributes=True)`, OpenAPI `examples` on fields
- **All async**, all the time — no sync DB queries, no blocking calls
- **Domain exceptions** — services raise `NotFoundError`, `AuthenticationError`, etc. Never `HTTPException`
- **PEP 695** — use type parameter syntax: `class BaseRepository[T: Base]`, `class APIResponse[T]`, `def success[T]()`
- **Repository pattern** — services talk to repositories, repositories inherit `BaseRepository[T]`
- **Correlation ID** — every request gets `X-Request-ID`; use `logger.bind(...)` (Loguru) to add custom context

## Seeding

The seed script is idempotent:

```bash
make seed
```

- Creates product types, categories, attribute groups, attributes, and options
- Attributes keyed by `code` — existing attributes are skipped
- Product-type-to-attribute links are re-created each run (via truncation)
- Shared fashion attributes linked to all fashion product types

## Migrations

Always create migrations after model changes:

```bash
make migration message="add_user_preferences_table"
make migrate
```

## Adding a New Product Type

1. Create a new JSON seed file: `scripts/seed_data/XX_attributes_<code>.json`
   - Include attributes, options, and `group_code` references
2. Register in `scripts/seed_product_definitions.py`:
   - Add entry to `PER_TYPE_ATTR_FILES` list (determines creation order)
   - Add code to `FASHION_PT_CODES` if it's a fashion type (gets shared attrs)
3. Add view types in `scripts/seed_data/04_image_view_types.json`
4. Add categories in `scripts/seed_data/03_categories.json`
5. Run `make seed`

**Attribute code uniqueness**: All attribute codes must be globally unique. If a shared attribute code (e.g., `closure_type`) needs different options or groups in the new type, rename it with a prefix (e.g., `newtype_closure_type`).

## Adding a New Endpoint

1. Create schema in `app/schemas/` — add OpenAPI `examples` to fields
2. Create service in `app/services/` — raise domain exceptions from `app.core.exceptions`
3. Create route in `app/api/v1/` — use typed dependencies
4. Register in `app/api/v1/router.py`
5. Add tests in `tests/`

## Project Board Automation (how to commit)

Every push to `main` is processed by the **Project Sync** workflow — see
[docs/project-board-automation.md](project-board-automation.md) for the full
developer rules. In short:

1. **Create a GitHub issue** for the work before coding.
2. **Reference it in the commit message**: `fixes #12` / `closes #12`
   (completes it → board Status becomes Done), `refs #12` or `#12`
   (only touches it → Status untouched). The push then links to the existing
   issue instead of creating a duplicate task.
3. No reference → an auto-generated 🤖 task appears on the board.
4. `[skip-task]` in the message opts a push out of the board entirely.
