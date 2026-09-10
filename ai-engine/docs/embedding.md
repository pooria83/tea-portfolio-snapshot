# Embedding & Vector Search

How the AI Engine turns product text into vectors, stores them in Qdrant, and
searches them with filters.

## 1. Embedding model abstraction

`EmbeddingModel` (`app/services/embedding/models/base.py`) is an ABC with:

```python
@property dimensions: int          # vector dimensionality (for collection validation)
@property model_name: str
async embed_query(text)  -> list[float] | None     # user queries (instruct prefix)
async embed_passage(text)-> list[float] | None     # documents (bare text)
async embed_batch(texts) -> list[list[float] | None]
async health() -> bool             # backend reachability probe (TTL-cached per instance)
```

`EmbeddingClient` (`app/services/embedding_client.py`) is a thin facade holding
the active model — routers depend on it, not on the concrete implementation.
It exposes `health()` (delegating to the active model's TTL-cached probe),
which `/chat` uses for its **advisory pre-flight check** before searching: a
failed ping only logs `PREFLIGHT_EMBEDDER_DOWN` and proceeds — the real embed
call is the arbiter (see [Chat Flow](chat-flow.md)).

### 1.0 Dimension mapping — `app/services/embedding_dims.py`

Dimensions are resolved from the model **name**, never hardcoded per provider.
`embedding_dims_for(model_name, fallback=None)` looks the model up in
`EMBEDDING_MODEL_DIMS` (keys are the bare model name; the `Qwen/` org prefix is
stripped before matching so runtime configs that omit it still resolve):

| Model | Dimensions |
|---|---|
| `Qwen3-Embedding-0.6B` | 1024 |
| `Qwen3-Embedding-4B` | 2560 |
| `Qwen3-Embedding-8B` | 4096 |
| `F2LLM-v2-4B` | 2560 |
| `jina-embeddings-v5-text-small` | 1024 |
| `BGE-M3` | 1024 |
| `Nomic Embed v2` | 768 |
| `multilingual-e5-base` | 768 |
| `multilingual-e5-large-instruct` | 1024 |

- Known model → its mapped dimension (e.g. `Qwen3-Embedding-4B` → **2560**).
- Unknown model → *fallback* if passed (usually
  `settings.embedding_dimensions`), otherwise `DEFAULT_EMBEDDING_DIMS` (1024);
  a `logger.warning` is emitted so an unmapped model never silently uses
  arbitrary dimensions.

This module is the **single source of truth** for vector sizes in the engine.
Startup (`main.py`), the runtime factory (`registry.py`) and the `/config`
endpoint (`routers/config.py`) all resolve dims through it — so switching the
embedding model always switches the collection dimensions correctly (the
dimension-mismatch guard in `ensure_collection()` will otherwise fail the
collection with a clear error).

### 1.1 Provider factory — `create_embedding_model(settings)`

Chosen by the `EMBEDDING_PROVIDER` env var:

| Provider | Class | When |
|---|---|---|
| `sentence_transformer` (default) | `SentenceTransformerModel` | Local in-process PyTorch, no container |
| `tei` | `TEIModel` | Local TEI container or Colab tunnel (GPU) |
| `openrouter` | `OpenRouterModel` | OpenRouter API (e.g. Nemotron 3) |
| anything else | — | `ValueError` at startup |

### 1.2 SentenceTransformerModel (default, local CPU)

- Loads `Qwen/Qwen3-Embedding-0.6B` on CPU at startup (this can take ~30s+;
  the model download is cached in `~/.cache/huggingface`).
- **Query prefix** (Qwen3 instruct format):

  ```
  Instruct: Given a web search query, retrieve relevant passages
  Query: {text}
  ```

- **Passage**: bare text, no prefix.
- All encoding runs in the default thread executor
  (`loop.run_in_executor`) so the event loop is never blocked.
- `normalize_embeddings=True` (unit vectors → cosine similarity).
- Historical note: TEI (Candle+MKL) segfaulted with exit 137 on the production
  CPU, which is why the in-process provider is the default.

### 1.3 TEIModel (remote/container)

- OpenAI-compatible client against `TEI_BASE_URL` (e.g. `http://tei:80/v1`
  in compose, or `https://xxx.trycloudflare.com/v1` from Colab).
- Same Qwen3 query instruct prefix; passage bare.
- `set_base_url(url)` swaps the endpoint live — used by runtime config
  (`tei_tunnel_url` on `/config`) and at startup.
- API key is **optional but real when provided** (`TEIModel(base_url, model,
  dimensions, api_key="")` — tei.py): the key is resolved from the DB
  (`llm_api_keys` for the active model) or env at startup (`main.py` lifespan)
  and sent as a Bearer token; only when empty does the client fall back to the
  placeholder `"unused"`. `/config` accepts `api_key` /
  `api_key_encrypted` (Fernet) on `embedding_provider` for TEI too.

#### 1.3.1 Colab GPU embedding servers

For GPU-backed embeddings without a local TEI container, the repo ships a
ready-to-run Colab notebook per embedding model in `docs/`, one per model in
`EMBEDDING_MODEL_DIMS`. Each loads the model on a Colab GPU and exposes an
OpenAI-compatible `/v1/embeddings` endpoint through a Cloudflare tunnel:

| Notebook | Model (catalog name) | HF repo | Dimensions | Notes |
|---|---|---|---|---|
| `docs/colab_embedding_server.ipynb` | `Qwen3-Embedding-0.6B` | `Qwen/Qwen3-Embedding-0.6B` | 1024 | Free-tier friendly |
| `docs/colab_embedding_server_4b.ipynb` | `Qwen3-Embedding-4B` | `Qwen/Qwen3-Embedding-4B` | 2560 | Needs more VRAM; half-precision if it OOMs |
| `docs/colab_embedding_server_8b.ipynb` | `Qwen3-Embedding-8B` | `Qwen/Qwen3-Embedding-8B` | 4096 | May OOM on the free tier — prefer 4B |
| `docs/colab_embedding_server_f2llm-v2-4b.ipynb` | `F2LLM-v2-4B` | `codefuse-ai/F2LLM-v2-4B` | 2560 | Qwen3-based; loaded bf16 (~8 GB) — high-RAM GPU |
| `docs/colab_embedding_server_bge-m3.ipynb` | `BGE-M3` | `BAAI/bge-m3` | 1024 | Dense vectors only (sparse/ColBERT not served) |
| `docs/colab_embedding_server_nomic-embed-v2.ipynb` | `Nomic Embed v2` | `nomic-ai/nomic-embed-text-v2-moe` | 768 | `trust_remote_code=True` + `einops`; `search_query:`/`search_document:` prefixes |
| `docs/colab_embedding_server_jina-v5-text-small.ipynb` | `jina-embeddings-v5-text-small` | `jinaai/jina-embeddings-v5-text-small` | 1024 | Last-token pooling, 32K context |
| `docs/colab_embedding_server_multilingual-e5-base.ipynb` | `multilingual-e5-base` | `intfloat/multilingual-e5-base` | 768 | `query:`/`passage:` prefixes |
| `docs/colab_embedding_server_multilingual-e5-large-instruct.ipynb` | `multilingual-e5-large-instruct` | `intfloat/multilingual-e5-large-instruct` | 1024 | Instruction-tuned; task prefix on queries |

> The catalog name is exactly the bare name in the `embed_models` table and in
> `EMBEDDING_MODEL_DIMS` — use it for `EMBEDDING_MODEL` / `embedding_provider.model`.
> Each notebook serves exactly one hardcoded model.

**To use one:**

1. Open the notebook in Colab (File → **Save a copy in Drive**), attach a GPU
   runtime (Runtime → **Change runtime type** → e.g. T4 GPU), and run cells
   1–4 in order. Cell 2 prints the loaded model's output dimension; cell 4
   prints the `https://*.trycloudflare.com` tunnel URL.
2. Point the engine at the tunnel and switch to the `tei` provider:

   ```
   EMBEDDING_PROVIDER=tei
   TEI_BASE_URL=https://<tunnel>.trycloudflare.com/v1
   ```

   Runtime config can do the same live via `POST /config`
   (`embedding_provider: "tei"` + `tei_base_url`, §3.1 of
   [Configuration](configuration.md)) — the HTTP client's base URL is swapped
   in place with `set_base_url`.
3. Keep the model in sync with the notebook. Each notebook serves exactly one
   hardcoded model, so `EMBEDDING_MODEL` must match it — e.g. the 4B notebook
   needs `EMBEDDING_MODEL=Qwen3-Embedding-4B`. The dims must agree with the
   §1.0 table: a 4B notebook produces 2560-dim vectors and a
   `products-qwen3-embedding-4b` Qdrant collection.
4. From the notebook run Cell 5 (or `curl` the tunnel) to verify the endpoint
   returns vectors of the expected length before restarting the engine.

The tunnel URL is **ephemeral**: restarting the notebook (or its tunnel
process) yields a new URL that must be re-applied via env or `/config`. The
notebooks are per-model, not a multi-model TEI instance.

### 1.4 OpenRouterModel (API)

- Legacy prefix style for Nemotron 3: `query: {text}` / `passage: {text}`.
- Requires `api_key` (resolved from DB or env at startup).

## 2. Qdrant collections (per model)

`RAGService` (`app/services/rag.py`) owns all Qdrant interaction. **Each
embedding model has its own collection**, so vectors of different models
never mix and switching models does not corrupt existing data.

### 2.0 Collection naming — `collection_name_for(model_name)`

`app/services/collection_naming.py` maps a model name to a Qdrant collection
name:

- `collection_slug(model_name)` — lowercase, runs of non-alphanumeric chars
  become a single dash, trimmed (`Qwen/Qwen3-Embedding-0.6B` →
  `qwen-qwen3-embedding-0-6b`; `Qwen3-Embedding-4B` → `qwen3-embedding-4b`).
- `collection_name_for(model_name)` → `products-{slug}` when it fits within
  200 chars, else `products-{sha1(model_name)[:12]}` (Qdrant's 255-char limit).
  Examples: `products-qwen3-embedding-4b`, `products-qwen-qwen3-embedding-0-6b`.
- Legacy `products` collections can be migrated per model with
  `scripts/rename_qdrant_collection.py` (dry-run + real mode).

### 2.1 Bootstrap — `ensure_collection()`

Called at startup (after the collection is selected):

1. List collections; if the active collection is missing → create with
   `VectorParams(size=<dims>, distance=COSINE)`, where `<dims>` is resolved
   via `embedding_dims_for(model_name, settings.embedding_dimensions)` (see
   §1.0) — NOT the raw `.env` value alone, so a runtime model override such as
   `Qwen3-Embedding-4B` always creates a 2560-dim collection. The creation
   branch also registers the BM25 sparse vector `text_bm25` with
   `Modifier.IDF` + `SparseIndexParams(on_disk=True)` (hybrid search §4.2) and
   marks the service sparse-enabled.
2. If it exists → validate its dimensions against the active model's dimensions.
3. On mismatch → `RuntimeError`:
   "collection has dim=X but config expects dim=Y. Drop and recreate the
   collection, then restart."
   (Startup failure is caught in `main.py` → "running in degraded mode".)
   On a dimension-valid **legacy** collection without the sparse config,
   `ensure_collection` adds `text_bm25` in place via `update_collection`; if
   that fails it logs and continues dense-only (graceful fallback).

> **Migrating a stale collection.** If a collection was previously created with
> the wrong dims (e.g. a 1024-dim `products-qwen3-embedding-4b`), drop it so
> the engine recreates it with the correct size:
> `curl -X DELETE http://<qdrant>/collections/products-qwen3-embedding-4b`.

### 2.2 Active collection switching — `set_collection()`

`RAGService.set_collection(name, dimensions)` switches the active collection
and expected dimensions at runtime. Callers:

- **Startup** (`main.py`): after building the `EmbeddingClient`, the RAG
  service targets `collection_name_for(embedding_client.model_name)` with the
  model's dimensions.
- **Runtime config** (`POST /config`, `config.py` `_apply_config`): when the
  embedding provider/model changes, the client is rebuilt and the RAG service
  switches to the new model's collection (and `ensure_collection()` runs for
  it). The response reports the collection switch in `changes["collection"]`.

### 2.2 Point identity

- `embed-product` upserts use `point_id = uuid5(NAMESPACE_DNS, f"{product_id}_{lang}")`
  — **deterministic**, so re-embedding a product+language replaces the same
  point (idempotent).
- `embed-text` never touches Qdrant.

### 2.3 Upsert payload — `upsert_embedding()`

```json
{
  "product_id": "9a3b...",          // original product UUID
  "lang": "en",                     // "en" | "ar" (one point per language)
  "text": "passage text...",        // the embedded passage
  "product_data": {                 // bilingual payload from the API (verbatim)
    "en": {...}, "ar": {...}, "store_id": "..."
  },
  "_color": ["red"],                // flat filter fields from `filters` (as provided,
  "_material": ["cotton"],          //  e.g. _color/_material/_category/_brand/_size)
  "_size": ["m", "42", "eu:42"],
  ...
}
```

The payload is exactly `{product_id, lang, text}` + `product_data` +
the flat filter dict.

## 3. Payload schema and parsing (`_parse_hits`)

On search results, each hit becomes a `ProductRef`:

| `ProductRef` field | Source |
|---|---|
| `id` | payload `product_id`, else Qdrant `hit.id` |
| `name` | `product_data.en.name`, else `product_data.ar.name`, else legacy `payload.name_en`/`name_ar` |
| `price` | `product_data.en.price`, else legacy `payload.price` |
| `currency` | `product_data.en.currency` (default `"SAR"`) |
| `brand` | `product_data.en.brand`, else legacy `payload.brand` |
| `image_url` | `product_data.en.image_url`, else legacy `payload.image_url` |
| `store_id` | `product_data.store_id` |
| `product_data` | the whole bilingual payload (kept for prompt formatting) |

## 4. Search — `RAGService.search(vector, limit, filters)`

```
if filters:
    normalized = {f"_{k}" if not k.startswith("_") else k: v for k, v in filters.items()}
    must = [FieldCondition(key=key, match=MatchAny(any=values)) for key, values if values]
    qdrant_filter = Filter(must=must)
    products = query(vector, limit, qdrant_filter)
    if len(products) >= limit: return products          # filtered search sufficed
    remaining = limit - len(products)
    if "_size" in normalized:                           # size-bonus fill tier
        relaxed = [color-only filter] if color values else []
        filled = fill(relaxed, re-rank +SEARCH_SIZE_BONUS per _size overlap)
        return products + filled
    if color values:                                    # color-only tier
        color_filter = Filter(must=[_color_family|_color MatchAny])
        fill remaining from color tier (deduped)
    fallback = query(vector, remaining)                 # unfiltered
    merge, dedup by id until limit reached
    return products
else:
    return query(vector, limit)                          # unfiltered
```

Underlying `_query`:

- `query_points` with `limit + 5` (headroom for dedup), `with_payload=True`,
  `score_threshold=self.score_threshold` — resolved from the active model's
  dimensions via `SCORE_THRESHOLDS_BY_DIM` (search quality plan item 2):
  1024-dim → **0.3**, 2560-dim → **0.25**, other → `MIN_SCORE_THRESHOLD`
  (**0.3**). `self.score_threshold` is refreshed in `set_collection` when the
  active model changes.
- Qdrant errors are caught → logged, empty result (search degrades to the
  zero-results path).

`search` delegates to **`search_scored`** (`rag.py`), which mirrors the exact
same tiering (hard filter → size-bonus fill → color tier → unfiltered
fallback, deduped throughout) but returns `list[(ProductRef, score)]` keeping
each hit's raw vector score. `/eval/search` uses it so the admin eval panel
gets ranked, scored results without re-querying Qdrant.

Filter keys are auto-prefixed with `_` to match the payload's flat filter
fields. `MatchAny` matches any of the case-variant values produced by
`normalize_filters` (see [Chat Flow](chat-flow.md#23-filter-normalization)).

### 4.1 Language-aware dedupe (prefer_lang)

Every point stores its language (`payload.lang`). `_parse_hits` /
`_parse_hits_scored` dedupe by `product_id` **within each search tier** and,
when `prefer_lang` is passed (chat and eval pass the detected locale —
search quality plan item 1), a later point of the same product whose `lang`
matches the target replaces the earlier higher-ranked point. The retained
point's text and vector language therefore follows the caller's locale
(an AR query gets the AR point's name/attributes in chat context even when
the EN point ranked higher).

### 4.2 Hybrid dense+sparse search (`query_text`)

Every collection carries a named BM25 sparse vector `text_bm25` (client-side
term-frequency tokens via `_tokenize`: NFKD normalization, EN/Arabic/digit
split, light stemming EN (`ies`/`ing`/`ed`/`es`/`s` with `ss`/`us` guards) and
AR (`ات`/`ين`/`ون`/`ة`/`ه`/`ي`), stopword drop EN+AR — search quality plan
items 4/6; `_fnv1a` hash → indices; Qdrant applies `Modifier.IDF`).
`upsert_embedding` writes it alongside the dense vector, boosting product-name
tokens `boost_weight=2.0` (item 5) so the strongest lexical signal ranks
higher.

`search_scored`/`search` accept `query_text`; when provided **and** the
collection has the sparse config (`_sparse_enabled`), `_query_hits` runs a
prefetch query — dense (`using=""`, `score_threshold=self.score_threshold`) +
sparse (`using="text_bm25"`) over a wider pool
(`limit * hybrid_pool_multiplier`, capped `hybrid_pool_max`; defaults 3 / 100,
constructor-tunable — item 7) — fused with `FusionQuery(Fusion.RRF)` (the
installed qdrant-client rejects a `k` argument, so RRF k stays the Qdrant
server default 60). Without `query_text` or with a dense-only collection the
dense path is byte-identical. `similar()` stays dense-only (ref-id queries).

Chat (`_run_search`) and eval (`_run_search_scored`) pass
`query_text=search_query`, where chat/eval also run the query through
`augment_query_text(query, filters)` (item 3): filter values (except `size`)
are tokenized and only stemmed tokens absent from the query are appended, so
the vector query aligns with the filtered subspace without duplicating words
(`Watches`/`watches`/`WATCHES` add nothing; `reds-pinks` appends `pink`).

### 4.1 Attributes are matched by embedding, not filters

Only the fixed keys (`color`, `material`, `category`, `brand`, `gender`,
`color_family`, `size`) become Qdrant filters. **Every other attribute —
neckline, sleeve type, occasion, watch movement type, fragrance notes, etc. —
is matched purely by vector similarity**: the API embed step writes the values
of `is_search_affecting` attributes into the bilingual embed text (as
`- Neckline: Round` / `- نوع الرقبة: دائري`), and the LLM's rewritten query
keeps those words (see [LLM & Prompts](llm.md#32-parse_search_query_prompt)).
There are no per-attribute meta filters and no per-attribute engine code —
enabling an attribute in search is a data-level flag in the API's
`search_affecting_flags.json`, then a re-index.

## 5. Locale-aware prompt formatting — `format_products_for_prompt`

Reads `product_data[locale]` (falls back to `product_data.en`), producing:

```
1. Red Cotton Dress  Brand: Zara  Price: 150.0 SAR  Category: Dresses  Attributes: color: red | material: cotton  Sizes: S, M, L
2. ...
```

- `category` handled as `{name: ...}` dict or plain string.
- `attributes` → `name: value` pairs joined with `|`.
- `available_sizes` joined with `, `.
- Legacy fallback (no `product_data`): `1. name - brand - price currency`.

## 6. Operational notes

| Topic | Note |
|---|---|
| Collections | One per model: `products-{slug}` (`collection_name_for`); the active collection follows the active embedding model |
| Dimensions | Resolved from the model name via `embedding_dims_for()` (§1.0) — the 9 seeded models resolve their own dims (0.6B→1024, 4B/`F2LLM-v2-4B`→2560, 8B→4096, base/multilingual-e5→768, etc.); unmapped models fall back to `EMBEDDING_DIMENSIONS` with a warning. A model change creates/validates its collection at the model's own dims; legacy collections stay untouched until migrated |
| Adding a model | 1) add `<BareModelName>: <dims>` to `EMBEDDING_MODEL_DIMS` (`app/services/embedding_dims.py`), 2) point the runtime config (or `/config`) at it; the engine picks up the collection name + dims automatically |
| Distance | COSINE (vectors normalized) |
| Timeouts | Qdrant client timeout 30s (`AsyncQdrantClient(..., timeout=30)`) |
| Proxy envs | All clients use `trust_env=False` — host proxy vars are ignored |
| Degraded mode | If Qdrant is unreachable at startup the app still boots; searches will return empty results with logged exceptions |

## 7. Changing the embedding provider at runtime

`POST /config` with `{"embedding_provider": {"provider": "...", "api_key": "", "base_url": ""}}`
rebuilds the `EmbeddingClient` live (see [Configuration](configuration.md)).
The RAG service **switches to the new model's collection**
(`set_collection(collection_name_for(model_name), dimensions)` +
`ensure_collection()`). Existing collections are never dropped — the API
drives a re-embed (re-index) so the new collection gets filled. On restart the
engine restores the same collection from the persisted runtime config.

## 8. Webhook delivery policy (`/embed-product`)

After an embed/upsert (success **or** failure), `/embed-product` POSTs
`{product_id, lang, status: done|error, model}` to the caller-supplied
`webhook_url` (`embed.py`):

- **3 attempts total** (`WEBHOOK_MAX_RETRIES = 2`), backoff **1s → 2s**.
- **No retry on client 4xx** — a 4xx response fails immediately ("not
  retrying"); only 5xx responses and connection/timeout exceptions retry.
- **SSRF guard** (`app/core/ssrf.py::is_safe_webhook_url`): HTTPS-only, no
  userinfo, host must resolve to a **public IP** across all resolved addresses
  (loopback/private/link-local/blocked networks rejected — with a DNS-rebind
  re-resolution check), and the POST client sets `follow_redirects=False`.
  An unsafe URL ⇒ the webhook is **silently skipped** (logged, no delivery,
  no retries).
- A failed final `done` webhook flips the endpoint response to
  `{"status": "error", "reason": "webhook delivery failed"}` even though the
  Qdrant upsert succeeded.
