# Product Graph Infra

Deployment infrastructure for TEA-assist microservices.

## Documentation

| Document | Description |
|---|---|
| [Project Board Automation](docs/project-board-automation.md) | Commit-to-board workflow: issue references, auto-tasks, skip marker |

## Architecture

Single-node Docker Swarm cluster with 5 stacks:

| Stack | Purpose | Services |
|---|---|---|
| `tea-infra` | Shared infrastructure | PostgreSQL 16, Redis 7, RabbitMQ 4, MinIO, Qdrant, pgAdmin, RedisInsight |
| `tea-monitor` | Centralized logging | Grafana, Loki, Promtail |
| `tea-portainer` | Docker Swarm management UI | Portainer CE |
| `tea-caddy` | Reverse proxy + TLS | Caddy with Cloudflare DNS module |
| `tea-app` | Application | AI engine, FastAPI backend, Next.js frontend |

## Network

All stacks share an attachable overlay network `tea-infra-net`:

```bash
docker network create --driver overlay --attachable tea-infra-net
```

## Subdomains

All routes served by `stacks/tea-caddy/Caddyfile`:

| Subdomain | Target | Stack | Auth |
|---|---|---|---|
| `portfolio.example.invalid` | API (FastAPI) on port 8000 | `tea-app` | App-level JWT / `API_API_KEY` |
| `portfolio.example.invalid` | Web UI (Next.js) on port 3000 | `tea-app` | None (login handled by the API) |
| `portfolio.example.invalid` | Grafana on port 3000 | `tea-monitor` | Grafana admin login |
| `portfolio.example.invalid` | Loki on port 3100 | `tea-monitor` | **None — unauthenticated** |
| `portfolio.example.invalid` | pgAdmin on port 80 | `tea-infra` | pgAdmin login |
| `portfolio.example.invalid` | RedisInsight on port 5540 | `tea-infra` | None (Redis password preconfigured via env) |
| `portfolio.example.invalid` | Qdrant REST API + dashboard on port 6333 | `tea-infra` | Qdrant API key (doubles as dashboard password) |
| `portfolio.example.invalid` | Portainer on port 9000 | `tea-portainer` | Portainer admin login |
| `portfolio.example.invalid` | MinIO S3 API on port 9000 | `tea-infra` | S3 access/secret keys (`MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`) |
| `portfolio.example.invalid` | MinIO console on port 9001 | `tea-infra` | MinIO console login (same root credentials) |

> **Exposure notes:** Docker-published host ports bypass UFW entirely (Docker inserts its own iptables rules ahead of it) — Qdrant (`6333`) and Loki (`3100`) are reachable directly on the host, not only through Caddy. `portfolio.example.invalid` has **no authentication**: anyone can read or write logs. All other routes are protected by their own login/API key as listed above. See [docs/security.md](docs/security.md) for the full exposure/hardening picture.

## Deploy

```bash
bash scripts/deploy.sh
```

Deploy order: infra → monitor → portainer → caddy → app

## Stacks

### tea-infra

```yaml
services:
  postgres: postgres:16.14-alpine
  redis: redis:7.4-alpine
  rabbitmq: rabbitmq:4.3-alpine
  minio: minio/minio:RELEASE.2025-09-07T16-13-09Z
  qdrant: qdrant/qdrant:v1.19.0
  pgadmin: dpage/pgadmin4:8.14
  redisinsight: redis/redisinsight:3.8.0
```

### tea-monitor

```yaml
services:
  grafana: grafana/grafana:13.1.2
  loki: grafana/loki:3.7.5
  promtail: grafana/promtail:3.6.11
```

### tea-caddy

```yaml
services:
  caddy: caddybuilds/caddy-cloudflare:2.11.4-alpine
```

### tea-app

```yaml
services:
  ai-engine: ghcr.io/tea-assist/product-graph-ai-engine:main  # LLM desc gen + RAG chat + in-process embeddings
  api: ghcr.io/tea-assist/product-graph-api:main              # FastAPI backend
  web-ui: ghcr.io/tea-assist/product-graph-web-ui:main        # Next.js dashboard
```

### Qdrant (API-key auth)

Qdrant requires an API key for **all** access (REST, dashboard, and client connections):

