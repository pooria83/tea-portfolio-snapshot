# Configuration

How the AI Engine is configured: environment variables (startup) and the
runtime config endpoint + file (hot reload without restart).

## 1. Configuration layers

```
1. ENV VARS (Settings, app/core/config.py)      → base configuration at boot
2. RUNTIME CONFIG FILE (ConfigManager)          → persisted overrides
3. POST /config (runtime endpoint)              → applies + persists overrides
4. STARTUP BOOTSTRAP (webhook to the API)       → asks the API to push current settings
```

Priority: runtime config file values override env defaults for the keys they
cover (e.g. `tei_tunnel_url`, `embedding_provider`, `default_llm_model`,
`user_comm_model`).

## 2. Environment variables (Settings)

`app/core/config.py` — pydantic-settings, `.env` file, `extra="ignore"`.

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `"Product Graph AI Engine"` | FastAPI title |
| `DEBUG` | `false` | Log level DEBUG, dev reload |
| `AI_ENGINE_PORT` | `8003` | HTTP port |
| `ENGINE_API_KEY` | `""` | Shared secret the backend API sends as `X-API-Key`; enforced on every route except `/health` (constant-time compare). Empty disables the guard (local dev) |
| `OPENCODE_ZEN_API_KEY` | `""` | Fallback key for OpenCode Zen (`https://opencode.ai/zen/v1`) |
| `OPENROUTER_API_KEY` | `""` | Fallback key for OpenRouter |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter base URL |
| `LLM_ENCRYPTION_KEY` | `""` | Fernet key to decrypt DB-stored LLM keys (must match the API's key) |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint |
| `QDRANT_COLLECTION` | `products` | Legacy default collection name — the engine now targets **per-model** collections `products-{slug}` (see `collection_name_for`); used only as the initial name before the active model resolves |
| `QDRANT_API_KEY` | `None` | Qdrant auth |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL — **only** for LLM key resolution |
| `LLM_MODEL` | `deepseek-v4-flash-free` | Default (non-comm) LLM model id |
| `USER_COMM_MODEL` | `deepseek-v4-flash-free` | Conversational LLM model id (runtime-overridable) |
| `EMBEDDING_PROVIDER` | `sentence_transformer` | `sentence_transformer` \| `tei` \| `openrouter` |
| `EMBEDDING_MODEL` | `Qwen/Qwen3-Embedding-4B` | Model name passed to the provider |
| `EMBEDDING_DIMENSIONS` | `2560` | Vector dimensions **fallback** — only used when the model is not in `EMBEDDING_MODEL_DIMS` (`app/services/embedding_dims.py`). Known models resolve their dims from the model name (see the §1.0 table in [Embedding](embedding.md) — e.g. 0.6B→1024, 4B→2560, 8B→4096) |
| `TEI_BASE_URL` | `http://localhost:8080/v1` | TEI endpoint (local TEI container, or a Colab GPU tunnel from `docs/colab_embedding_server*.ipynb` — one per model, §1.3.1 of [Embedding](embedding.md)) |
| `AI_ENGINE_CONFIG_PATH` | `/data/engine-config.json` | Runtime config JSON path (local dev: `./engine-config.json`) |
| `ACTIVITY_LOG_DIR` | `./logs` | Directory for per-day JSONL activity logs |
| `API_BOOTSTRAP_URL` | `http://api:8000/api/v1/webhook/ai-engine-bootstrap` | API bootstrap webhook URL |

### 2.1 Compose wiring notes (`docker-compose.yml`)

The repo compose file diverges from the Settings defaults above:

- It passes `EMBEDDING_PROVIDER=${EMBEDDING_PROVIDER:-tei}` (Settings default:
  `sentence_transformer`) and pins `EMBEDDING_MODEL`/`EMBEDDING_DIMENSIONS` to
  `Qwen/Qwen3-Embedding-0.6B` / `1024` to match its TEI container — **not** the
  Settings defaults (`Qwen/Qwen3-Embedding-4B`, `2560`).
- Not wired through at all: `ENGINE_API_KEY`, `LLM_ENCRYPTION_KEY`,
  `LLM_MODEL`/`USER_COMM_MODEL`, `API_BOOTSTRAP_URL`, `ACTIVITY_LOG_DIR`,
  `AI_ENGINE_CONFIG_PATH` (compose relies on the code defaults).
- Its `DATABASE_URL` points at a `postgres` host this compose file does not
  define — it assumes the infra stack's Postgres is reachable on the network.

**API key resolution order** (at startup and on `refresh_llm`): DB-stored
encrypted key for the model (`llm_api_keys` + `llm_models`, active flags) →
env fallback → `None` (engine logs a warning; calls will fail with 5xx).
Keys are **not** LLM-only: startup also resolves an active DB key for the
embedding model itself (`resolve_active_api_key`, `OPENROUTER_API_KEY` as
fallback), so TEI/OpenRouter embedders can use stored keys too.

## 3. Runtime config endpoint (`POST /config`)

`app/routers/config.py`. The body is a **partial** dict; every present key is
applied independently. Each change is written to the config file
(`ConfigManager.set`) **and** applied to live objects.

### 3.1 `tei_base_url`

- Persists as `tei_tunnel_url`.
- If the active embedding model is a `TEIModel` → `set_base_url()` swaps the
  endpoint immediately (used to point at a fresh Colab tunnel URL).
- To run the embedding server on Colab, use the per-model GPU notebook in
  `docs/` matching the model — `colab_embedding_server.ipynb` (Qwen3 0.6B),
  `_4b.ipynb` (4B), `_8b.ipynb` (8B), `_f2llm-v2-4b.ipynb` (F2LLM-v2-4B),
  `_bge-m3.ipynb` (BGE-M3), `_nomic-embed-v2.ipynb` (Nomic v2),
  `_jina-v5-text-small.ipynb` (jina v5), `_multilingual-e5-base.ipynb`,
  `_multilingual-e5-large-instruct.ipynb` — §1.3.1 of
  [Embedding](embedding.md). Paste `https://<tunnel>.trycloudflare.com/v1`
  here and set `embedding_model` to the catalog name the notebook serves.

### 3.2 `embedding_provider`

```json
{"embedding_provider": {"provider": "tei", "api_key": "", "base_url": "https://xxx.trycloudflare.com/v1", "model": "Qwen3-Embedding-4B"}}
```

- Rebuilds the model via the same factory logic as startup and replaces
  `app.state.embedding_client`. Dimensions are resolved from the `model` name
  via `embedding_dims_for()` (§1.0 of [Embedding](embedding.md)), so switching
  models switches collection dims too (e.g. 4B → 2560).
- No collection migration — each model gets its **own** collection
  (`set_collection`); the engine never drops or rewrites existing collections.
- If a collection already exists with the wrong dims for the model,
  `ensure_collection()` reports `changes["collection_error"]` and the engine
  runs degraded until the stale collection is dropped.

### 3.3 `default_llm_model` / `user_comm_model`

```json
{"user_comm_model": {"model": "deepseek-v4-flash-free", "api_key": "sk-...", "provider": "opencode_zen"}}
```

- Replaces `app.state.llm_client` / `app.state.comm_llm_client` with a new
  `LLMClient`. Entries accept a `provider` field — `opencode_zen` (default) or
  `openrouter`. Any caller-supplied `base_url` is **ignored entirely**: the URL
  is always the provider-pinned default (`opencode_zen` →
  `https://opencode.ai/zen/v1`, `openrouter` → `OPENROUTER_BASE_URL`), so API
  keys can never be shipped to an arbitrary host.

### 3.4 `refresh_llm`

```json
{"refresh_llm": true}
```

- Re-resolves both keys from PostgreSQL and rebuilds both clients.
- The default model name comes from the persisted runtime config
  (`default_llm_model`) if set, else `LLM_MODEL`; the comm model name comes
  from the runtime config (`user_comm_model`) if set, else `USER_COMM_MODEL`.

### 3.5 Response

```json
{"status": "ok", "changes": {"user_comm_model": "deepseek-v4-flash-free", "refresh_llm": "ok"}}
```

`changes` contains only the keys that were applied.

## 4. Bootstrap flow

`_bootstrap_loop` in `app/main.py` runs on **every** startup, unconditionally:

- After an initial 2s delay it `POST`s `{API_BOOTSTRAP_URL}` (the API's
  `/api/v1/webhook/ai-engine-bootstrap`) with exponential backoff: starting at
  5s, doubling per attempt, capped at 60s, for up to `BOOTSTRAP_MAX_ATTEMPTS`
  = 12 attempts; then it gives up with an error log (the engine keeps running
  on env/config defaults).
- The loop only logs the response status — applying settings is a **push**
  model: the API reacts to the webhook by calling the engine's `POST /config`
  (§3), which applies and persists the overrides. The loop never reloads the
  config file itself.
- An existing config file does **not** skip the loop: persisted values say
  nothing about whether LLM models/keys are still current, so every start
  re-asks the API (the call is idempotent).

Use case: bootstrap is a **refresh mechanism on every start**, not first-run
provisioning — the API remains the source of truth for model credentials/URLs.

## 5. ConfigManager (file persistence)

`app/services/config_manager.py`:

| Method | Behavior |
|---|---|
| `_load()` | Reads JSON from `AI_ENGINE_CONFIG_PATH` (missing file → defaults, logged) |
| `_save()` | Creates parent dirs, writes JSON atomically-ish |
| `reload()` | Re-reads from disk (utility; the bootstrap loop no longer calls it) |
| `has_config()` | Whether any data was loaded |
| `get(key, default)` | String value |
| `set(key, value)` | Update + persist |

Keys persisted by `POST /config`: `embedding_provider`, `embedding_model`,
`embedding_base_url`, `tei_tunnel_url`, `default_llm_model`,
`user_comm_model`. Example content:

```json
{"embedding_provider": "tei", "embedding_model": "Qwen3-Embedding-4B", "embedding_base_url": "https://xxx.trycloudflare.com/v1", "tei_tunnel_url": "https://xxx.trycloudflare.com/v1", "default_llm_model": "deepseek-v4-flash-free", "user_comm_model": "deepseek-v4-flash-free"}
```

In Docker the file lives at `/data/engine-config.json` on a volume so it
survives restarts.

## 6. Changing configuration safely

| Change | Safe path |
|---|---|
| Embedding provider / model | `POST /config` (live) — client rebuilt + collection switched to the model's `products-{slug}`; the API drives a re-embed (re-index) for the new model. |
| LLM model for chat | `POST /config` `user_comm_model` |
| LLM API key | `POST /config` `refresh_llm` (DB keys), or restart after env change |
| TEI tunnel URL | `POST /config` `tei_base_url` (live swap) |
| Qdrant / DB endpoints | Env var + restart |
