# Technical overview

## Module map and review entry points

- **web/** ← `TEA-assist/product-graph-web-ui`: Next.js App Router, React/TypeScript, Redux Toolkit/RTK Query, next-intl, forms/validation, administrative tools, and chat. Start with `web/src/app/`, `web/src/hooks/useChatSocket.ts`, and `web/src/store/api/`.
- **api/** ← `TEA-assist/product-graph-api`: FastAPI endpoints, service/repository layers, PostgreSQL models and Alembic migrations, auth, optional MongoDB chat, Redis, object storage, AI integration, and evaluation. Start with `api/app/main.py`, `api/app/services/chat_service.py`, and `api/app/ai/client.py`.
- **ai-engine/** ← `TEA-assist/product-graph-ai-engine`: FastAPI inference orchestration, intent/planning, model clients, retrieval, embeddings, and evaluation search. Start with `ai-engine/app/routers/chat.py`, `ai-engine/app/services/rag.py`, and `ai-engine/app/services/embedding/`.
- **infra/** ← `TEA-assist/product-graph-infra`: Docker Swarm/Compose topology, reverse proxy, monitoring, Ansible, and scripts. Retained configuration is sanitized and cannot be used as production credentials/configuration.
- **mobile/** ← `TEA-assist/product-graph-mobile-app`: React Native/TypeScript client, navigation, chat, authentication, TanStack Query, Zustand, keychain storage, and native project context. Start with `mobile/src/features/` and `mobile/src/services/`. Primary implementation attribution belongs to Mohammad.

## Model and retrieval evidence

The AI Engine's `app/core/config.py` defaults to `Qwen/Qwen3-Embedding-4B`, 2560 dimensions, with the `sentence_transformer` provider. Both `llm_model` and `user_comm_model` use `deepseek-v4-flash-free`; this is source evidence for the DeepSeek V4 Flash configuration, not an independent check of provider availability or the current active model. Runtime configuration and persisted model settings can override defaults.

The embedding registry supports local SentenceTransformer, a remote TEI/OpenAI-compatible endpoint, and OpenRouter. Query instruction formatting for Qwen3 is visible in the TEI implementation. Tests and seed configuration also reference other Qwen3 sizes. It would be inaccurate to describe every deployment as using one model or dimension.

The [architecture](architecture.md) details tool calling, structured/raw-query fallbacks, dense/sparse retrieval, RRF, filters, and deduplication. Read `ai-engine/tests/test_rag_hybrid.py`, `tests/test_rag.py`, `tests/test_search_tools.py`, and `tests/test_chat_router.py` alongside the implementation.

## Retrieval evaluation

`ai-engine/app/routers/eval.py` exposes `/eval/search`, preserving scored product results. It deliberately uses `_resolve_search(..., use_tools=False)`, so evaluation bypasses tool-calling variability; parsing/model inference is still not guaranteed deterministic.

`api/app/services/search_eval_service.py` manages queries, judgments, imports, and metrics. `_metric_item` computes:

- **MRR@10:** reciprocal of the best judged-relevant rank at or before 10, averaged over queries that have relevant judgments.
- **Recall@10:** judged relevant products in the top 10 divided by all relevant judgments for that query, averaged over those queries.

Queries without relevant judgments are excluded from the metric denominator. This depends on judgment completeness; it is not a measurement of all relevant products in the catalog. Model scores and hybrid fusion scores also should not be treated as directly comparable confidence probabilities.

The source golden dataset has **166 English/Arabic queries**. This snapshot preserves text/locale and removes **650 development-catalog relevance references**. `api/scripts/seed_data/search_eval_golden.json` explicitly explains that new judgments are required. No catalog records, production measurements, achieved MRR/Recall numbers, or benchmark improvements are asserted.

The web admin evaluation page is retained at `web/src/app/[locale]/(dashboard)/admin/search-eval/page.tsx`; API models, schemas, migrations, and tests for evaluation are included.

## Data and messaging

PostgreSQL/SQLAlchemy/Alembic implement relational catalog, account, settings, and evaluation storage. MongoDB/Motor supports optional conversation and message persistence. Redis cache logic and invalidation are in `api/app/core/cache.py`; lock coordination is in `app/core/distributed_lock.py`. MinIO access is implemented in the API storage service.

The implemented chat path is web/mobile → API → AI Engine over HTTP, then the API relays response frames over WebSocket. Broker infrastructure exists separately; no complete RabbitMQ producer/consumer workflow is claimed. Background description and embedding tasks are launched from API startup, with recovery/status callbacks visible in the source.

## Testing approach

- **AI Engine:** pytest/pytest-asyncio tests with mocked model clients, Qdrant, and HTTP dependencies; router, parsing, retrieval, hybrid, embeddings, auth, crypto, and SSRF cases are present.
- **API:** pytest async API/service tests, PostgreSQL through Testcontainers or `TEST_DATABASE_URL`, Mongo mock support, and mocked external dependencies; migrations and Locust load-test source are retained.
- **Web:** Vitest and Testing Library tests for components, hooks, state, and API behavior; Playwright authentication scenarios and type/lint configuration are present.
- **Mobile:** Jest and React Native Testing Library tests for hooks, chat streams, components, auth/storage, and screens; Detox configuration and an e2e auth scenario are present. Native builds require excluded assets and signing/local configuration.
- **Infrastructure:** YAML and workflow configuration demonstrate validation/deployment intentions. Nested `.github/workflows` files are historical examples and are not active root workflows in this snapshot.

Test presence is distinct from successful execution. Snapshot preparation performs static parsing, a focused dependency-free metric behavior check, integrity checks, and security scans. It does not claim the original full test suites passed, coverage targets were achieved, or deployments were exercised. See [verification](sanitization.md).

## Reliability and visible security patterns

Visible mechanisms include cached health probes, request correlation/logging, HTTP timeouts, fallback search/response paths, product deduplication, Redis locking for recovery work, MongoDB optionality, and Docker health checks/resource limits. These are implementation patterns, not an availability guarantee.

API security code includes password hashing, JWT validation, role/account checks, OAuth state consumption, cookie settings, rate limiting, webhook/API-key checks, and encrypted stored model credentials. The AI Engine has a shared-key middleware and SSRF-related outbound URL checks. Mobile stores tokens through keychain integration.

Configuration matters: an empty engine key disables its guard, an empty webhook secret disables verification, and some default-setting checks warn rather than fail. Snapshot redactions are not security fixes to the applications. No penetration-test, compliance, production-hardening, or absence-of-vulnerabilities claim is made.

## Deployment and boundaries

Dockerfiles and sanitized Compose/Swarm stacks are preserved with Ansible and selected scripts. PostgreSQL, Redis, RabbitMQ, MinIO, Qdrant, reverse proxy, and monitoring definitions demonstrate topology. Production addresses, keys, environment files, tunnel identities, and local artifacts were removed or replaced. No deployment was performed.

Ownership and AI-tool use come from the owner's statement, not code-derived authorship proof. Active production models, production metrics, exclusive architectural ownership, live infrastructure state, and a complete RabbitMQ processing pipeline cannot be verified from this snapshot and are not claimed.
