# Testing

How to run, what is covered, and how the suite is organized.

## 1. Commands

| Command | What it runs |
|---|---|
| `make test` | `uv run pytest` — full suite with coverage report |
| `make test-cov` | pytest with HTML coverage report |
| `make lint` | `uv run ruff check app/` |
| `make typecheck` | `uv run mypy app/` (strict mode) |
| `make format-check` | `uv run ruff format app/ --check` |
| `make format` | `uv run ruff format app/` |
| `make setup` | copy `.env.example` + `uv sync --extra dev` |

Pre-commit (`.pre-commit-config.yaml`): ruff (`--fix`) + ruff-format → mypy →
pytest → trailing-whitespace/end-of-file/check-yaml/check-added-large-files
(`--maxkb=1024`)/check-merge-conflict/debug-statements/detect-private-key.

CI runs the same gates in `quality` (see [Deployment](deployment.md#3-cicd)).

## 2. Suite stats

- **533 tests** (as of the last full run, `pytest --collect-only`: 533 across
  35 files), all passing.
- Coverage: **~90.6%** (pytest gate: `--cov-fail-under=50`).
- `pytest.ini_options`: `asyncio_mode = "auto"`,
  `asyncio_default_test_loop_scope = "session"`, `testpaths = ["tests"]`,
  `addopts = "-v --cov=app --cov-report=term-missing --cov-fail-under=50"`.
- Note: CI's `quality` job pins Python **3.13** while the production Docker
  image builds on Python **3.14** — a small version skew to keep in mind when
  a failure only reproduces in one of the two.

## 3. Layout

```
tests/
├── conftest.py                    # shared fixtures (see §4)
├── test_activity_logger.py        # JSONL activity logging (17 tests)
├── test_build_product_text.py     # _build_product_text in description.py
├── test_chat_router.py            # /chat: tools, parse fallback, direct answer, streaming, errors
├── test_collection_naming.py      # collection_name_for per-model naming
├── test_config.py                 # Settings behavior
├── test_config_manager.py         # ConfigManager file load/save/reload
├── test_config_router.py          # POST /config applying overrides
├── test_crypto.py                 # Fernet decrypt
├── test_description_router.py     # /generate-description + model override + 502s
├── test_embed_router.py           # /embed-product + webhook retries
├── test_embed_text_router.py      # /embed-text
├── test_embedding_client.py       # facade delegation
├── test_embedding_dims.py         # dimension mapping by model name + fallback
├── test_eval_router.py            # /eval/queries + /eval/search (parse-path scoring)
├── test_health.py                 # GET /health
├── test_http_client.py            # trust_env=False clients, proxy isolation
├── test_key_service.py            # DB key resolution + decryption fallbacks
├── test_lang_detect.py            # script detection + hints
├── test_llm_client.py             # retries, JSON parsing, tools, streaming, debug capture
├── test_logging.py                # loguru setup, stdlib interception, PII filter
├── test_main.py                   # app wiring, lifespan, middleware registration
├── test_middleware.py             # LogContextMiddleware header → contextvars + EngineAuthMiddleware (X-API-Key, 401 paths, empty-secret bypass)
├── test_openrouter_model.py       # OpenRouter embedding model
├── test_rag_hybrid.py             # BM25 tokenizer/sparse TF, sparse config ensure/fallback, prefetch+RRF shape, dense fallback without query_text
├── test_rag.py                    # search filters/fallback/parse_hits/format context
├── test_registry.py               # embedding model factory
├── test_schemas.py                # pydantic validation (limits, defaults)
├── test_search_tools.py           # search_products tool schema + filter normalization (incl. Arabic, size variants)
├── test_sentence_transformer_model.py  # local model (query prefix, executor)
├── test_similar_router.py         # /similar tiering, 404, language-preference
├── test_ssrf.py                   # SSRF guards (private-IP blocklist on outbound URLs)
├── test_summarize_router.py       # /summarize incl. empty-message shortcut
├── test_tei_model.py              # TEI model (base URL swap, dimensions)
├── test_title_router.py           # /title
└── test_trace_logging.py          # always-on TRACE_* log chains for /chat + /similar
```

## 4. Fixtures (`conftest.py`)

| Fixture | Purpose |
|---|---|
| `settings` | `Settings` with test values (no real secrets) |
| `mock_openai_chat` / `mock_openai_embedding` | AsyncMocks for completions/embeddings |
| `anyio_backend` | Pins the anyio backend to `"asyncio"` for async tests |
| `mock_openai_client` | Patches **both** `app.core.http_client.AsyncOpenAI` and `app.services.embedding_client.AsyncOpenAI` (the openai-v3 transport path) — every LLM/embedding call is intercepted |
| `mock_qdrant_client` | AsyncMock Qdrant client (collections, upsert, query) |
| `llm_client` / `embedding_client` / `rag_service` | Real classes wired to the mocks |
| `mock_llm_client` / `mock_embedder` / `mock_rag` | MagicMocks speced to the real classes for router tests |
| `test_app` / `test_client` | FastAPI app with the six routers (description, chat, summarize, title, similar, eval) + overridden dependencies; `httpx.ASGITransport` client |

Test style: `async def` tests with `pytest.mark.asyncio` auto mode; router
tests assert status codes, response shapes, and error paths (e.g. 502 on
model resolution failure).

## 5. Testing patterns to follow

1. **Never hit real services** — mock the OpenAI client and Qdrant client at
   the boundary (`patch("app.core.http_client.AsyncOpenAI")`).
2. **Cover the fallback paths** — `chat_with_tools` returning `None` must
   exercise `parse_search_query`; direct answers must skip search entirely.
3. **Streaming** — consume the SSE generator and assert the exact frame
   sequence (`debug` → `assistant_start` → `product_cards` → `text_chunk`* →
   `assistant_end`), including the `embedding_failed` / `chat_failed` frames.
4. **Retries** — a raising mock must be retried `MAX_RETRIES + 1` times and
   end with the "failed" return value.
5. **Hybrid search** (`test_rag_hybrid.py`) — tokenizer unit tests (NFKD, EN/
   Arabic split, stemming, stopwords, FNV-1a hashing, name boost ×2); sparse
   config ensure/update fallback; prefetch query shape (pool = limit × 3,
   capped 100, dense + `text_bm25` branches, `Fusion.RRF`); and the dense-only
   fallback when `query_text` is absent/empty or the collection lacks the
   sparse config.
6. **SSRF guards** (`test_ssrf.py`) — outbound URLs resolving to private IPs
   are blocked.
7. **Coverage floor** — the CI gate is 50%, the suite currently sits well
   above it; keep new code tested.