- The key is set on the Qdrant service via `QDRANT__SERVICE__API_KEY: ${QDRANT_API_KEY}` (from the server `.env`).
- The **ai-engine** authenticates with `QDRANT_API_KEY` env var (its `AsyncQdrantClient` passes `api_key=`).
- Access without the key returns `401 "Must provide an API key or an Authorization bearer token"`.

Verify locally:

```bash
curl -H "api-key: $QDRANT_API_KEY" http://localhost:6333/collections     # 200
curl http://localhost:6333/collections                                    # 401
```

Public access goes through Caddy at `https://portfolio.example.invalid` — the **dashboard** (`https://portfolio.example.invalid/dashboard`) logs in with the same API key as password.

## CI/CD

Each repo has a GitHub Actions workflow:

- **product-graph-api**: Build → push to GHCR → SSH deploy
- **product-graph-web-ui**: Build → push to GHCR → SSH deploy
- **product-graph-infra**: rsync → (Ansible if `ansible/**` changed) → rewrite server `.env` from secrets → `scripts/deploy.sh`

Deploy SSH user: `tea` at `192.0.2.10` (password from `SERVER_PASSWORD` secret).

> **Important:** the infra deploy workflow **rewrites** `/opt/tea-assist/product-graph-infra/.env` on every push from GitHub secrets. Any new var used by compose must be added **both** to `deploy.yml` heredoc **and** as a repo-level GitHub secret (`gh secret set NAME`, no `--env` — these workflows don't use environments).

## Server `.env` vars

Compose files interpolate variables from `/opt/tea-assist/product-graph-infra/.env` (sourced by `scripts/deploy.sh`). Full list written by CI:

| Variable | Used by | Description |
|---|---|---|
| `CLOUDFLARE_API_TOKEN` | caddy | Cloudflare DNS-01 TLS |
| `GRAFANA_ADMIN_PASSWORD` | grafana | Monitoring login |
| `POSTGRES_PASSWORD` | postgres, api, ai-engine | DB password |
| `RABBITMQ_PASSWORD` | rabbitmq, api | Queue password |
| `MINIO_ROOT_USER` | minio, api | Object storage access key |
| `MINIO_ROOT_PASSWORD` | minio, api | Object storage password |
| `MINIO_PUBLIC_URL` | api | Public MinIO base URL — **must be `https://portfolio.example.invalid` in production** (dev uses `https://portfolio.example.invalid`; no trailing slash) |
| `API_SECRET_KEY` | api | FastAPI secret key |
| `API_JWT_SECRET_KEY` | api | JWT signing key |
| `API_API_KEY` | api | Service-to-service API key |
| `AI_ENGINE_OPENCODE_ZEN_API_KEY` | ai-engine | OpenCode Zen (DeepSeek V4 Flash) fallback key |
| `AI_ENGINE_LLM_ENCRYPTION_KEY` | ai-engine, api | Fernet key — decrypts DB-stored LLM keys (must match API's `LLM_ENCRYPTION_KEY`) |
| `MONGO_URL` / `MONGO_DB_NAME` | api | Atlas chat history (MongoDB) |
| `QDRANT_API_KEY` | qdrant, ai-engine | Qdrant API key + dashboard password |
| `REDIS_PASSWORD` | redis, redisinsight, api | Redis `requirepass` + client auth |

See [.env.example](.env.example) at the repo root for the full template — it mirrors the exact 16 vars the CI heredoc writes, in the same order. Note that `stacks/tea-app/.env.example` alone is **not** sufficient: the CI validate job copies it and appends 5 more vars (`PGADMIN_EMAIL`, `PGADMIN_PASSWORD`, `GRAFANA_ADMIN_PASSWORD`, `CLOUDFLARE_API_TOKEN`, `REDIS_PASSWORD`).

> **Warning:** `AI_ENGINE_LLM_ENCRYPTION_KEY` and `AI_ENGINE_OPENCODE_ZEN_API_KEY` are **required** — without the encryption key the ai-engine cannot decrypt DB-stored LLM keys and crashes on startup with `OpenAIError: Missing credentials`. No manual `docker pull` is needed after a CI push: `scripts/deploy.sh` pulls all three `:main` app images automatically before deploying (`pull_app_images`) and force-updates the three app services afterward; if a pull fails it logs a warning and continues with the cached image.

## MongoDB Atlas Backup (Chat History)

M0 free tier has no native backups. A daily `mongodump` of the chat history DB, mirrored to MinIO, is recommended — but this cron is **not** provisioned by the playbook; set it up manually on the VPS using the suggested crontab below. See [docs/backups.md](docs/backups.md) for the consolidated backup story (all datastores).

```bash
# On the VPS (after installing mongodb-database-tools)
set -a && source /opt/tea-assist/product-graph-infra/.env && set +a
bash /opt/tea-assist/product-graph-api/dev-tools/backup_mongo.sh /opt/tea-assist/backups
mc alias set tea-backup http://localhost:9000 minioadmin "$MINIO_ROOT_PASSWORD" --api S3v4
mc mirror /opt/tea-assist/backups tea-backup/mongo-backups
```

Suggested crontab entry (daily at 02:30, retention of 14 days):

```cron
30 2 * * * cd /opt/tea-assist && set -a && source product-graph-infra/.env && set +a && product-graph-api/dev-tools/backup_mongo.sh backups >> backups/mongo_backup.log 2>&1 && mc mirror --overwrite backups tea-backup/mongo-backups && find backups -name "tea-*.archive.gz" -mtime +14 -delete
```

## Database Backup & Restore

### Dump local dev DB and restore to production

```bash
# 1. Dump local database (plain SQL for cross-version compatibility)
pg_dump -h localhost -U postgres -d product_graph --format=plain --no-owner --no-privileges | gzip > /tmp/product_graph.sql.gz

# 2. Copy to server
scp /tmp/product_graph.sql.gz tea@192.0.2.10:/tmp/

# 3. Restore into production PostgreSQL container
ssh tea@192.0.2.10
CID=$(docker ps --filter name=tea-infra_postgres -q | head -1)
gunzip -c /tmp/product_graph.sql.gz > /tmp/product_graph.sql
docker cp /tmp/product_graph.sql $CID:/tmp/product_graph.sql
docker exec $CID psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'product_graph' AND pid <> pg_backend_pid();"
docker exec $CID psql -U postgres -c "DROP DATABASE IF EXISTS product_graph;"
docker exec $CID psql -U postgres -c "CREATE DATABASE product_graph;"
docker exec $CID psql -U postgres -d product_graph -f /tmp/product_graph.sql
docker service update --force tea-app_api
```

**Note:** Use `--format=plain` (SQL) instead of `--format=custom` to avoid `unsupported version` errors when `pg_dump` (local) differs from `pg_restore` (server) versions.

### Key tables after seed

| Table | Rows |
|-------|------|
| `store_products` | ~1,900 |
| `categories` | 131 |
| `brands` | 86 |
| `product_types` | 30 |
| `users` | 2 |

## Server Info

- IP: `192.0.2.10`
- OS: Ubuntu/Debian
- RAM: 8GB
- Docker Swarm: single node
- Domain: `portfolio.example.invalid` via Cloudflare

## Server Tools (Provisioned via Ansible)

| Tool | What it does |
|------|-------------|
| `htop` | Interactive process viewer — press `F6` to sort by CPU/memory |
| `nethogs` | See which processes are using bandwidth (`sudo nethogs eth0`) |
| `rsync` | Local/remote file sync with compression and progress (`rsync -avz --progress`) |
| `curl` | Test APIs, download files |
| `wget` | Recursive downloads, mirror sites |
| `tmux` | Terminal multiplexer — `tmux new -s mysession`, then detach with `Ctrl+B d` |
| `vnstat` | Lightweight traffic logger — `vnstat -m` for monthly, `vnstat -h` for hourly |
| `ncdu` | Disk usage analyzer — `ncdu /` to find space hogs |
| `jq` | JSON command-line processor — `docker inspect foo | jq '.[].Name'` |
| `mtr` | Network diagnostic — `mtr portfolio.example.invalid` shows real-time path + packet loss |
| `lsof` | List open files — `lsof -i :5432` to see what's using a port |
| `tree` | Directory tree — `tree /opt/tea-assist` |
