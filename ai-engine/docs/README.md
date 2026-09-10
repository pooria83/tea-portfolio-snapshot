# AI Engine Documentation

Deep technical documentation for the **Product Graph AI Engine** — the AI
service that powers product description generation, RAG-based conversational
product search, and product embedding for the TEA-assist platform.

## Index

| Document | Contents |
|---|---|
| [Architecture](architecture.md) | System position, components, service lifecycle, end-to-end data flows |
| [API Endpoints](api-endpoints.md) | Every HTTP endpoint: request/response schemas, error codes, behaviors |
| [Chat Flow](chat-flow.md) | The `/chat` pipeline in depth: tool-calling, parse fallback, Qdrant search, streaming SSE protocol |
| [Embedding](embedding.md) | Embedding model abstraction, providers, per-model Qdrant collections (`products-{slug}`), payload schema, filters |
| [Search Quality](search-quality.md) | Hybrid dense+sparse search (`text_bm25`, RRF fusion), model-aware score thresholds, `prefer_lang`, `augment_query_text`, eval endpoints + golden-set workflow, tuning checklist |
| [LLM Client & Prompts](llm.md) | `LLMClient`, retry policy, debug capture, all prompt templates, language hints |
| [Configuration](configuration.md) | Environment variables, runtime `/config` endpoint, bootstrap flow, `ConfigManager` |
| [Logging](logging.md) | Loguru setup, context propagation, PII redaction, middleware |
| [Activity Logging](activity-logging.md) | JSONL request/response activity logs per day |
| [Testing](testing.md) | Test suite layout, fixtures, coverage, how to run |
| [Deployment](deployment.md) | Dockerfile, compose profiles, CI/CD, Swarm deploy |
| [Project Board Automation](project-board-automation.md) | Commit-to-board workflow: issue references, auto-tasks, `[skip-task]` |
| [Colab Embedding Servers](embedding.md) | GPU embedding via Colab notebooks — one per embedding model, `colab_embedding_server*.ipynb` (Qwen3 0.6B/4B/8B, F2LLM-v2-4B, BGE-M3, Nomic v2, jina v5, e5-base, e5-large-instruct) — run, tunnel URL, provider wiring |

## Reading Order

1. **New to the project** → [Architecture](architecture.md), then [API Endpoints](api-endpoints.md).
2. **Working on chat/search** → [Chat Flow](chat-flow.md).
3. **Working on embeddings/vector store** → [Embedding](embedding.md).
4. **Working on search quality / eval / tuning** → [Search Quality](search-quality.md).
5. **Working on model/prompt behavior** → [LLM Client & Prompts](llm.md).
6. **Deploying or debugging runtime config** → [Configuration](configuration.md) + [Deployment](deployment.md).

## Source Map (quick reference)

```
app/
├── main.py                      # FastAPI app, lifespan (clients init), bootstrap loop
├── core/
│   ├── config.py                # Settings — env-var backed pydantic settings
│   ├── logging.py               # loguru setup, contextvars, stdlib interception
│   ├── middleware.py            # LogContextMiddleware (X-Request-Id / X-User-Id)
│   ├── activity_logger.py       # ActivityLoggerMiddleware — JSONL per-day logs
│   ├── auth.py                  # EngineAuthMiddleware — X-API-Key guard
│   ├── health.py                # TTLHealthCache / ping_openai_endpoint / probe_with_cache
│   ├── ssrf.py                  # is_safe_webhook_url — webhook SSRF guard
│   ├── http_client.py           # OpenAI/httpx clients with trust_env=False (+ OpenCode Zen UA)
│   └── crypto.py                # Fernet decrypt for DB-stored LLM keys
├── models/
│   ├── embed_product.py         # EmbedProductRequest
│   ├── embed_text.py            # EmbedTextRequest
│   └── similar.py               # SimilarRequest/SimilarResponse
├── routers/
│   ├── chat.py                  # POST /chat — RAG chat (streaming + tool calling)
│   ├── description.py           # POST /generate-description
│   ├── embed.py                 # POST /embed-product
│   ├── embed_text.py            # POST /embed-text
│   ├── similar.py               # POST /similar — metadata-aware similar products
│   ├── eval.py                  # POST /eval/queries + /eval/search — admin search-eval
│   ├── summarize.py             # POST /summarize
│   ├── title.py                 # POST /title
│   └── config.py                # POST /config — runtime model/provider overrides
├── schemas/
│   ├── chat.py                  # ChatRequest/Response, SearchContext, Summarize/Title schemas
│   ├── eval.py                  # EvalQueries/Search schemas — admin search-eval
│   └── product.py               # ProductData, GenerateDescriptionRequest/Response
└── services/
    ├── llm_client.py            # LLMClient — all OpenAI chat calls, retries, debug capture
    ├── embedding_client.py      # Thin facade over the active EmbeddingModel (model_name, dimensions)
    ├── embedding_dims.py        # embedding_dims_for(model_name) — single source of truth for vector dims
    ├── collection_naming.py     # collection_name_for(model) → per-model Qdrant collection names
    ├── embedding/
    │   ├── registry.py          # create_embedding_model(settings) factory
    │   └── models/              # base.py + sentence_transformer | tei | openrouter
    ├── rag.py                   # RAGService — Qdrant collection, upsert, search, prompt context
    ├── key_service.py           # DB-backed LLM API key resolution (encrypted keys)
    ├── config_manager.py        # Runtime config JSON file (ConfigManager)
    ├── lang_detect.py           # Script-based locale detection + response-language hints
    ├── prompts.py               # All system/user prompt templates
    └── search_tools.py          # search_products tool schema + filter normalization
```
