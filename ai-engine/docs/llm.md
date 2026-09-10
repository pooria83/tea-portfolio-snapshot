# LLM Client & Prompts

Everything about talking to LLMs: the `LLMClient` wrapper, retry policy,
debug capture, streaming, language hints, and every prompt template.

## 1. LLMClient overview

`app/services/llm_client.py` — a thin, hardened wrapper around the OpenAI
Python SDK (`AsyncOpenAI`), built by `create_openai_client`
(`app/core/http_client.py`), which:

- passes `http_client=httpx2.AsyncClient(trust_env=False)` — since openai v3
  the SDK **vendors its own httpx fork (`httpx2`) for transport**, so the
  no-proxy client must be built from that fork for `trust_env=False` to
  actually apply;
- sets `default_headers={"User-Agent": "opencode/1.18.23
  ai-sdk/provider-utils/4.0.23 runtime/bun/1.3.14"}` — OpenCode Zen's
  free-tier gate keys off the `User-Agent`; requests without the opencode UA
  are rejected with 429 `FreeUsageLimitError`.

```python
LLMClient(api_key: str, base_url: str, model: str, provider: str = "")
```

The constructor keeps a masked key (`mask_api_key`: first 6 + last 4 chars)
exposed as `log_context` (`provider=... api_key=sk-sds........yrut`) and
appended to failure logs; `health()` probes the router endpoint (TTL-cached,
see below).

Muse Spark models (`muse-spark*`) via Zen require the **Responses API**
(`POST /v1/responses`); the Chat Completions endpoint returns `500` for this
family (verified 2026-08-26). `_complete()` auto-detects the prefix, translates
`messages → input`, `tools`, `response_format` → `text.format`, and wraps the
`output[]` (reasoning / `output_text` / `function_call`) back to a
`choices[0].message` shape so callers keep using the same `tool_calls`/`content`
contract for both streaming and non-streaming paths.

Key selection is handled by `resolve_active_api_key`
(`app/services/key_service.py`): the SQL picks the **first active** key row
for the model (`ORDER`-less `LIMIT 1` on `is_active = true` rows) — this is
explicitly **not round-robin** anywhere; decryption failures and missing rows
fall back to the env key.

Both instances are pushable/persistable at runtime via `/config`
(`default_llm_model` / `user_comm_model` / `refresh_llm`) — see
[Configuration](configuration.md).

