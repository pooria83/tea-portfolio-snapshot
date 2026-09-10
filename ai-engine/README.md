# Product Graph AI Engine

AI service for the TEA-assist platform: **product description generation**,
**RAG conversational product search** (REST + SSE streaming), **product
embedding**, and chat support endpoints (rolling summaries + titles).

- **LLM**: DeepSeek V4 Flash via OpenCode Zen (OpenRouter supported for model overrides)
- **Embeddings**: Qwen3 family — default `Qwen/Qwen3-Embedding-4B` (2560 dims) via in-process SentenceTransformer, TEI (remote/Colab tunnel), or OpenRouter; per-model vector dims (0.6B→1024, 4B→2560, 8B→4096) resolved from the model name
- **Vector store**: Qdrant (cosine, per-model collections with model-specific dims, bilingual payloads)
- **Stack**: FastAPI · Python 3.14 · uv · loguru · SQLAlchemy (async) · Fernet

The engine is **stateless**: it keeps no product database and no chat history.
All product data arrives in request bodies; PostgreSQL is read-only (encrypted
LLM API keys); persistent state lives in Qdrant.

## Quick Start

```bash
cp .env.example .env        # configure API keys (OPENCODE_ZEN_API_KEY, QDRANT_URL, ...)
make setup                  # uv sync --extra dev
make dev                    # dev server on :8003 with hot reload
```

Interactive API docs: <http://localhost:8003/docs>

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check (used by Docker HEALTHCHECK) |
| POST | `/config` | Runtime overrides: embedding provider, LLM models, TEI tunnel URL, LLM refresh |
| POST | `/generate-description` | Generate EN/AR/FA product descriptions (per-model override supported) |
| POST | `/chat` | RAG conversational product search — JSON response or SSE stream (`stream: true`) |
| POST | `/embed-product` | Embed product passage → Qdrant → webhook callback to the API |
| POST | `/embed-text` | Embed free text, return the raw vector (admin/embedding test) |
| POST | `/summarize` | Rolling conversation summary `S2 = f(S1, new messages)` |
| POST | `/title` | Short conversation title (2–6 words) from the first user message |
| POST | `/similar` | Similar products to an indexed product (metadata-aware, dense-only) |
| POST | `/eval/queries` | LLM-generate diverse catalog-realistic queries (admin search-eval) |
| POST | `/eval/search` | Deterministic parse-path search with per-hit scores (admin search-eval) |

## Key Behaviors

- **Tool-calling search first, parse fallback second** — the comm LLM calls a
  `search_products` tool; models without tool support fall back to
  query-rewrite + filter JSON parsing; direct answers skip search entirely.
- **Filtered vector search with fallback** — Qdrant `FieldCondition` +
  `MatchAny` on color/material/category/brand/gender/color_family; unfiltered
  search pads results when filtered results are short.
- **Hybrid dense+sparse search** — client-side BM25 sparse vectors
  (`text_bm25`) fused with the dense branch via `Fusion.RRF` (k=60) over a
  wider pool; model-aware score thresholds (1024→0.3, 2560→0.25); language-
  aware dedupe (`prefer_lang`); dense-only fallback when sparse is unavailable.
- **Similar products** — metadata-aware tiers (category chain → color family →
  unfiltered) with color-family ranking bonus, dense-only.
- **Search evaluation** — `/eval/queries` + `/eval/search` for repeatable
  MRR/Recall measurement against the API's 166-query golden set.
- **Streaming chat** — SSE frames: `debug`, `assistant_start`,
  `product_cards`, `text_chunk`*, `assistant_end` / `error`.
- **Bilingual Qdrant payloads** — `product_data` with `en`/`ar`, locale-aware
  prompt context and no-results hints (en/ar/fa).
- **DB-backed LLM keys** — encrypted keys in `llm_api_keys` decrypted at
  runtime (Fernet), env fallback, live refresh via `/config`.

## Documentation

Full technical documentation lives in [`docs/`](docs/README.md).

| Document | Contents |
|---|---|
| [docs/README.md](docs/README.md) | Docs index + source map |
| [Architecture](docs/architecture.md) | System position, components, lifecycle, end-to-end data flows |
| [API Endpoints](docs/api-endpoints.md) | Every endpoint: schemas, flows, error codes |
| [Chat Flow](docs/chat-flow.md) | `/chat` pipeline in depth: tools, parse fallback, search, SSE protocol |
| [Embedding](docs/embedding.md) | Providers, Qdrant payload schema, filters, collection management |
| [Search Quality](docs/search-quality.md) | Hybrid dense+sparse pipeline, score thresholds, `prefer_lang`, query augmentation, eval workflow + tuning |
| [LLM Client & Prompts](docs/llm.md) | Retries, debug capture, prompts, language hints |
| [Configuration](docs/configuration.md) | Env vars, `/config` runtime overrides, bootstrap flow |
| [Logging](docs/logging.md) | Loguru setup, context propagation, PII redaction |
| [Activity Logging](docs/activity-logging.md) | Per-day JSONL request/response logs |
| [Testing](docs/testing.md) | Test suite, fixtures, coverage, patterns |
| [Deployment](docs/deployment.md) | Docker, compose profiles, CI/CD, Swarm |
| [Project Board Automation](docs/project-board-automation.md) | Commit-to-board workflow: issue references, auto-tasks, `[skip-task]` |
| [Colab Embedding Server](docs/colab_embedding_server.ipynb) | Notebook for a remote GPU embedding server |

## Development

```bash
make lint            # ruff check
make typecheck       # mypy (strict)
make format-check    # ruff format --check
make test            # pytest + coverage (~90%+, 533 tests)
make docker-build    # full stack via compose (profile 'full')
```

## Environment Variables

Full reference in [docs/configuration.md](docs/configuration.md). The most
important ones:

| Variable | Default | Description |
|---|---|---|
| `OPENCODE_ZEN_API_KEY` | — | Fallback LLM API key (OpenCode Zen) |
| `ENGINE_API_KEY` | `""` | Shared secret the API sends as `X-API-Key` (empty disables the auth guard) |
| `LLM_ENCRYPTION_KEY` | — | Fernet key for DB-stored LLM keys (must match API) |
| `QDRANT_URL` / `QDRANT_COLLECTION` | `http://localhost:6333` / `products` | Vector store |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL (LLM key resolution only) |
| `LLM_MODEL` / `USER_COMM_MODEL` | `deepseek-v4-flash-free` | Default / conversational LLM |
| `EMBEDDING_PROVIDER` | `sentence_transformer` | `sentence_transformer` \| `tei` \| `openrouter` |
| `EMBEDDING_MODEL` / `EMBEDDING_DIMENSIONS` | `Qwen/Qwen3-Embedding-4B` / `2560` | Embedding model + dimensions **fallback** (known models resolve dims from name: 0.6B→1024, 4B→2560, 8B→4096) |
| `AI_ENGINE_CONFIG_PATH` | `/data/engine-config.json` | Runtime config file (Docker) |
| `ACTIVITY_LOG_DIR` | `./logs` | JSONL activity log directory |

## CI Runners

CI, build, and deploy run on **self-hosted GitHub Actions runners** on the
TeaServer host (org Actions minutes are quota-limited). The runner service users
(`runner-api`, `runner-web-ui`, `runner-ai-engine`, `runner-mobile`) belong to
the `docker` group so `docker build`/`docker push` work; restart the runner
services after changing group membership (`sudo systemctl restart
actions.runner.TEA-assist-product-graph-ai-engine.tea-ai-engine-runner.service`).
