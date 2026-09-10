# Product Graph API Documentation

See **[README.md](README.md)** — the full developer documentation index (architecture, services, AI engine integration, chat system, embedding pipeline, LLM management, API reference, background tasks, authentication, data stores, and operational guides).

This file is kept as a short link index for tooling that references `docs/index.md`.

## Contents

- [Documentation Index](README.md) — complete reading paths
- [Getting Started](getting-started.md) — setup, Docker profiles, commands, testing, backup/restore, code style
- [Architecture](architecture.md) — project structure, modules, data flow, middleware
- [Services Deep Dive](services.md) — every service module in `app/services/`
- [API Reference](api-reference.md) — endpoints, auth, rate limits, WebSockets, webhooks, errors
- [AI Engine Integration](ai-engine-integration.md) — client methods, request/response contracts, config push, webhooks
- [Chat System](chat-system.md) — WebSocket protocol, Mongo schema, compaction, titling
- [Embedding Pipeline](embedding-pipeline.md) — embed-text building, filters, recovery cron, backfill
- [LLM Management](llm-management.md) — models, encrypted API keys, prompt templates, config push
- [Background Tasks](background-tasks.md) — cron cycles, locks, shutdown order
- [Authentication](authentication.md) — JWT rotation, OTP, Google, API keys, RBAC, lockout
- [Data Stores](data-stores.md) — PostgreSQL, MongoDB, Redis, MinIO, RabbitMQ
- [Caching](caching.md) — Redis cache layer: key registry, TTLs, invalidation
- [Product Definition System](product-definition-system.md) — catalog, attributes, categories, seed data
- [Search Evaluation](search-eval.md) — golden-set queries, judgments, MRR@10 / Recall@10 metrics
- [Error Codes](error-codes.md) — error codes & `translation_key` contract
- [Logging](logging.md) — structured logging, request IDs, PII redaction, activity log
- [Getting Started](getting-started.md) — setup, Docker profiles, commands, testing, backup/restore, code style
- [Testing](testing.md) — PostgreSQL 16 test setup, mocks, coverage gate, load tests
- [Deployment](deployment.md) — CI/CD pipeline, Docker Swarm production, environment variables
- [Backups & Restore](backups-and-restore.md) — Postgres/Mongo/MinIO/Qdrant backups + local→server MinIO sync
- [Cloudflare Tunnel (dev)](cloudflare-tunnel-dev.md) — exposing local dev services via `*.dev.portfolio.example.invalid`
- [Repository Ownership](repository-ownership.md) — repo responsibilities across the TEA-assist org
- [Project Board Automation](project-board-automation.md) — commit-to-board workflow
- [Zara Scraper](scraping/zara.md) — Zara-specific scraper details
