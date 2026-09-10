# Services Deep Dive

Every module in `app/services/` — what it does, its key functions, and the patterns it follows. Services are the **business-logic layer**: they raise typed domain exceptions (never `HTTPException`) and are called by route handlers in `app/api/v1/`.

## Index of Services

| Service | File | Responsibility |
|---|---|---|
| `auth_service` | `services/auth_service.py` | Register, login, refresh rotation, OTP, Google auth |
| `user_service` | `services/user_service.py` | Profile CRUD, phone/Google linking |
| `product_service` | `services/product_service.py` | Generic `products` CRUD (legacy/list view) |
| `product_definition_service` | `services/product_definition_service.py` + `services/product_definition/` package | Full store-product catalog CRUD (the real catalog); helpers split into a subpackage |
| `product_info_service` | `services/product_info_service.py` | `get_product_info()` — UUID→display-name resolution + `minify_product_info()` |
| `embedding_config` | `services/embedding_config.py` | Active embedding model resolution (`get_active_embedding_model`), `EMBEDDING_MODEL_DIMS` map, `get_embedding_dims` |
| `favorite_service` | `services/favorite_service.py` | Favorites: add/remove/list for the current user |
| `store_service` | `services/store_service.py` | Store CRUD (max 3/owner), member management, ownership checks |
| `storage_service` | `services/storage_service.py` | MinIO wrapper (sync client in executor), URL helpers, bucket moves |
| `sms_service` | `services/sms_service.py` | Twilio SMS (dev mock fallback) |
| `chat_service` | `services/chat_service.py` | Chat orchestration: turns, history, compaction, titling |
| `llm_service` | `services/llm_service.py` | LLM model/key admin (Fernet), settings resolution, engine config push |
| `prompt_template_service` | `services/prompt_template_service.py` | Active prompt-template get/update (deactivate-old + insert-new) |
| `system_setting_service` | `services/system_setting_service.py` | Key-value settings upsert; embedding-provider config push to the engine; auto re-index on model change |
| `scraper_header_service` | `services/scraper_header_service.py` | Zara scraper-header CRUD with header-block validation + error tracking |
| `search_eval_service` | `services/search_eval_service.py` | Search-eval golden set: generate/import/list/update, judgments, MRR@10/Recall@10 metrics, eval-search proxy |
| `product_ai_cron` | `services/product_ai_cron.py` | AI description cron (Redis lock, batches, retries) |
| `embedding_cron` | `services/embedding_cron.py` | Embed text building, recovery cron, backfill helpers |
| `ws_manager` | `services/ws_manager.py` | `ConnectionManager` WebSocket registry (+ graceful `close()`) |
| `activity_log_cleanup` | `services/activity_log_cleanup.py` | Purges old `activity_logs` rows |
| `prompt_defaults` | `services/prompt_defaults.py` | Default prompt texts (single source of truth, mirrored in the AI Engine) |

---

## `auth_service` — Identity & Sessions

Functions:

- **`register_user(db, email, username, password, full_name)`** — uniqueness check (`ConflictError` with `E.EMAIL_OR_USERNAME_TAKEN`), bcrypt hash, insert.
- **`authenticate_user(db, email, password)`** — lookup + verify; inactive accounts → `AuthorizationError`.
- **`create_tokens(db, user)`** — issues access + refresh JWT, stores the **hashed** refresh token row (`RefreshTokenRepository`, `hash_token`).
- **`refresh_access_token(db, token)`** — the rotation protocol:
  1. Decode; look up by hash in DB.
  2. If already `revoked` → **reuse detected**: revoke *all* tokens for that user and raise `E.REFRESH_TOKEN_REUSE`.
  3. Otherwise revoke this one and mint a fresh pair.
- **`send_otp(redis, phone)`** — per-phone send cap (`otp_max_send_per_phone`), 6-digit code in Redis with `otp_expire_seconds` TTL; Twilio unless `twilio_bypass` (then logged).
- **`verify_otp(db, redis, phone, code)`** — verify attempt cap (`otp_max_verify_attempts`), code comparison, auto-create user by phone on success. Dev magic code `123456` when `twilio_bypass`.
- **`google_auth(db, id_token_str, client_type)`** — verifies OAuth2 ID token against configured client IDs, then: existing `google_id` → login; existing email → link; else create. Returns tokens.

