# LLM Management

How LLM models, API keys, and prompt templates are stored and pushed to the AI Engine — the admin surface that makes the whole AI system runtime-configurable without deploys.

## The Admin Surfaces

| Endpoint group | What it manages |
|---|---|
| `/admin/llm/models` | Model registry (model, provider, context window, active flag) |
| `/admin/llm/api-keys` | Encrypted provider API keys (Fernet), multiple per model |
| `/admin/llm/settings` | The two active picks: `default_llm_model_id`, `user_comm_model_id` |
| `/admin/llm/prompt-templates` | The six prompt types with versioned history |

## Models (`llm_models`)

Row: `id` (UUID), `model` (e.g. `gpt-oss-20b`), `provider` (`opencode_zen` | `openrouter`), `context_window` (**nullable**, default `8192` — used for chat history budgeting), `is_active`.

- `GET /admin/llm/models` — the **only** model endpoint. Lists every model with its nested `api_keys[]` (`LLMModelResponse`: `id`, `provider`, `model`, `is_active`, `context_window`, `api_keys[].{id, model_id, name, is_active, masked_key, created_at}`). There are no POST/PUT/DELETE model routes — models are managed by seeding.

## API Keys (`llm_api_keys`)

Row: `LLMApiKey{id, model_id (FK → llm_models.id, NOT NULL), name?, api_key_encrypted (Text, Fernet), is_active}` — **multiple keys per model**; `resolve_model_config` picks the **first active key** of the model (`llm_service`).

- `POST /admin/llm/api-keys` — body `{model_id, name?, api_key}` — encrypts and stores a new key (`201`, returns masked response).
- `PATCH /admin/llm/api-keys/{key_id}/toggle` — flip a key's `is_active`.
- `DELETE /admin/llm/api-keys/{key_id}` — hard-delete one key.

There is **no** key list endpoint, no upsert-by-provider, and no delete-by-provider. The masked key is returned for display only — plaintext never goes back to a client.

Decryption (`decrypt_api_key`) is used only in the config-push path (`resolve_model_config`) — the plaintext travels **API → engine over `/config`**, never back to a client.

## `LLM_ENCRYPTION_KEY` Lifecycle

- The key is read from `settings.llm_encryption_key` (pydantic Settings, not `os.environ`) on first encrypt/decrypt call.
- **Production refuses to start without it**: `_get_cipher()` raises `RuntimeError("LLM_ENCRYPTION_KEY is not set — refusing to start in production with an ephemeral key …")` when the setting is empty and `environment == "production"`.
- In non-production an **ephemeral key** is generated with a logged warning — stored keys become undecryptable after restart.
- The same key must be shared with the AI Engine when it resolves encrypted configs.

## Settings (`llm_settings`)

Single-row semantics: PK is a **UUID string**, and `LLMSettingRepository.get_single()` (`SELECT … LIMIT 1`) is the canonical read; the row is created on first write.

- `GET /admin/llm/settings` — current ids + resolved model names.
- `PUT /admin/llm/settings` — sets ids (existence-only check via `get_model_or_404`); **activeness is enforced at push time**, when `resolve_model_config` requires an active model with an active key (`get_active_with_api_keys`).

### The config push (`forward_model_to_ai`)

On any settings change, the API calls `forward_model_to_ai` once per configured id (default model first, then user-comm model). Each call issues **one** `update_config` request with a **single-entry payload**:

```json
{"default_llm_model": {"model": "mimo-v2.5-free", "api_key": "<decrypted>", "base_url": "https://opencode.ai/zen/v1"}}
```

```json
{"user_comm_model": {"model": "…", "api_key": "…", "base_url": "https://openrouter.ai/api/v1"}}
```

Provider base URLs are mapped in the API (`PROVIDER_BASE_URLS`: `opencode_zen → https://opencode.ai/zen/v1`, `openrouter → https://openrouter.ai/api/v1`). If an id is unset, the model inactive, or its active key undecryptable, that push is skipped with a logged warning — the engine keeps its previous config for that key.

## Prompt Templates (`prompt_templates`)

Versioned content for six types (keys: `pre_prompt`, `ending_prompt`, `chat_assistant`, `parse_query`, `summarize`, `title`).

- `GET /admin/llm/prompt-templates` — current active content per type (`_get_active_content`: newest `created_at` among non-deleted rows).
- `PUT /admin/llm/prompt-templates` — update a type: **deactivate** all rows of that type (`is_active = false`), **insert** a new active row. Full history is retained.
- Seeding: `scripts/seed.py` inserts the `prompt_defaults` content if no active row of that type exists (along with everything else it seeds — see below). There is no `scripts/seed_llm_config.py`.

Defaults live in `services/prompt_defaults.py` (mirrored in the engine repo). **Once seeded, DB is authoritative**: every chat call and description call re-reads the active content and forwards it — changing a template takes effect on the next turn, no restart, no engine redeploy.

## Seeding (`scripts/seed.py`)

`uv run scripts/seed.py` (idempotent) creates:

- **admin** (`admin@productgraph.ai`) and **seller** users.
- **10 LLM models**: `opencode_zen` → `big-pickle`, `mimo-v2.5-free`, `hy3-free`, `nemotron-3-ultra-free`, `nemotron-3.5-lightning-free`, `muse-spark-1.2-contributor-free`, `laguna-s-2.1-free`, `deepseek-v4-flash-free` (plus `north-mini-code-free` legacy); `openrouter` → `nvidia/nemotron-3-embed-1b:free`, `gpt-oss-20b`.
- **9 embed models** matching `EMBEDDING_MODEL_DIMS`: Qwen3 0.6B/4B/8B, F2LLM-v2-4B, jina-embeddings-v5-text-small, BGE-M3, Nomic Embed v2, multilingual-e5-large-instruct, multilingual-e5-base.
- **6 prompt templates** (one per type above).
- The `product_ai_generation_cron = "true"` system setting.
- One Zara scraper header row.

## Bootstrap Webhook

`POST /api/v1/webhook/ai-engine-bootstrap` (called by the engine after its own restart; also gated by `verify_webhook_secret`): the API reads system settings + LLM settings and pushes the complete runtime config (TEI URL, embedding provider, both model configs via per-key `forward_model_to_ai` calls) through `update_config`. This is how the engine recovers its runtime config without touching its own DB.

## System Settings (`system_settings`) — AI-related keys

| Key | Used for |
|---|---|
| `tei_tunnel_url` | TEI (embeddings) base URL for the engine (dev tunnels) |
| `embedding_provider` | embedding provider selection — JSON dict with a `model` key that is the **active embedding model** (`get_active_embedding_model`, returning `(model, dims)`); changing the model triggers an automatic re-index of every product. Vector dims come from `EMBEDDING_MODEL_DIMS` (9 seeded models: 0.6B→1024, 4B→2560, 8B→4096, F2LLM-v2-4B→2560, jina-v5-text-small→1024, BGE-M3→1024, Nomic Embed v2→768, e5-base→768, e5-large-instruct→1024) |
| `product_ai_generation_cron` | master switch for the description cron (`"true"`/`"false"`) |

`PUT /admin/system-settings` upserts a key/value pair and — if the key is AI-related — pushes the config to the engine immediately.

## Testing

`tests/test_admin_llm.py` — model list (empty + with nested API keys), key add/toggle/delete incl. Fernet encryption-at-rest and auth guards. Prompt-template GET/PUT lives in `tests/api/v1/test_prompt_templates.py`; settings cache in `tests/test_llm_settings_cache.py`.