The engine holds two instances (see [Architecture](architecture.md#22-the-two-llm-clients)):

- `app.state.llm_client` — default LLM (description gen, query parsing)
- `app.state.comm_llm_client` — conversational LLM (chat answers, tools, summaries, titles)

### 1.1 Single funnel: `_complete()`

Every LLM call goes through `_complete(**kwargs)`:

1. Logs the full request: `LLM_REQUEST model={} payload={}` (serialized via `_serialize`, safe for pydantic objects; both request and response payloads pass through the recursive `redact_sensitive` so key-named fields are `[REDACTED]`).
2. Calls `self.client.chat.completions.create(**kwargs)`.
3. On exception → `LLM_FAILED model={} error={}` and re-raises (retry layer above decides).
4. Non-streaming calls log the full response: `LLM_RESPONSE model={} response={}`.
5. `capture_debug=True` appends `{prompt: request, response: response}` to
   `self._captured_debug` — a **FIFO `deque(maxlen=64)`**, not a single slot;
   `take_captured_debug()` pops the **oldest** entry, so concurrent callers
   each get their own capture instead of racing over one shared slot.

### 1.2 Retry policy: `_retry()`

```python
MAX_RETRIES = 2          # 3 attempts total
INITIAL_BACKOFF = 1.0    # backoff: 1s, 2s
```

Every content-based public method funnels through `_complete_content` (which
wraps `_complete` in `_retry`); `chat_with_tools`, `generate_title`, and the
streaming methods keep bespoke closures. `_retry` retries **only transient**
failures — connection/timeout errors, retryable HTTP statuses
(`408/409/425/429/500/502/503/504`) and the app-level `RetryableError`
(raised for empty `choices`/`content` in `classify_intent` and
`generate_title`). Permanent errors (4xx, bad keys) fail fast: logged once and
the "failed" value is returned. On final failure the method returns its
"failed" value (`None`, empty list) — **except** `chat_stream` /
`chat_plain_stream`, which re-raise so the router can fall back to
non-streaming.

## 2. Methods

| Method | Temperature | JSON mode | Notes |
|---|---|---|---|
| `health()` | — | — | Not a completion: `GET {base_url}/models` reachability probe (any HTTP status = up), TTL-cached (healthy 20s / unhealthy 5s); used by `/chat` pre-flight (`PREFLIGHT_LLM_DOWN` is advisory) |
| `generate_descriptions(product_text)` | 0.7 | `json_object` | `DESCRIPTION_SYSTEM_PROMPT`; returns `(descriptions, tokens, prompt)` |
| `generate_with_raw_prompt(raw_prompt)` | 0.7 | `json_object` | Freeform; returns `(descriptions, tokens)` |
| `parse_search_query(raw_query, locale, capture_debug, prompt)` | 0.1 | `json_object` | `PARSE_SEARCH_QUERY_PROMPT` (or custom with `{raw_query}`); returns dict or `None` |
| `chat(user_query, products_context, locale)` | 0.5 | — | Legacy single-call chat (`FASHION_ASSISTANT_PROMPT`); superseded by the context/tool variants |
| `chat_with_tools(messages, tools, locale, capture_debug)` | 0.3 | — | `tool_choice="auto"`; returns `ToolCallResult(answer \| tool_call_args)` or `None` |
| `classify_intent(query, history, locale)` | 0.0 | `json_object` | `ROUTER_PROMPT`; returns `"greeting"` \| `"search"` \| `"general"`, defaults to `"search"` on any failure |
| `chat_plain(messages, locale)` | 0.5 | — | Plain conversational answer without product context (greeting/general branches) |
| `chat_plain_stream(messages, locale)` | 0.5 | — | Streaming variant of `chat_plain` |
| `chat_with_context(messages, products_context, locale)` | 0.5 | — | Restates last user message + context in final turn |
| `chat_stream(messages, locale)` | 0.5 | — | `stream=True`; async generator of text deltas |
| `summarize(messages, previous_summary, locale, prompt)` | 0.2 | — | `SUMMARIZE_PROMPT`; returns `(summary, tokens)` |
| `generate_title(query, locale, prompt)` | 0.2 | — | `TITLE_PROMPT`, `max_tokens=512`; if `content` is empty, extracts the title from `reasoning_content`, preferring the last candidate in the target script (Arabic/Persian for ar/fa); returns `str \| None` |
| `generate_eval_queries(count, locales, catalog_context, prompt)` | 0.8 | `json_object` | `EVAL_QUERIES_PROMPT`; returns `list[{"text", "locale"}]` deduplicated and trimmed to `count`, or `None` |

### 2.1 `ToolCallResult`

```python
@dataclass
class ToolCallResult:
    answer: str | None = None
    tool_call_args: list[dict[str, Any]] | None = None
    tokens_used: int = 0
```

- Multiple tool calls are supported and all returned (`TOOL_CALLS_MULTIPLE`).
- Malformed JSON args are tolerated (`{}` + `TOOL_CALL_BAD_ARGS` log).
- Non-dict args are dropped.

### 2.2 Streaming (`chat_stream`)

- `async for chunk in stream`; skips chunks without `choices`.
- Only `delta.content` is yielded (deltas accumulated for the
  `LLM_STREAM_RESPONSE` log).
- On exception → `LLM_STREAM_FAILED` and **re-raise** (the router falls back
  to `chat_with_context`).

## 3. Prompt templates — `app/services/prompts.py`

All prompts are centralized here (they are also editable at runtime through
the API's prompt-template management; the values here are the built-in
defaults).

### 3.1 `DESCRIPTION_SYSTEM_PROMPT`

Product description writer, 2–3 sentences, EN + AR, JSON `{"en", "ar"}`.
Requires key features (material, fit, occasion/style), natural Arabic, no
invented details. `{product_text}` is the built product text
(`_build_product_text` in `description.py`: name EN/AR, brand, category,
image descriptions, attributes, price).

### 3.2 `PARSE_SEARCH_QUERY_PROMPT`

Search query optimizer. Extracts `rewritten_query` + `filters`:
`color`, `material`, `category`, `brand`, `gender`, `color_family`, `size`.

Key rules embedded in the prompt:

- Rewrite for vector search: **keep every style/design/feature word** the user
  mentions (neckline, sleeve type, fit, occasion, movement type, fragrance
  notes, materials, features) — those are matched by the embedding, not by
  filters; only strip words captured by the fixed filter keys.
- **Translate filter values to English** (Arabic query `فستان أحمر` → `color: ["Red"]`).
- Gender enum: men, women, girls, boys, babies, kids, unisex.
- `color_family`: map concrete colors to the closest of
  red, pink, blue, navy, green, black, gray, white, beige, brown, camel,
  gold, silver, purple, orange, yellow, multicolor.
- Only include explicitly-mentioned filter keys.
- 10 worked examples (EN + AR + watch + perfume cross-category).

Even if the rewrite drops an attribute word, the parse fallback in
`chat.py::_resolve_search` also searches the **raw query verbatim** as an extra
spec when the rewrite differs from the original — words can never be lost.

### 3.3 `ROUTER_PROMPT`

Intent-classification prompt used by `classify_intent` (the conversation
router on the comm LLM, JSON mode, temp 0.0). The model must output exactly
`{"intent": "greeting" | "search" | "general"}`:

- `greeting` — social openers with no product request (hello, thanks,
  small talk, typos/variants).
- `search` — anything that asks for / implies products, **including implicit
  references** ("the red dress I mentioned", follow-ups about color, size,
  brand, price, style, category).
- `general` — everything else: fashion advice, what-to-wear questions,
  store/return questions, unrelated topics.
- Tie-break rule in the prompt: "When in doubt between search and general,
  choose search."

`classify_intent` prepends the last 6 history turns as context and defaults to
`search` on any failure (`ROUTER_FAILED` / unknown intent) so the search flow
stays the safe default. The verdict is logged as `ROUTER_INTENT`.

### 3.4 `FASHION_ASSISTANT_INSTRUCTIONS` / `CHAT_SYSTEM_PROMPT`

Fashion assistant persona. Critical instruction: **do not list/enumerate the
products** (the UI already shows cards) — answer conversationally, describe
best matches (name, brand, price, why it fits), suggest alternatives or ask
clarifying questions when nothing matches.

### 3.5 `SUMMARIZE_PROMPT`

Running-summary summarizer. Must keep: what the user is looking for
(category, color, size, brand, price range), what was recommended and the
user's reaction (liked/disliked/bought), preferences/clarifications/
constraints. Compact bullets, **merge** the previous summary (never verbatim).
Format args: `{previous_summary}`, `{history_text}`, `{locale_hint}`.

### 3.6 `TITLE_PROMPT`

Chat titler: 2–6 words, no quotes/punctuation, summarizes shopping intent
(category, color, style). Format args: `{query}`, `{locale_hint}`.

### 3.7 `EVAL_QUERIES_PROMPT`

Search-eval query designer: generates `{count}` diverse, realistic shopper
queries grounded in `{catalog_context}`, spread across `{locales}`, mixing
specific (category/color/size/brand/material/style words) and broad queries,
written in each query's own locale. JSON `{"queries": [{"text", "locale"}]}`.
Used by `/eval/queries` (admin search-eval panel).

## 4. JSON mode & parsing

- `generate_descriptions` / `generate_with_raw_prompt` / `parse_search_query`
  / `generate_eval_queries` use `response_format={"type": "json_object"}` and
  parse with `json.loads(content)`. A `json.JSONDecodeError` is caught and
  returned as the "failed" value (invalid JSON is not retried).
- `_complete_content` returns `(content, tokens_used)` or `None`; empty
  `choices` yields `None`, empty content yields `(None, tokens)` so token usage
  is still reported.

## 5. Response language hints — `app/services/lang_detect.py`

Every conversational call appends a final user message:

| Detection | Hint |
|---|---|
| fa (Persian chars `پچژگکی`) | "Respond in Farsi." |
| ar (Arabic script) | "Respond in Arabic." |
| en (Latin) | "Respond in English." |
| inconclusive | `_RESPONSE_HINTS[locale]`, else "Respond in the same language as the user's most recent message." |

The **detected language of the user's message wins** over the request `locale`
so multi-lingual users get replies in the language they type.

## 6. Debug capture

- `capture_debug=True` on `parse_search_query` and `chat_with_tools`.
- Captures are appended to a FIFO `deque(maxlen=64)`; `take_captured_debug`
  pops the **oldest** entry (concurrent-safe — each caller gets its own
  capture, oldest first).
- Surfaced to clients as `ChatResponse.debug` / the `{"type": "debug"}` SSE
  frame (validated by `_valid_debug_dict` / `_as_chat_debug` — both must be
  dicts with `prompt` and `response` keys).

## 7. Adding a new LLM capability

1. Add the prompt template to `prompts.py`.
2. Add a method on `LLMClient` that funnels through `_complete` and wraps in `_retry`.
3. Add a router endpoint (or reuse the comm client from an existing one).
4. Cover with unit tests (mock `client.chat.completions.create` — see [Testing](testing.md)).

## 8. Log trail

```
LLM_REQUEST | LLM_RESPONSE | LLM_FAILED | LLM_STREAM_FAILED | LLM_STREAM_RESPONSE
TOOL_CHAT | TOOL_CALLS_MULTIPLE | TOOL_CALL_BAD_ARGS
PARSE_QUERY_FAILED | CHAT_FAILED | CONTEXT_CHAT_FAILED | SUMMARIZE_FAILED | TITLE_FAILED
GEN_DESC | GEN_RAW (per-attempt retry logs)
EVAL_QUERIES_FAILED | EVAL_QUERIES_BAD_SHAPE
ROUTER_INTENT / ROUTER_FAILED (chat.py router hop; see §3.3)
```
