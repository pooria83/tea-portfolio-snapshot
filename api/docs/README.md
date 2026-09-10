# Product Graph API — Developer Documentation

The Product Graph API (`product-graph-api`) is the backend for the AI Product Finder (TEA) platform. It is a FastAPI service that owns authentication, the product catalog, stores, sellers, files, chat history, and the orchestration of every AI feature — delegating all model inference (chat, descriptions, summaries, titles, embeddings) to the `product-graph-ai-engine` service over HTTP.

Start here: **[Architecture](architecture.md)** gives the full-system picture. Everything below goes one level deeper.

## Reading Paths

| You want to understand... | Read this |
|---|---|
| The whole system, end to end | [Architecture](architecture.md) |
| How every service module works | [Services Deep Dive](services.md) |
| Every endpoint, request/response, auth & rate limits | [API Reference](api-reference.md) |
| How the API talks to the AI Engine (chat, description, embedding, config) | [AI Engine Integration](ai-engine-integration.md) |
| Chat: MongoDB schema, WebSocket protocol, compaction, titling | [Chat System](chat-system.md) |
| Embedding lifecycle: text building, filters, webhook, recovery cron | [Embedding Pipeline](embedding-pipeline.md) |
| LLM models, API keys, providers, prompt templates | [LLM Management](llm-management.md) |
| Background jobs: cron cycles, locks, shutdown order | [Background Tasks](background-tasks.md) |
| Auth: JWT, OTP, Google, RBAC, API keys, rate limiting | [Authentication](authentication.md) |
| PostgreSQL/Mongo/Redis/MinIO/RabbitMQ usage | [Data Stores](data-stores.md) |
| The Redis cache layer: key registry, TTLs, invalidation | [Caching](caching.md) |
| The dynamic product definition (catalog) system | [Product Definition System](product-definition-system.md) |
| Golden-set search evaluation: MRR@10 / Recall@10 workflow | [Search Evaluation](search-eval.md) |
| Error codes & `translation_key` contract with frontends | [Error Codes](error-codes.md) |
| Structured logging, request IDs, PII redaction, activity log | [Logging](logging.md) |
| Local setup, Docker profiles, commands, testing | [Getting Started](getting-started.md) |
| Test infrastructure: PG16, mocks, coverage gate, load tests | [Testing](testing.md) |
| Production deployment & env vars | [Deployment](deployment.md) |
| Backup & restore runbooks: Postgres/Mongo/MinIO/Qdrant + server sync | [Backups & Restore](backups-and-restore.md) |
| Zara scraper pipeline | [Zara Scraper](scraping/zara.md) |

## Repository Layout

```
app/
├── ai/                 # AIEngineClient — HTTP client to product-graph-ai-engine
├── api/v1/             # Route handlers (auth, users, products, stores, chats, files, admin, ws)
│   └── admin/          # Admin-only routers (llm, prompt_templates, system_settings, ai_engine, cron, conversations)
├── core/               # Config, auth primitives, DI, exceptions, error codes, middleware, broker, redis, metrics
├── db/                 # MongoDB (Atlas) connection for chat history
├── models/             # SQLAlchemy ORM models (42 classes across 38 modules)
├── repositories/       # Data-access layer (BaseRepository[T] + Mongo repos)
├── schemas/            # Pydantic v2 request/response schemas
├── scrapers/           # Zara scraper pipeline
└── services/           # Business logic: auth, user, product, store, chat, cron, embedding, storage, sms, ws
```

## Core Concepts (TL;DR)

- **Stateless API, smart engine**: the API is a thin proxy for AI. The engine does RAG (Qdrant), LLM calls, and embeddings. The API supplies context (product info, prompts, history) and persists results.
- **Two databases**: transactional data (users, stores, products, LLM config) lives in **PostgreSQL**; chat conversations/messages live in **MongoDB** (optional — graceful 503 degradation when `MONGO_URL` is empty).
- **Three background tasks** start with the app: product AI description cron (300s), embedding recovery cron (60s), and activity log cleanup (24h).
- **Every AI call carries context headers** `X-Request-Id` / `X-User-Id` so engine logs correlate with API logs.
- **Everything is observable**: Loguru JSON logging, Prometheus metrics, an `activity_logs` table, and typed error codes with `translation_key` for frontend i18n.

## Index

- [Architecture](architecture.md)
- [Services Deep Dive](services.md)
- [API Reference](api-reference.md)
- [AI Engine Integration](ai-engine-integration.md)
- [Chat System](chat-system.md)
- [Embedding Pipeline](embedding-pipeline.md)
- [LLM Management](llm-management.md)
- [Background Tasks](background-tasks.md)
- [Authentication](authentication.md)
- [Data Stores](data-stores.md)
- [Caching](caching.md)
- [Product Definition System](product-definition-system.md)
- [Search Evaluation](search-eval.md)
- [Error Codes](error-codes.md)
- [Logging](logging.md)
- [Getting Started](getting-started.md)
- [Testing](testing.md)
- [Deployment](deployment.md)
- [Backups & Restore](backups-and-restore.md)
- [Cloudflare Tunnel (dev)](cloudflare-tunnel-dev.md)
- [Repository Ownership](repository-ownership.md)
- [Project Board Automation](project-board-automation.md)
- [Zara Scraper](scraping/zara.md)