Redis keys: `otp:{phone}` (code), `otp_send:{phone}` (count, 600s), `otp_verify:{phone}` (count, 600s), `login_attempts:{email}`.

## `user_service` — Profile Management

- `get_user_by_id` — admin lookup.
- `update_user` / `update_user_profile` — avatar URL handling: `move_url_to_bucket(temp → profile)`.
- `send_link_otp` / `verify_link_phone` — same OTP mechanics as auth, scoped to linking a phone to the current user.
- `link_google(db, user, id_token_str)` — attach `google_id` to the current account.

## `product_service` — Generic Products (list view)

Simple CRUD over the legacy `products` table with `list_products(db, pagination, filters)` — filterable/sortable/paginated. This is the admin-facing list; the real catalog lives in `product_definition_service`.

## `product_definition_service` — The Catalog (core domain)

The largest service (771-line main module, plus the `app/services/product_definition/` helper package). Owns everything under `/stores/{store_id}/products` and the public product-definition read endpoints. Key functions:

- `create_store_product` / `update_store_product` / `delete_store_product` — full product lifecycle with images, variants, color sets, pieces, attributes (EAV). Validates option UUIDs against product-type attribute options; supports inline image URL moves from temp bucket.
- `get_store_product(db, product_id, store_id)` — single fetch with `selectinload` for relationships (variants, images, attribute values, brand, category, ai_description_versions).
- `list_store_products` / `search_store_products` — paginated listing; search matches name_en/name_ar (`ILIKE`).
- `list_my_products` / `search_my_products` / `count_my_products` — seller dashboard variants (multi-store, optional store filter, `status` filter for counts).
- `add_product_image` / `update_product_image` / `delete_product_image` / `reorder_product_images` — image lifecycle with view types and variant binding.
- `update_product_variant` / `delete_product_variant` / `generate_variant_combinations` — variant math: cartesian product of selected attribute options for the product type, used by the frontend builder.
- `generate_variant_combinations` returns `[{options: {attr_name: option_name}, price, sku, ...}]`-shaped records for the seller UI.

Pattern note: store-owned mutations go through `_verify_store_owner` (in the route) → `StoreMember` role checks; strict-owner checks for destructive ops.

### `app/services/product_definition/` package

Create/update helpers split out of the main module (imported as private functions):

- **`attributes.py`** — `_resolve_attribute_values`: merges explicit `attribute_values` with auto-derived colors from color sets (`primary_color` attribute code).
- **`images.py`** — `_update_product_images`: replace-all image sync; matches each incoming image's `variant_signature` against current variants' option-id subsets to bind variant images.
- **`pieces.py`** — `_upsert_pieces` / `_upsert_color_sets`: upsert by `sort_order`, preserving existing row ids when order matches.
- **`variants.py`** — `_create_variant`: variant insert + `VariantAttributeOption` links (flush per step).

## `product_info_service` — Product → AI-ready Dictionaries

This is the **bridge between the catalog and the AI system**:

- **`get_product_info(db, product_id, lang)`** — assembles a full product dictionary in the requested locale:
  - Resolves brand name, category chain (walk `parent_id`), product type name.
  - Images: `image_url` normalized via `_resolve_image_url` (MinIO public URL prefix), localized alt text, view type.
  - Attributes: EAV rows joined to `attributes`; values resolved from JSON (composition `[{material, percentage}]`, UUID arrays, single UUID, plain text) into display names via `attribute_options`.
  - Sizes, variants (with localized option names + variant images + discount %), pieces.
- **`minify_product_info(data)`** — strips nulls, replaces images→`image_alt_texts` (max 2), variants→`available_sizes`, removes heavy keys. Used for AI prompts and embedding payloads.

## `store_service` — Stores & Members

