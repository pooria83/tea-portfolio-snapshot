# Product Graph API

AI Product Finder backend — FastAPI with async PostgreSQL, Redis, RabbitMQ, and MinIO.

## Quick Start

```bash
docker compose --profile full up -d
make seed
make dev
```

API available at [http://localhost:8000](http://localhost:8000)
Docs at [http://localhost:8000/docs](http://localhost:8000/docs)

## Features

- **Full Product Catalog**: Types, categories, attributes, brands, variants, images, color sets, pieces
- **AI Description Generation**: Background cron (300s cycle) or manual trigger; admin-managed LLM models & API keys (Fernet-encrypted), prompt templates, system settings
- **RAG Chat**: WebSocket-based (streaming) + REST conversational product search via Qdrant vector DB — Mongo-backed conversations, compaction, titling, idempotent sends; **public anonymous chat** for guests (ephemeral 10-min WS-only tokens), intent round-trip (greeting/search/general), `similar_request` for lookalikes, message feedback
- **Cookie + Bearer auth**: httpOnly `access_token`/`refresh_token` cookies (SameSite=Lax) with `X-CSRF-Token` protection for browser clients, `Authorization: Bearer` for native apps, OAuth authorization-code nonce — all auth flows set both transports
- **Auto-Embedding on Save**: Product create/update triggers async fire-and-forget embedding via AI Engine. Supports multiple embedding models (9 seeded: Qwen3-0.6B/4B/8B, F2LLM-v2-4B, jina-v5-text-small, BGE-M3, Nomic Embed v2, multilingual-e5) — one `product_embeddings` row per product per model, per-model Qdrant collections; **one monolingual passage per language** (en + ar points with dense + BM25 sparse vectors); vector dims resolved from the model name (`EMBEDDING_MODEL_DIMS`). Tracks lifecycle via `embedding_status` on `product_embeddings`.
- **Authentication**: Phone OTP + Google OAuth, JWT with refresh rotation, RBAC (admin/seller)
- **Public surface**: `GET /public/products/random` home sliders, public product detail, anonymous chat sessions
- **Search Evaluation**: admin golden set (166 queries en/ar), query generation/import, judgments, MRR@10 / Recall@10 metrics
- **Scraper Pipeline**: 3-phase Zara scraper (sitemap → scrape → transform) with image flow
- **Admin Dashboard API**: LLM management, prompt templates, system settings, cron reports
- **Product Info API**: Full product data with locale-aware UUID→display name resolution

## Documentation

| Document | Description |
|---|---|---|
| [Documentation Index](docs/README.md) | All developer docs with reading paths |
| [Architecture](docs/architecture.md) | Project structure, modules, middleware, data flow |
| [Services Deep Dive](docs/services.md) | Every service module in `app/services/` |
| [API Reference](docs/api-reference.md) | Every endpoint: request/response, auth, rate limits, WebSockets, webhooks, errors |
| [AI Engine Integration](docs/ai-engine-integration.md) | Client methods, request/response contracts, config push, webhooks |
| [Chat System](docs/chat-system.md) | WebSocket protocol, Mongo schema, compaction, titling |
| [Embedding Pipeline](docs/embedding-pipeline.md) | Embed-text building, filters, recovery cron, backfill |
| [LLM Management](docs/llm-management.md) | Models, encrypted API keys, prompt templates |
| [Background Tasks](docs/background-tasks.md) | Cron cycles, locks, consumer/dispatcher, shutdown order |
| [Authentication](docs/authentication.md) | JWT rotation, OTP, Google, API keys, RBAC, lockout |
| [Data Stores](docs/data-stores.md) | PostgreSQL, MongoDB, Redis, MinIO, RabbitMQ |
| [Product Definition System](docs/product-definition-system.md) | Catalog, attributes, categories, seed data |
| [Error Codes](docs/error-codes.md) | Error codes & `translation_key` contract |
| [Logging](docs/logging.md) | Structured logging, request IDs, activity log |
| [Getting Started](docs/getting-started.md) | Setup, Docker profiles, commands, testing, backup/restore |
| [Deployment](docs/deployment.md) | Docker, production, proxy setup |
| [Scraper Mapping](SCRAPER_MAPPING.md) | Category, color, attribute mapping & pipeline |
| [Zara Scraper](docs/scraping/zara.md) | Zara-specific scraper details |
| [Project Board Automation](docs/project-board-automation.md) | Commit-to-board workflow: issue references, auto-tasks, skip marker |

## Tech Stack

**FastAPI** · **SQLAlchemy 2.0 async** · **PostgreSQL 16** · **Redis 7** · **RabbitMQ** · **MinIO** · **aio-pika** · **Pydantic v2** · **JWT** · **structlog** · **Prometheus** · **uv**

## CI Runners

CI, build, and deploy run on **self-hosted GitHub Actions runners** on the
TeaServer host (org Actions minutes are quota-limited). The runner service users
(`runner-api`, `runner-web-ui`, `runner-ai-engine`, `runner-mobile`) belong to
the `docker` group so `docker build`/`docker push` work; restart the runner
services after changing group membership (`sudo systemctl restart
actions.runner.TEA-assist-product-graph-api.tea-api-runner.service`).
