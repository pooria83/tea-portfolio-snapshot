# TEA — Private Technical Portfolio

> This repository is a private portfolio snapshot prepared for technical review. The original production repositories remain private and unchanged. This snapshot contains selected code and documentation relevant to the TEA platform and my technical contribution.

TEA is an AI-native conversational product discovery platform. Users describe what they are looking for; the platform interprets the request, retrieves catalog products, and presents conversational responses with product cards. This snapshot brings five services together for review, with source provenance and explicit sanitation boundaries.

## Start here

- [Architecture](docs/architecture.md): request paths, retrieval, storage, and supporting infrastructure.
- [Technical overview](docs/technical-overview.md): implementation evidence, tests, reliability, and limitations.
- [My contribution](docs/my-contribution.md): Pooria / Hasan Jalili's work and team boundaries.
- [Sanitization and verification](docs/sanitization.md): exclusions, validation, and review-only constraints.
- [Snapshot manifest](docs/snapshot-manifest.json): source commits, retained file hashes, redactions, and exclusions.

## Repository layout

```text
tea-portfolio-snapshot/
├── README.md
├── web/           Next.js application, components, state, and tests
├── api/           FastAPI Product API, data models, migrations, and tests
├── ai-engine/     FastAPI AI service, embeddings, retrieval, and tests
├── infra/         Sanitized Docker Swarm, Compose, and Ansible configuration
├── mobile/        React Native application and native project context
└── docs/          Portfolio documentation, provenance, and verification
```

## Engineering highlights

The AI Engine implements tool-first search planning with a structured parsing fallback; Qwen3 embedding support; Qdrant dense and BM25-style sparse retrieval; rank fusion; filter relaxation; and product-level deduplication. The API owns catalog data, authentication, chat persistence, model configuration, and retrieval evaluation. Web and mobile consume the API and its streaming chat protocol.

Verified technologies include Python/FastAPI, PostgreSQL/SQLAlchemy/Alembic, Redis, RabbitMQ broker setup, optional MongoDB chat storage, MinIO object storage, Qdrant, Qwen3 embeddings, a configured DeepSeek V4 Flash model identifier, Docker/Swarm, Next.js/React, and React Native. HTTP event streaming and WebSocket transport are both present. These are repository observations, not assertions about the current production deployment.

## Contribution and development process

Pooria / Hasan Jalili primarily implemented the web application, Product API (including AI-assisted development), AI Engine, and retrieval/embedding pipeline, with Docker, RabbitMQ, repository setup, and related technical improvements. Product architecture and major decisions were collaborative. Mohammad primarily implemented mobile and contributed to other infrastructure work. See the [contribution statement](docs/my-contribution.md) for precise attribution.

Claude Code, Codex, Cursor, and OpenCode were part of the owner-reported development workflow. Human engineers remained responsible for architecture decisions, validation, review, testing, and business correctness. No exclusive architecture ownership or productivity percentage is claimed.

## Review scope

This is a source review snapshot, not a production deployment or a fully runnable demo. Source histories are not merged. Environment files, private keys, tunnel credentials, cookies, signing material, local artifacts, and binary assets are excluded. Deployment addresses and credential-bearing sample configuration are sanitized. Lockfiles, tests, migrations, meaningful source, and selected technical documentation are retained.

Each module's original README and technical docs are historical source material; this root documentation defines the snapshot's scope and verified claims. Some original run commands refer to excluded environment files, certificates, fonts, or native assets. Review [execution limitations](docs/sanitization.md) before attempting an isolated local setup. No production services were started or accessed during snapshot preparation.