- `create_store` — max 3 active stores per owner (`E.STORE_LIMIT_REACHED`); owner auto-added as `owner` member.
- `update_store` — price-unit lock once products exist; logo URL moves temp→store bucket.
- `delete_store` — owner-only.
- `get_store` / `get_user_stores` — returns stores where user is owner OR member; `get_store` returns `(store, my_role)`.
- `add_member` / `remove_member` / `get_members` — member management; owners only add/remove; owner member is protected.

## `storage_service` — MinIO Wrapper

- Wraps the sync `minio` client in `run_in_executor` (thread pool).
- `ensure_bucket` / `set_bucket_public` (public-read bucket policy) — called at startup for each of the 4 buckets.
- `upload_file`, `get_file`, `delete_file`, `stat_file`, `list_files`, `get_presigned_url`, `download_file_iterator`.
- `cross_bucket_move` / `move_file` / `delete_files_by_prefix` — copy + delete semantics (no server-side rename in MinIO for cross-bucket).
- URL helpers: `get_public_url`, `resolve_image_url`, `strip_domain`.
- Module-level `move_url_to_bucket(url, source, dest)` — moves a file only if the URL points into `source`'s bucket; returns the new public URL or the original. Used by profile/avatar/logo flows to promote temp uploads.

## `sms_service` — Twilio

- Lazy client; `send_otp` runs the blocking Twilio call in a single-worker thread executor.
- No credentials configured → logs the code and returns `True` (**dev mock mode**).

## `chat_service` — Chat Orchestration

The heart of the chat feature. See [Chat System](chat-system.md) for the full protocol; here's the shape:

- **`ensure_active_conversation`** — reuse the user's active conversation or create one.
- **`claim_turn`** — the atomic slot claim: `ConversationRepo.claim_message_slot` increments `userMessageCount` in a Mongo `find_one_and_update` (concurrency-safe), auto-closes at `chat_max_messages`. Locale detection (`detect_locale`) upgrades the conversation locale. Returns `(conversation, user_message, summary, history, locale)`.
- **`_build_history`** — last `chat_history_window` messages, budgeted by the active comm model's `context_window` (50% budget from `llm_settings`; default 12000 tokens; fallback estimate `len/4`).
- **`chat_prompts`** — loads active `chat_assistant` + `parse_query` prompt templates from Postgres (`None` ⇒ engine defaults).
- **`enrich_product_names`** — attaches trilingual name/brand fields to product cards from `store_products`/`brands` (single batched query); failures logged, never raised.
- **`persist_assistant`** — saves the assistant message with `product_snapshots` (id, trilingual names, price, currency, normalized image URL, buy_url, store_id), `search_context`, `debug`.
- **`persist_failed`** — assistant message with `status: "failed"` + error code.
- **`maybe_compact`** — rolling compaction: when unsummarized tokens exceed `chat_compact_threshold_tokens`, the oldest batch (minus the history window) is summarized via engine `/summarize`; `summarizedMessageCount` + `summary` recorded.
- **`maybe_title`** — auto-title from the first user message via engine `/title`.
- **`send_message`** — the non-streaming (REST) equivalent of the WS turn: claim → engine `chat_conversational` → persist → compact → title.

## `product_ai_cron` — Description Generation Cron

- **Lock**: Redis `SET cron:product_ai_generation NX EX 600` — single-runner across replicas; released after each cycle.
- **Cycle** (every 300s, 600s timeout): check `product_ai_generation_cron` system setting, resolve `default_llm_model`, loop batches of 10 products missing `ai_description_en` AND `ai_description_ar`.
- **Per product**: `get_product_info` (en) → `minify_product_info` → prompt = `pre_prompt + product JSON + ending_prompt` → `AIEngineClient.generate_description` → save `AIDescriptionVersion` (prompt + model recorded) → update product fields.
- **Retries**: 3 attempts, backoff 1s/3s/9s. On final failure, logged and skipped (product stays pending for next cycle).
- Writes an `activity_logs` `CRON_RUN` row per cycle.

## `embedding_cron` — Embedding Pipeline (per-model)

Two responsibilities:

