# Chat Flow — the `/chat` pipeline in depth

`POST /chat` (`app/routers/chat.py`) is the heart of the AI Engine. This
document walks through every step: pre-flight health pings, locale detection,
conversation assembly,
**conversation routing** (intent classification → greeting / search / general),
**search resolution** (tool calling → parse fallback → direct answer), search
execution with merge, the zero-results path, and answer generation
(non-streaming and SSE streaming).

## 1. Request → context preparation

```
POST /chat  ChatRequest{query, locale, limit, history, summary, stream, parse_prompt, system_prompt}
```

### 1.1 Pre-flight health pings

The chat handler opens with two concurrent reachability probes
(`app/core/health.py`):

```python
embedder_ok, llm_ok = await asyncio.gather(embedder.health(), comm_llm.health())
```

A failed ping only logs `PREFLIGHT_EMBEDDER_DOWN` / `PREFLIGHT_LLM_DOWN` and
the request proceeds — the probes are **advisory only, never abort** ("the
real embed call is the arbiter": actual embed/LLM calls carry 60s timeouts and
raise 502 / emit an SSE error frame if an endpoint is truly down).

Implementation (`app/core/health.py`):

- `TTLHealthCache` — verdict cache on monotonic time: healthy results live
  **20s**, unhealthy ones only **5s** (a down service fails fast without being
  hammered by every request).
- `ping_openai_endpoint(base_url)` — `GET {base_url}/models`; **any HTTP
  status counts as reachable** (401/404 still prove the server answers); only
  connection/timeout failures count as down. Two attempts with escalating
  timeouts (**2s → 6s**) absorb brief blips. Never raises.
- `probe_with_cache` — skips the network call entirely on a fresh cache hit.
- Wired into `LLMClient.health()`, `EmbeddingClient.health()` (delegating to
  the active model), and each provider — `tei`/`openrouter` ping their base
  URL; `sentence_transformer` is in-process and always healthy.

### 1.2 Locale detection (`detect_locale`)

```python
effective_locale = detect_locale(request.query) or request.locale
```

`app/services/lang_detect.py` detects the language from the **script** of the
query, with precedence `fa` > `ar` > `en`:

- Persian-specific characters `پ چ ژ گ ک ی` → `"fa"`
- Any other Arabic-script characters (U+0600–U+06FF) → `"ar"`
- Latin letters → `"en"`
- Inconclusive (empty, numbers/emoji only) → `None` (request `locale` wins)

`effective_locale` drives two things:

1. **Product context formatting** — `format_products_for_prompt(products, effective_locale)` reads `product_data[effective_locale]`.
2. **The no-results hint** — `_NO_RESULTS_HINTS[effective_locale]` (ar/fa/en).