**1. Embed-text building** — `build_embed_data(product_id, db)` returns a **4-tuple** `(embed_text_en, embed_text_ar, product_data, filters)`:
- `embed_text_en` / `embed_text_ar`: **one monolingual passage per language** (name/category/brand, attribute lines, price, SKU, descriptions incl. AI descriptions, sizes, variants, image alt texts, care instructions + localized enrichment tokens); a language with no usable content yields `None` for that passage.
- `product_data`: minified bilingual `{en: {...}, ar: {...}, store_id}` used as the Qdrant payload.
- `filters`: flat filter fields `_color`, `_material`, `_category`, `_brand`, `_gender`, `_color_family`, `_size` — built from EN+AR product info AND variant option values (bilingual matching), gender normalized (`men/women/girls/boys/babies/kids/unisex`, fallback `unisex`), color aliases (`printed → Multicolor`), color families from `attribute_options.color_family`, deduped; only non-empty fields included.

**2. Per-model status + helpers** — all rows live in `product_embeddings` (one per product × model, `model_name` snapshot):
- `get_active_embedding_model(db)` (in `embedding_config.py`) — reads the `model` key from the `embedding_provider` system setting; returns `(model_name, dimensions)`; fallback `DEFAULT_EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"` / `DEFAULT_EMBEDDING_DIMS = 1024`.
- `get_embedding_dims(model_name)` (in `embedding_config.py`) — dimension lookup via `EMBEDDING_MODEL_DIMS` (bare names, org prefix stripped; 9 seeded models incl. 0.6B→1024, 4B→2560, 8B→4096); unmapped models → `DEFAULT_EMBEDDING_DIMS` with a warning.
- `_ensure_active_model_rows` — inserts missing `pending` rows for the active model (idempotent, `md5(product_id||':'||model_name)` ids).
- `reindex_active_model(db, model_name)` — upserts **every** product to `pending` for the model (`ON CONFLICT DO UPDATE`); used by auto re-index on model change and the admin re-index endpoint.
- `_fetch_stale_products` — active-model rows `pending`/`generating` with `updated_at < now − 2min` (batch 50).
- `fetch_unembedded_products(include_errors)` — for backfill (active model).
- `_embed_single_product` — builds data, sets `pending`, submits **one `embed_product` call per language** (en, ar — each with its own monolingual passage) with `webhook_url` (cron path), or updates the row directly when `webhook_url is None` (backfill path reads the sync response).
- `submit_for_embedding` (serial) / `submit_for_embedding_concurrent` (semaphore, used by the backfill script).
- `run_embedding_recovery_cron` — 60s loop; on stale rows, submits with webhook; logs `CRON_RUN` activity.

## `llm_service` — LLM Models, API Keys & Settings

Backs `/admin/llm/*`. All key material is Fernet-encrypted (`app/core/crypto.py`) and cache-invalidated on write:

- `list_models` / `get_model_or_404` — model catalog with eager-loaded keys.
- `add_api_key(db, model_id, name, api_key)` — create-only insert of an encrypted `LLMApiKey`; invalidates `llm_api_keys` + `llm_models` caches.
- `toggle_api_key(db, key_id)` / `delete_api_key(db, key_id)` — flip `is_active` / hard-delete (no soft delete).
- `get_settings` / `update_settings` — single-row LLM settings (`default_llm_model_id`, `user_comm_model_id`); validates model ids exist.
- `resolve_model_config(db, model_id)` — returns `{model, api_key, base_url}` for an active model with an active key: decrypts the key and maps provider→base URL via `PROVIDER_BASE_URLS` (`opencode_zen` → `https://opencode.ai/zen/v1`, `openrouter` → `https://openrouter.ai/api/v1`). Cached per model (`llm:config:`), fails open to the DB.
- `forward_model_to_ai(...)` — pushes a resolved model config to the engine via `AIEngineClient.update_config` under `default_llm_model` / `user_comm_model`; logs a warning (never raises) when no resolvable active key exists.

## `prompt_template_service` — Prompt Templates

- `get_prompt_response` — active content for all six prompt types (falls back to `prompt_defaults` when no DB row).
- `update_templates(db, body)` — per provided type: deactivate the current active row, insert a fresh `PromptTemplate(is_active=True)` (history-preserving deactivate-old + insert-new pattern); invalidates the `prompt_templates` cache prefix.