The **request `locale`** is separately passed to the LLM answer calls where it
only matters when script detection is inconclusive (see
[LLM Client & Prompts](llm.md#5-response-language-hints)).

### 1.3 Message assembly (`build_messages`)

```
messages = [
  system:  system_prompt or CHAT_SYSTEM_PROMPT
  system:  "Previous conversation summary:\n{summary}"        ← only if summary non-empty
  ...history (role user|assistant pairs)...
  user:    query
]
```

`CHAT_SYSTEM_PROMPT` (= `FASHION_ASSISTANT_INSTRUCTIONS`) tells the model it is
a fashion assistant, **not to enumerate products** (the UI already renders the
cards), and to answer conversationally.

### 1.4 Conversation routing (`classify_intent`)

Before any search resolution, the **comm LLM** classifies the user's intent in
one cheap JSON-mode call (temperature 0.0, `response_format=json_object`,
`ROUTER_PROMPT`):

```python
intent = await comm_llm.classify_intent(request.query, history, locale=request.locale)
# → "greeting" | "search" | "general"
```

The router prompt receives the query (plus up to 6 recent history turns when
present) and must return `{"intent": ...}`. Rules:

| intent | Meaning |
|---|---|
| `greeting` | social openers with no product request (hello/hi/how are you/thanks/small talk, incl. typos) |
| `search` | any request that asks for/mentions/implies products, incl. implicit refs and follow-ups (color, size, brand, price, style, category) |
| `general` | everything else — fashion advice, occasion recommendations, store/return questions |

Ambiguity between search and general resolves to **search**. On any router
failure (unparseable JSON, unknown intent, API error after retries) it defaults
to `search` so the existing search flow stays the safe default. The chosen
intent is logged as `ROUTER_INTENT` and surfaced in the response
`search_context.intent`.

Routing outcomes:

```
intent == greeting → _plain_answer(..., intent="greeting")
intent == general  → _plain_answer(..., intent="general")
intent == search   → _resolve_search (existing tool → parse flow) → Qdrant → answer
```

Greeting and general branches call `chat_plain` (non-streaming) or
`chat_plain_stream` (streaming): a plain conversational answer with **no
product context, no search, products=[]** in the response. `search_context` is
`{intent: <branch>, tool_used: false, specs: []}`.

## 2. Search resolution (`_resolve_search`)

This is the most important logic. It decides *what* to search and *how* to
search it, in three tiers:

```
1. TOOL CALLING   comm_llm.chat_with_tools(messages, [search_products])   ← skipped when use_tools=False (eval)
     ├─ tool call(s)  → specs = [(query, filters), ...]        (tool_used = true)
     ├─ direct answer → return (no search at all)
     └─ exception     → log TOOL_CALL_UNSUPPORTED, fall through
2. PARSE FALLBACK   llm.parse_search_query(query, locale, prompt=parse_prompt)
     ├─ success     → (rewritten_query, filters)
     └─ failure     → raw query, no filters
```

`_resolve_search(comm_llm, llm, request, messages, use_tools=True)`. The
`use_tools=False` variant (used by `/eval/search` for reproducible search
quality evals) skips the tool step entirely and goes straight to the parse
path — same rewritten-query filters + raw-query dual spec, no tool-calling
variance.

### 2.1 Tool-calling path

`chat_with_tools` sends the search messages (with `role != "assistant"`
filtered out — assistant turns are dropped for the tool step) plus a
`response_locale_hint` user message, with `tools=[SEARCH_PRODUCTS_TOOL]`,
`tool_choice="auto"`, temperature 0.3.

The tool (`app/services/search_tools.py`):

```json
{
  "type": "function",
  "function": {
    "name": "search_products",
    "description": "Search the fashion product catalog for items matching the user's request. Resolve implicit references before calling: e.g. 'the red dress I mentioned' becomes query 'red dress'; 'shorter' adds a length filter; 'that same brand' carries the brand forward. Keep the query concise for vector similarity search.",
    "parameters": {
      "type": "object",
      "properties": {
        "query":  {"type": "string", "description": "..."},
        "filters": {"type": "object", "properties": {
          "color": {"type": "array", "items": {"type": "string"}},
          "material": {"type": "array", "items": {"type": "string"}},
          "category": {"type": "array", "items": {"type": "string"}},
          "brand": {"type": "array", "items": {"type": "string"}},
          "gender": {"type": "array", "items": {"type": "string", "enum": ["men","women","girls","boys","babies","kids","unisex"]}},
          "color_family": {"type": "array", "items": {"type": "string", "enum": [10 families]}},
          "size": {"type": "array", "items": {"type": "string"}}
        }, "additionalProperties": false}
      },
      "required": ["query"]
    }
  }
}
```

Outcomes of the single LLM call:

| `message.tool_calls` | `message.content` | Result |
|---|---|---|
| 1+ calls | — | `ToolCallResult(tool_call_args=[...])` — every call becomes a spec; **multiple parallel calls are all executed and merged** |
| none | text | `ToolCallResult(answer=text)` — model answered directly; no search |
| call with malformed args | — | args parsed defensively (`{}` on JSON error, logged `TOOL_CALL_BAD_ARGS`) |

Each `tool_call_args` entry is normalized by `normalize_tool_args(args)`:

- `query` → stripped string; empty query falls back to `request.query`.
- `filters` → `normalize_filters()` (see §2.3).

The tool schema (`SEARCH_PRODUCTS_TOOL`) instructs the model to include every
explicitly mentioned attribute **both** in the query (for vector similarity)
**and** in `filters`, with a concrete example.

### 2.2 Parse fallback path

When the tool call fails or the model doesn't support tools, the **default
LLM** (`llm_client`, not the comm client) runs `parse_search_query`:

- temperature 0.1, `response_format={"type": "json_object"}`.
- Prompt: `PARSE_SEARCH_QUERY_PROMPT` (or custom `parse_prompt` if supplied —
  supports `{raw_query}` placeholder; if absent, the query is appended).
- Expected output: `{"rewritten_query": "...", "filters": {...}}`.
- `rewritten_query` keeps every style/design/feature word (neckline, sleeve,
  fit, occasion, movement type, fragrance notes, materials, features) — those
  are matched by the **embedding**, not by filters — and only strips words
  already captured by the fixed filter keys.
- `filters` may contain `color`, `material`, `category`, `brand`, `gender`,
  `color_family`, `size`; filter values are translated to English. `size` uses
  the size labels as the user said them (e.g. `["M"]`, `["XL"]`, `["42"]`,
  `["EU 42"]`, `["One Size"]`) — the engine normalizes them to canonical tokens.
- Empty/no filters → `filters = None`, raw query used as-is.

**Raw-query dual spec (parse path):** when the rewrite differs from the original
query, `_resolve_search` also searches the **raw query verbatim** as an extra
spec (same filters, color safety net re-applied). Both specs are executed and
merged/deduped, so an attribute/feature word the LLM dropped from the rewrite
(e.g. "chronograph", "vanilla", "V neck") still reaches the vector search.

**Color safety net (both paths):** after normalization, `inject_color_filter()`
scans the final search query for a known color word (via `COLOR_FAMILY_MAP`);
if it finds one and no `color`/`color_family` filter was emitted, it injects
the mapped family bucket (e.g. `"green dress"` → `color_family: ["greens"]`).
This guarantees an exact color filter even when the model skips `filters`
entirely. Existing `color`/`color_family` filters are never overridden.

Debug capture: both paths capture `{prompt, response}` into the client and
return it via `take_captured_debug()` for the `debug` frame/field.

### 2.3 Filter normalization (`normalize_filters`)

Shared by tool args and parse output. Produces typed, case-variant filter
lists for Qdrant `MatchAny`:

| Filter key | Normalization |
|---|---|
| `gender` | Aliases mapped to canonical enum via `GENDER_NORMALIZE_MAP` (e.g. `male`→`men`, `baby`→`babies`, Arabic `رجال`→`men`, `اطفال`→`kids`), deduped |
| `color_family` | Values expanded via `COLOR_FAMILY_MAP` (concrete colors → family buckets, e.g. `burgundy`→`reds-pinks`); family names accepted as-is; deduped |
| `color` | Known colors mapped to their family (added to `color_family`), unknown colors kept as exact case-variant values |
| `material`/`category`/`brand` | Case variants: original, lower, title, upper (e.g. `zara`, `Zara`, `ZARA`) so `MatchAny` hits payload display values |
| `size` | Canonical lowercase tokens via `_size_variants` — letters/words collapse (`M`/`medium`→`m`, `XL`/`extra large`→`xl`), free sizes → `one size`, numeric sizes stay raw, system-prefixed values expand to both the bare number and the system-tagged form (`EU 42`→`["42", "eu:42"]`). Matches the payload `_size` tokens written by the API embed step (products without declared sizes carry the `one size` token) |

If `color_family` ends up populated, `color` is dropped (families supersede
exact colors). Returns `None` when no usable filters remain.

## 3. Search execution (`_run_search_specs`)

Every spec `(search_query, filters)` is executed and results are **merged and
deduplicated by product id**:

```python
for search_query, filters in specs:
    query_vec = await embedder.embed_query(search_query)   # None → HTTP 502 "Embedding failed"
    query_text = augment_query_text(search_query, filters) # filter tokens appended (stemmed-dedupe, size skipped)
    products  = await rag.search(query_vec, limit=limit, filters=filters,
                                 query_text=query_text, prefer_lang=effective_locale)
    merge into result (skip ids already seen)
```

- Embedding failure in the **non-streaming** path raises
  `HTTPException(502, "Embedding failed")`.
- Embedding failure in the **streaming** path yields
  `{"type": "error", "code": "embedding_failed"}` and ends the stream.
- Multiple specs are logged as `SEARCH_MERGED`.

`RAGService.search` (see [Embedding](embedding.md#4-search) and
[Search Quality](search-quality.md)):

```
query_text provided and sparse config enabled?
  ├─ yes → HYBRID prefetch query
  │        dense branch (using="", model-aware score_threshold) +
  │        sparse branch (using="text_bm25", engine-side BM25 tokens)
  │        over pool = limit × 3 (capped 100), fused with Fusion.RRF (k=60)
  └─ no  → plain dense query (byte-identical to pre-hybrid behavior)
filters present?
  ├─ yes → filtered query (FieldCondition + MatchAny on _prefixed keys)
  │        results ≥ limit → done
  │        results < limit → fallback unfiltered search to fill (dedupe)
  │        with a "size" filter: relaxed tiers (color-only, unfiltered) are
  │        re-ranked with SEARCH_SIZE_BONUS (0.2) per hit whose payload _size
  │        overlaps the queried size, so products available in that size
  │        outrank closer vector hits that are not (size remains a hard filter
  │        in the first tier)
  └─ no  → plain unfiltered query
dedupe by product_id with prefer_lang = effective_locale (same-product point
in the detected locale replaces a kept point when it ranks later)
score_threshold = model-aware (0.3 for 1024-dim, 0.25 for 2560-dim,
MIN_SCORE_THRESHOLD otherwise), request limit = limit + 5 (parse headroom)
```

`augment_query_text` appends the spec's filter value tokens (color family,
category, brand — never `size`) to the query text so the sparse branch agrees
with the active filters; duplicates are removed at stemmed-token level.

## 4. Answer generation

### 4.1 Zero results

```
products empty →
  answer = _NO_RESULTS_HINTS[effective_locale]
  ChatResponse(answer=hint, products=[], search_context=..., debug=...)
```

Hints:

| Locale | Hint |
|---|---|
| ar | لم أجد منتجات مطابقة. جرّب بحثاً مختلفاً. |
| fa | محصولی مطابق پیدا نکردم. لطفاً جستجوی دیگری را امتحان کنید. |
| en | I couldn't find any matching products. Try a different search. |

No LLM call is made on this path.

### 4.2 Non-streaming answer (`chat_with_context`)

```python
context = rag.format_products_for_prompt(products, locale=effective_locale)
answer  = await comm_llm.chat_with_context(messages, context, locale=request.locale)
```

`format_products_for_prompt` renders a numbered list from
`product_data[locale]` (fallback `en`): `Name | Brand | Price currency |
Category: name | Attributes: k: v | k: v | Sizes: ...` — with a compact
fallback for payloads without `product_data`.

`chat_with_context` appends a final user turn that **restates the user's last
message** plus the available products plus the locale hint, so the model's last
input still carries the original request.

Answer `None` → `HTTPException(502, "Chat generation failed")`.

### 4.3 Streaming answer (`chat_stream` + `_stream_chat`)

```
SSE stream (media_type="text/event-stream", one JSON object per line):
  [debug]           {"type":"debug","debug":{prompt,response}}     (if captured)
  [assistant_start] {"type":"assistant_start","search_context":{...}}
  [product_cards]   {"type":"product_cards","products":[{id,name,price,currency,brand,image_url,store_id}],"locale":"en"}
  [text_chunk]*     {"type":"text_chunk","delta":"..."}
  [assistant_end]   {"type":"assistant_end"}
```

Greeting/general intents stream the **plain** variant (`_stream_plain` +
`chat_plain_stream`): `assistant_start` (search_context with the intent) →
`product_cards` with `products: []` → `text_chunk`* → `assistant_end`. On a
plain-stream break (`PLAIN_STREAM_FAILED`) the accumulated answer resets and
**one** non-streaming retry (`chat_plain`) runs inside the same stream —
frames already emitted are not replayed; if both fail →
`{"type":"error","code":"chat_failed"}`.

A **direct answer** turn (model answered without searching) streams via
`_stream_direct_answer` — the text is already fully generated, so it is sent
as a single frame batch:

```
[debug]           {"type":"debug", ...}                          (if captured)
[assistant_start] {"type":"assistant_start","search_context":{intent:"search", specs:[]}}
[product_cards]   {"type":"product_cards","products":[]}
[text_chunk]      {"type":"text_chunk","delta":"<whole answer>"}  (single chunk)
[assistant_end]   {"type":"assistant_end"}
```

Failure modes:

| Situation | Behavior |
|---|---|
| embedding fails | `{"type":"error","code":"embedding_failed"}` then end (no `assistant_start`) |
| zero results | `product_cards` with `products: []` + one `text_chunk` with the localized hint + `assistant_end` |
| stream breaks mid-way (`STREAM_FAILED`) | retry once non-streaming (`chat_with_context`); on success the whole answer is sent as one `text_chunk`, then `assistant_end` |
| stream AND fallback fail | `{"type":"error","code":"chat_failed"}` |

The stream messages are `messages + [user: query + available products context]`
(redundant restatement ensures the last user turn carries the context).

Product payloads in `product_cards` are the trimmed `_product_payload` list
(`id`, `name`, `price`, `currency`, `brand`, `image_url`, `store_id`) — the
full `product_data` is **not** streamed.

## 5. Response schema recap

| Case | `answer` | `products` | `search_context` | `debug` |
|---|---|---|---|---|
| Greeting | plain LLM reply | `[]` | `{intent: "greeting", tool_used: false, specs: []}` | — |
| General | plain LLM answer | `[]` | `{intent: "general", tool_used: false, specs: []}` | — |
| Direct answer (no tool call) | model text | `[]` | `{intent: "search", tool_used: false, specs: []}` | optional |
| Normal search | generated text | `ProductRef[]` | `{rewritten_query, filters, tool_used, specs, intent: "search"}` | optional |
| Zero results | localized hint | `[]` | same as above | optional |

`search_context`:
- `rewritten_query`/`filters` mirror **spec[0]** (first executed spec) for backward compatibility.
- `specs` lists **every** executed spec (multiple when the model made parallel tool calls).
- `tool_used` = `true` when the tool-calling path produced the specs.
- `intent` = the routed intent (`greeting` / `general` / `search`) — new with the conversation router.

## 6. Log trail

Every phase is logged with stable prefixes for tracing:

```
CHAT START (query/locale/limit/history)
PREFLIGHT_EMBEDDER_DOWN | PREFLIGHT_LLM_DOWN (advisory — request proceeds)
ROUTER_INTENT query=... intent=... | ROUTER_GREETING | ROUTER_GENERAL | ROUTER_FAILED | ROUTER_UNKNOWN_INTENT
TOOL_CALL_UNSUPPORTED | TOOL_SEARCH specs | TOOL_DIRECT_ANSWER | TOOL_CALL_BAD_ARGS | TOOL_CALLS_MULTIPLE
DIRECT_ANSWER (model answered without searching)
LLM_PARSE original=... rewritten=... filters=...
EMBED_EXCEPTION | EMBED_FAILED | EMBED_DONE
TRACE_QDRANT_HITS_HYBRID collection=... query_text=... pool=... hits=...
SEARCH_FILTERED | SEARCH_FILTERED_RESULTS | SEARCH_FALLBACK | SEARCH_FALLBACK_RESULTS
SEARCH_UNFILTERED | SEARCH_UNFILTERED_RESULTS | SEARCH_MERGED | SEARCH_ZERO_RESULTS
SEARCH_SIZE_TIER remaining=... (size-aware relaxed-tier re-ranking)
LLM_RESPONSE_FAILED | LLM_STREAM_FAILED | STREAM_FAILED | CHAT END
PLAIN_STREAM_FAILED | PLAIN_CHAT_FAILED (greeting/general branches)

EVAL_QUERIES_START / EVAL_QUERIES_DONE (/eval/queries — LLM batch generation)
```