## `system_setting_service` — System Settings & Engine Config Push

- `list_settings` — all key-value rows.
- `update_setting(db, ai_client, key, value)` — upsert by key. For the `embedding_provider` key, the value is validated into a JSON config dict (`provider` ∈ `sentence_transformer|tei|openrouter`; TEI requires model registered in `embed_models` + tunnel URL; API keys are Fernet-encrypted in the stored config) before persisting.
- `apply_setting_to_ai_engine(...)` — after commit, pushes `tei_tunnel_url` → `{tei_base_url}` and `embedding_provider` → `{embedding_provider: config}` to the engine via `update_config`. When the embedding **model actually changed**, triggers `reindex_active_model` so every product is re-marked pending for the new model.
- `to_response` — schema mapping helper.

## `scraper_header_service` — Zara Scraper Headers

CRUD over the `ScraperHeader` store (name → raw HTTP header block):

- `list_headers` / `get_header` — admin listing/lookup (`SCRAPER_HEADER_NOT_FOUND`).
- `upsert_header(db, name, raw)` — validates the block via `app/scrapers/zara/header_parser.validate_header_block` (must contain a Cookie header; `ValueError` → route returns `422 scraper_header_invalid`), then creates/replaces the block and resets status to `ready` (clearing error state).
- `clear_header(db, name)` — sets the stored header back to NULL (scraper exits with an error on start until re-supplied).
- `mark_error` / `mark_ready` — called by the scraper pipeline to surface failures (`error_message` truncated to 2000 chars) or reset after a successful run start.

## `search_eval_service` — Search Evaluation

Powers `/admin/search-eval/*` (golden-set management + quality metrics):

- `build_catalog_context(db)` — compact bilingual summary of product types + `is_search_affecting` attributes + sample option values (capped 8000 chars) used as LLM context.
- `generate_queries(...)` — calls engine `/eval/queries`, persists returned rows (`source=llm`, `status=pending`, deduped on `(text, locale)`).
- `import_queries(db, items, admin_id)` — imports golden-set rows (`source=seed`); creates `relevant=True` judgments from `relevant_ids` (status `evaluated` when ids present). Returns `(created, skipped, judgments_created)`.
- `list_queries` / `update_query` — filtered listing; PATCH-style update of `status`/`rewritten_query`/`filters`.
- `save_judgments(...)` — replace-all judgments (delete + insert); flips status to `evaluated` when any judgment is relevant.
- `get_metrics(db)` — MRR@10 (mean 1/min-relevant-rank, ranks ≤ 10 only) + Recall@10 over evaluated queries; overall + per-locale (en/ar); cached under `seval:metrics:` (5 min).
- `eval_search(ai_client, body)` — proxy to engine `/eval/search`; normalizes image URLs, returns rank/score/results plus rewritten query/filters/specs.

## `ws_manager` — WebSocket Manager

`ConnectionManager` — per-user WebSocket registry: `connect`, `disconnect`, `send_to_user` (drops dead sockets), `broadcast`, plus a graceful `close()` that terminates every tracked socket (code 1001) during shutdown and clears the registry. The active chat WS path (`/ws/chat/{id}`) manages its own socket directly in `ws.py` and does not use this registry; it is instantiated on `app.state.ws_manager` at startup and closed first-in-line after activity drain at shutdown.

## `activity_log_cleanup` — Retention

`run_activity_log_cleanup(session_factory, shutdown_event)` — every 24h deletes `activity_logs` older than 60 days (batch DELETE), logs its run. See [Logging](logging.md).

## `prompt_defaults` — Prompt Canon

Defines the six prompt types and their defaults:

| Type | Key | Used by |
|---|---|---|
| `pre_prompt` / `ending_prompt` | description generation | `product_ai_cron`, `generate-descriptions` endpoint |
| `chat_assistant` | chat system prompt | chat flow (WS + REST) |
| `parse_query` | query→filters/rewrite | chat flow (engine-side) |
| `summarize` | rolling compaction | `maybe_compact` |
| `title` | auto-titling | `maybe_title` |

Once seeded, the DB rows are authoritative — the API always sends the active content, and the engine's built-in copies are only fallbacks.
