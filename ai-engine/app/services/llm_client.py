import asyncio
import contextlib
import json
import re
from collections import deque
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import Any, TypeVar, cast

from loguru import logger
from openai import APIConnectionError, APITimeoutError
from pydantic import BaseModel

from app.core.health import TTLHealthCache, ping_openai_endpoint, probe_with_cache
from app.core.http_client import create_openai_client
from app.services.lang_detect import _ARABIC_SCRIPT_RE, _LATIN_RE, detect_locale, response_locale_hint
from app.services.prompts import (
    DESCRIPTION_SYSTEM_PROMPT,
    EVAL_QUERIES_PROMPT,
    FASHION_ASSISTANT_PROMPT,
    PARSE_SEARCH_QUERY_PROMPT,
    ROUTER_PROMPT,
    SUMMARIZE_PROMPT,
    TITLE_PROMPT,
)

T = TypeVar("T")

MAX_RETRIES = 2
INITIAL_BACKOFF = 1.0

# Models that require the OpenAI Responses API (POST /v1/responses) instead of
# Chat Completions. Muse Spark via Zen is one of them; Zen's /chat/completions
# returns 500 while /responses succeeds (verified 2026-08-26).
_RESPONSES_MODEL_PREFIXES = ("muse-spark",)


def _is_responses_model(model: str) -> bool:
    return model.startswith(_RESPONSES_MODEL_PREFIXES)


def _chat_to_responses_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Translate Chat Completions kwargs to Responses API kwargs."""
    out: dict[str, Any] = {"model": kwargs["model"]}
    if "messages" in kwargs:
        out["input"] = kwargs["messages"]
    if "tools" in kwargs:
        tools: list[dict[str, Any]] = []
        for t in kwargs["tools"]:
            if t.get("type") == "function" and "function" in t:
                fn = t["function"]
                tools.append(
                    {
                        "type": "function",
                        "name": fn["name"],
                        "description": fn.get("description", ""),
                        "parameters": fn.get("parameters", {}),
                    }
                )
            else:
                tools.append(t)
        out["tools"] = tools
    if "tool_choice" in kwargs:
        out["tool_choice"] = kwargs["tool_choice"]
    if "temperature" in kwargs:
        out["temperature"] = kwargs["temperature"]
    if "response_format" in kwargs:
        rf = kwargs["response_format"]
        if isinstance(rf, dict) and rf.get("type") == "json_object":
            out["text"] = {"format": {"type": "json_object"}}
    if "stream" in kwargs:
        out["stream"] = kwargs["stream"]
    if "max_tokens" in kwargs:
        out["max_output_tokens"] = kwargs["max_tokens"]
    if "max_output_tokens" in kwargs:
        out["max_output_tokens"] = kwargs["max_output_tokens"]
    return out


def _wrap_responses_as_chat(resp: Any) -> Any:
    """Wrap a Responses API response to look like a Chat Completions response.

    Callers expect ``resp.choices[0].message.content`` and
    ``resp.choices[0].message.tool_calls[*].function.{name,arguments}``.
    """
    text_parts: list[str] = []
    tool_items: list[Any] = []
    for item in getattr(resp, "output", []) or []:
        t = getattr(item, "type", None)
        if t == "message":
            for c in getattr(item, "content", []) or []:
                if getattr(c, "type", None) == "output_text":
                    text_parts.append(getattr(c, "text", "") or "")
        elif t == "function_call":
            tool_items.append(item)

    text: str | None = "".join(text_parts) if text_parts else None

    class _MockFunction:
        def __init__(self, name: str, arguments: str) -> None:
            self.name = name
            self.arguments = arguments

    class _MockToolCall:
        def __init__(self, item: Any) -> None:
            self.id = getattr(item, "call_id", None) or getattr(item, "id", None)
            self.function = _MockFunction(
                getattr(item, "name", ""),
                getattr(item, "arguments", "") or "{}",
            )

    class _MockMessage:
        def __init__(self, content: str | None, items: list[Any]) -> None:
            self.content = content
            self.tool_calls = [_MockToolCall(it) for it in items] if items else None
            self.reasoning_content = None

    class _MockChoice:
        def __init__(self, msg: Any) -> None:
            self.message = msg

    class _MockUsage:
        def __init__(self, u: Any) -> None:
            self.total_tokens = getattr(u, "total_tokens", 0) if u is not None else 0

    class _MockResp:
        def __init__(self, raw: Any, msg: Any) -> None:
            self.choices = [_MockChoice(msg)]
            self.usage = _MockUsage(getattr(raw, "usage", None))
            self._raw = raw

    return _MockResp(resp, _MockMessage(text, tool_items))


_RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


class RetryableError(Exception):
    """Application-level transient failure worth retrying (e.g. empty LLM content)."""


def _is_transient_error(exc: Exception) -> bool:
    """Return True only for errors worth retrying: connection/timeout failures,
    retryable HTTP statuses (5xx, 429, ...) and app-level RetryableError.
    Permanent client errors (400, 401, 403, 404, 422) and unknown exceptions
    fail fast instead, so a bad request or bad key never triggers wasted retries."""
    if isinstance(exc, RetryableError):
        return True
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and status in _RETRYABLE_STATUS_CODES:
        return True
    return isinstance(exc, (APIConnectionError, APITimeoutError))


def mask_api_key(key: str) -> str:
    """Mask an API key, keeping the first 6 and last 4 chars: ``sk-sds........yrut``."""
    if not key:
        return ""
    if len(key) <= 10:
        return "****"
    return f"{key[:6]}........{key[-4:]}"


_SENSITIVE_KEYS = {"api_key", "apikey", "api-key", "authorization", "token", "password", "secret", "cookie"}


def redact_sensitive(value: Any) -> Any:
    """Recursively replace known sensitive fields with a placeholder, so LLM
    payloads logged at DEBUG level never leak keys or secrets."""
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if isinstance(k, str) and k.lower() in _SENSITIVE_KEYS and not isinstance(v, (dict, list)) else redact_sensitive(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_sensitive(v) for v in value]
    return value


@dataclass
class ToolCallResult:
    """Outcome of a single LLM call with tools available."""

    answer: str | None = None
    tool_call_args: list[dict[str, Any]] | None = None
    tokens_used: int = 0


async def _retry(coro_factory: Callable[[], Any], label: str = "", context: str = "") -> Any:
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            if not _is_transient_error(exc):
                logger.error("{} failed (non-transient, not retried): {} {}", label, exc, context)
                return None
            if attempt < MAX_RETRIES:
                backoff = INITIAL_BACKOFF * (2**attempt)
                logger.warning("{} attempt {}/{} failed: {} — retrying in {}s {}", label, attempt + 1, MAX_RETRIES + 1, exc, backoff, context)
                await asyncio.sleep(backoff)
    logger.error("{} failed after {} attempts: {} {}", label, MAX_RETRIES + 1, last_exc, context)
    return None


class LLMClient:
    def __init__(self, api_key: str, base_url: str, model: str, provider: str = "") -> None:
        self.client = create_openai_client(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model
        self.base_url = base_url
        self._provider = provider
        self._masked_key = mask_api_key(api_key)
        self._captured_debug: deque[dict[str, Any]] = deque(maxlen=64)
        self._health = TTLHealthCache()

    async def health(self) -> bool:
        """Reachability probe for the LLM router (GET /models, cached)."""
        return await probe_with_cache(lambda: ping_openai_endpoint(self.base_url), self._health)

    @property
    def log_context(self) -> str:
        return f"provider={self._provider or 'unknown'} api_key={self._masked_key}"

    @staticmethod
    def _serialize(value: Any) -> str:
        try:
            if isinstance(value, BaseModel):
                return json.dumps(value.model_dump(), ensure_ascii=False, default=str)
            return json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            return str(value)

    async def _complete(self, **kwargs: Any) -> Any:
        """Single funnel for all LLM calls: full request logged before sending,
        full response logged after receiving, failure logged on error."""
        capture = bool(kwargs.pop("capture_debug", False))
        logger.info("LLM_REQUEST model={} payload={}", self.model, self._serialize(redact_sensitive(kwargs)))
        # Muse Spark via Zen requires the Responses API (POST /v1/responses).
        # The Chat Completions endpoint returns 500 for this family (verified
        # 2026-08-26: minimal payload with muse-spark-1.2-contributor-free 500s
        # on /chat/completions but succeeds on /responses).
        is_resp = _is_responses_model(self.model)
        if is_resp:
            rkwargs = _chat_to_responses_kwargs(kwargs)
            logger.info(
                "LLM_REQUEST_RESPONSES model={} payload={}",
                self.model,
                self._serialize(redact_sensitive(rkwargs)),
            )
            try:
                if kwargs.get("stream"):
                    # Streaming Responses API: wrap to look like chat chunks.
                    raw_stream = await self.client.responses.create(**rkwargs)

                    async def _wrap_stream() -> Any:
                        try:
                            async for event in raw_stream:
                                t = getattr(event, "type", "")
                                if t == "response.output_text.delta":
                                    delta = getattr(event, "delta", "") or ""

                                    class _Delta:
                                        content = delta

                                    class _Choice:
                                        delta = _Delta()

                                    class _Chunk:
                                        choices = [_Choice()]

                                    yield _Chunk()
                                elif t == "response.completed":
                                    # Let the iterator exhaust naturally; no break needed
                                    continue
                        finally:
                            with contextlib.suppress(Exception):
                                await raw_stream.aclose()

                    return _wrap_stream()
                else:
                    raw = await self.client.responses.create(**rkwargs)
                    # Wrap to chat-like shape so callers keep using .choices[0].message
                    wrapped = _wrap_responses_as_chat(raw)
                    logger.info(
                        "LLM_RESPONSE model={} response={}",
                        self.model,
                        self._serialize(redact_sensitive(wrapped)),
                    )
                    if capture:
                        self._captured_debug.append(
                            {
                                "prompt": json.loads(self._serialize(rkwargs)),
                                "response": json.loads(self._serialize(raw)),
                            }
                        )
                    return wrapped
            except Exception as exc:
                logger.error("LLM_FAILED model={} {} error={}", self.model, self.log_context, repr(exc))
                raise
        try:
            resp = await self.client.chat.completions.create(**kwargs)
        except Exception as exc:
            logger.error("LLM_FAILED model={} {} error={}", self.model, self.log_context, repr(exc))
            raise
        if not kwargs.get("stream"):
            logger.info("LLM_RESPONSE model={} response={}", self.model, self._serialize(redact_sensitive(resp)))
            if capture:
                self._captured_debug.append(
                    {
                        "prompt": json.loads(self._serialize(kwargs)),
                        "response": json.loads(self._serialize(resp)),
                    }
                )
        return resp

    def take_captured_debug(self) -> dict[str, Any] | None:
        """Pop and return the oldest captured LLM request/response pair.

        Captures are kept in a FIFO deque so concurrent callers each get their
        own debug entry instead of racing over a single shared slot.
        """
        if self._captured_debug:
            return self._captured_debug.popleft()
        return None

    async def _complete_content(
        self,
        label: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        response_format: dict[str, str] | None = None,
        capture_debug: bool = False,
        empty_is_transient: bool = False,
        **extra: Any,
    ) -> tuple[str | None, int] | None:
        """Retry-wrapped completion returning ``(content, tokens_used)`` or None.

        Empty ``choices`` yields None; empty content yields ``(None, tokens)``
        so token usage is still reported. When ``empty_is_transient`` both cases
        raise ``RetryableError`` so the retry loop can recover. ``extra``
        kwargs (e.g. ``max_tokens``) are forwarded to ``_complete``.
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": cast("Any", messages),
            "temperature": temperature,
            **extra,
        }
        if response_format:
            kwargs["response_format"] = response_format
        if capture_debug:
            kwargs["capture_debug"] = True

        async def _do() -> tuple[str | None, int] | None:
            resp = await self._complete(**kwargs)
            if not resp.choices:
                if empty_is_transient:
                    raise RetryableError("empty choices")
                return None
            content = resp.choices[0].message.content
            tokens_used = resp.usage.total_tokens if resp.usage else 0
            if not content:
                if empty_is_transient:
                    raise RetryableError("empty content")
                return (None, tokens_used)
            return (content, tokens_used)

        return cast("tuple[str | None, int] | None", await _retry(_do, label=label, context=self.log_context))

    async def generate_descriptions(self, product_text: str) -> tuple[dict[str, str] | None, int, str]:
        prompt = DESCRIPTION_SYSTEM_PROMPT.format(product_text=product_text)
        result = await self._complete_content(
            "GEN_DESC",
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        if result is None:
            logger.error("Description generation failed after retries")
            return (None, 0, prompt)
        content, tokens_used = result
        if content is None:
            return (None, tokens_used, prompt)
        try:
            return (cast("dict[str, str]", json.loads(content)), tokens_used, prompt)
        except json.JSONDecodeError:
            logger.error("Description generation failed after retries")
            return (None, 0, prompt)

    async def generate_with_raw_prompt(self, raw_prompt: str) -> tuple[dict[str, str] | None, int]:
        result = await self._complete_content(
            "GEN_RAW",
            [{"role": "user", "content": raw_prompt}],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        if result is None:
            logger.error("Raw description generation failed after retries")
            return (None, 0)
        content, tokens_used = result
        if content is None:
            return (None, tokens_used)
        try:
            return (cast("dict[str, str]", json.loads(content)), tokens_used)
        except json.JSONDecodeError:
            logger.error("Raw description generation failed after retries")
            return (None, 0)

    async def parse_search_query(
        self,
        raw_query: str,
        locale: str = "en",
        capture_debug: bool = False,
        prompt: str | None = None,
    ) -> dict[str, object] | None:
        prompt = prompt or PARSE_SEARCH_QUERY_PROMPT
        prompt = prompt.format(raw_query=raw_query) if "{raw_query}" in prompt else f"{prompt}\n\nUser query: {raw_query}"

        result = await self._complete_content(
            f"PARSE_QUERY {raw_query[:50]}",
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
            capture_debug=capture_debug,
        )
        if result is None:
            logger.error("PARSE_QUERY_FAILED raw={}", raw_query)
            return None
        content, _tokens = result
        if content is None:
            logger.error("PARSE_QUERY_FAILED raw={}", raw_query)
            return None
        try:
            return cast("dict[str, object]", json.loads(content))
        except json.JSONDecodeError:
            logger.error("PARSE_QUERY_FAILED raw={}", raw_query)
            return None

    async def generate_eval_queries(
        self,
        count: int,
        locales: list[str],
        catalog_context: str,
        prompt: str | None = None,
    ) -> list[dict[str, str]] | None:
        """Generate a batch of diverse catalog-realistic search queries for eval.

        Returns a list of ``{"text": ..., "locale": ...}`` dicts, deduplicated
        and trimmed to ``count``, or None when the LLM call or JSON parse fails.
        """
        prompt = prompt or EVAL_QUERIES_PROMPT
        prompt = prompt.format(
            count=count,
            locales=", ".join(locales) or "en, ar",
            catalog_context=catalog_context or "(none provided)",
        )

        result = await self._complete_content(
            f"EVAL_QUERIES count={count}",
            [{"role": "user", "content": prompt}],
            temperature=0.8,
            response_format={"type": "json_object"},
        )
        if result is None:
            logger.error("EVAL_QUERIES_FAILED count={}", count)
            return None
        content, _tokens = result
        if content is None:
            logger.error("EVAL_QUERIES_FAILED count={}", count)
            return None
        try:
            data = cast("dict[str, object]", json.loads(content))
        except json.JSONDecodeError:
            logger.error("EVAL_QUERIES_FAILED count={}", count)
            return None
        raw_queries = data.get("queries")
        if not isinstance(raw_queries, list):
            logger.error("EVAL_QUERIES_BAD_SHAPE count={}", count)
            return None
        out: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for entry in raw_queries:
            if not isinstance(entry, dict):
                continue
            text = str(entry.get("text") or "").strip()
            locale = str(entry.get("locale") or "en").strip().lower()
            if not text or locale not in ("en", "ar"):
                continue
            key = (text, locale)
            if key in seen:
                continue
            seen.add(key)
            out.append({"text": text, "locale": locale})
            if len(out) >= count:
                break
        return out

    async def chat(
        self,
        user_query: str,
        products_context: str,
        locale: str = "en",
    ) -> str | None:
        locale_hint = response_locale_hint(locale, user_query)

        prompt = FASHION_ASSISTANT_PROMPT.format(
            products_context=products_context,
            user_query=user_query,
            locale_hint=locale_hint,
        )

        result = await self._complete_content(
            f"CHAT {user_query[:50]}",
            [{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        if result is None:
            logger.error("CHAT_FAILED user_query={}", user_query)
            return None
        content, _tokens = result
        if content is None:
            logger.error("CHAT_FAILED user_query={}", user_query)
            return None
        return content

    async def chat_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        locale: str = "en",
        capture_debug: bool = False,
    ) -> ToolCallResult | None:
        """Single LLM call with function-calling tools.

        Returns a ToolCallResult with either a final answer or tool call
        arguments. Returns None when the call fails after retries or the model
        does not support tools (raised as an exception is not swallowed here —
        callers decide the fallback).
        """
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), None)
        locale_hint = response_locale_hint(locale, last_user)
        full_messages: list[dict[str, str]] = messages + [{"role": "user", "content": locale_hint}]

        async def _do() -> ToolCallResult | None:
            resp = await self._complete(
                model=self.model,
                messages=cast("Any", full_messages),
                tools=cast("Any", tools),
                tool_choice="auto",
                temperature=0.3,
                capture_debug=capture_debug,
            )
            if not resp.choices:
                return None
            choice = resp.choices[0]
            tokens_used = resp.usage.total_tokens if resp.usage else 0
            message = choice.message
            if message.tool_calls:
                calls: list[dict[str, Any]] = []
                for call in message.tool_calls:
                    call_fn = getattr(call, "function", None)
                    args_raw = getattr(call_fn, "arguments", None) or "{}"
                    try:
                        args = json.loads(args_raw)
                    except json.JSONDecodeError:
                        logger.warning("TOOL_CALL_BAD_ARGS raw={}", args_raw[:200])
                        args = {}
                    if isinstance(args, dict):
                        calls.append(cast("dict[str, Any]", args))
                if len(calls) > 1:
                    logger.info("TOOL_CALLS_MULTIPLE count={} — executing all calls", len(calls))
                if calls:
                    return ToolCallResult(tool_call_args=calls, tokens_used=tokens_used)
            content = message.content
            return ToolCallResult(answer=content, tokens_used=tokens_used)

        result = await _retry(_do, label="TOOL_CHAT", context=self.log_context)
        return cast("ToolCallResult | None", result)

    async def classify_intent(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
        locale: str = "en",
    ) -> str:
        """Route a user message to one of ``greeting`` | ``search`` | ``general``.

        A cheap JSON-mode classification call on the conversational model.
        Falls back to ``"search"`` on any failure so the existing search flow
        remains the safe default.
        """
        prompt = ROUTER_PROMPT.format(query=query)
        if history:
            history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
            prompt = f"Conversation so far:\n{history_text}\n\n{prompt}"

        result = await self._complete_content(
            f"ROUTER {query[:50]}",
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
            empty_is_transient=True,
        )
        if result is None:
            logger.warning("ROUTER_FAILED — defaulting to search for query={}", query[:50])
            return "search"
        content, _tokens = result
        if content is None:
            logger.warning("ROUTER_FAILED — defaulting to search for query={}", query[:50])
            return "search"
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("ROUTER_FAILED — defaulting to search for query={}", query[:50])
            return "search"
        intent = cast("str | None", data.get("intent"))
        if intent not in ("greeting", "search", "general"):
            logger.warning("ROUTER_UNKNOWN_INTENT raw={}", intent)
            return "search"
        return intent

    async def chat_plain(
        self,
        messages: list[dict[str, str]],
        locale: str = "en",
    ) -> str | None:
        """Plain conversational answer without product context (greeting/general)."""
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), None)
        locale_hint = response_locale_hint(locale, last_user)
        final = messages + [{"role": "user", "content": locale_hint}]

        result = await self._complete_content(
            "PLAIN_CHAT",
            final,
            temperature=0.5,
        )
        if result is None:
            logger.error("PLAIN_CHAT_FAILED")
            return None
        content, _tokens = result
        return content

    async def chat_plain_stream(
        self,
        messages: list[dict[str, str]],
        locale: str = "en",
    ) -> AsyncGenerator[str, None]:
        """Stream a plain conversational answer (greeting/general)."""
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), None)
        locale_hint = response_locale_hint(locale, last_user)
        final = messages + [{"role": "user", "content": locale_hint}]

        stream = await self._complete(
            model=self.model,
            messages=cast("Any", final),
            temperature=0.5,
            stream=True,
        )
        parts: list[str] = []
        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    parts.append(delta.content)
                    yield delta.content
        except Exception as exc:
            logger.error("LLM_STREAM_FAILED model={} {} error={}", self.model, self.log_context, repr(exc))
            raise
        logger.info("LLM_PLAIN_STREAM_RESPONSE model={} text={}", self.model, "".join(parts))

    async def chat_with_context(
        self,
        messages: list[dict[str, str]],
        products_context: str,
        locale: str = "en",
    ) -> str | None:
        """Final answer call: conversation messages + product context."""
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), None)
        locale_hint = response_locale_hint(locale, last_user)

        # Restate the query so the model's final user turn still carries it.
        final = messages + [{"role": "user", "content": f"{last_user}\n\nAvailable products:\n{products_context}\n\n{locale_hint}"}]

        result = await self._complete_content(
            "CONTEXT_CHAT",
            final,
            temperature=0.5,
        )
        if result is None:
            logger.error("CONTEXT_CHAT_FAILED")
            return None
        content, _tokens = result
        return content

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        locale: str = "en",
    ) -> AsyncGenerator[str, None]:
        """Stream the final answer as text deltas."""
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), None)
        locale_hint = response_locale_hint(locale, last_user)
        final = messages + [{"role": "user", "content": locale_hint}]

        stream = await self._complete(
            model=self.model,
            messages=cast("Any", final),
            temperature=0.5,
            stream=True,
        )
        parts: list[str] = []
        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    parts.append(delta.content)
                    yield delta.content
        except Exception as exc:
            logger.error("LLM_STREAM_FAILED model={} {} error={}", self.model, self.log_context, repr(exc))
            raise
        logger.info("LLM_STREAM_RESPONSE model={} text={}", self.model, "".join(parts))

    async def summarize(
        self,
        messages: list[dict[str, str]],
        previous_summary: str = "",
        locale: str = "en",
        prompt: str | None = None,
    ) -> tuple[str | None, int]:
        """Rolling conversation summary: S2 = f(S1, new_messages)."""
        history_text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        locale_hint = response_locale_hint(locale, history_text)
        prompt = prompt or SUMMARIZE_PROMPT
        prompt = prompt.format(
            previous_summary=previous_summary,
            history_text=history_text,
            locale_hint=locale_hint,
        )

        result = await self._complete_content(
            "SUMMARIZE",
            [{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        if result is None:
            logger.error("SUMMARIZE_FAILED")
            return (None, 0)
        content, tokens_used = result
        return (content or "", tokens_used)

    async def generate_title(self, query: str, locale: str = "en", prompt: str | None = None) -> str | None:
        """Short conversation title (2-6 words) from the first user message."""
        locale_hint = response_locale_hint(locale, query)
        prompt = prompt or TITLE_PROMPT
        prompt = prompt.format(query=query, locale_hint=locale_hint)
        target_locale = detect_locale(query) or locale

        def _clean(raw: str) -> str:
            for marker in ("Final title:", "Title:", "Answer:"):
                if marker in raw:
                    raw = raw.split(marker, 1)[1]
                    break
            quoted = re.findall(r'"([^"]+)"', raw)
            if quoted:
                target = [q for q in quoted if _ARABIC_SCRIPT_RE.search(q)] if target_locale in ("ar", "fa") else [q for q in quoted if _LATIN_RE.search(q)]
                if target:
                    raw = target[-1]
            return raw.strip().strip('"').strip()

        def _extract_from_reasoning(reasoning: str) -> str:
            lines = [line.strip() for line in reasoning.splitlines() if line.strip()]
            if not lines:
                return ""
            if target_locale in ("ar", "fa"):
                candidates = [line for line in lines if _ARABIC_SCRIPT_RE.search(line)]
                pick = candidates[-1] if candidates else lines[-1]
            else:
                candidates = [line for line in lines if _LATIN_RE.search(line)]
                pick = candidates[-1] if candidates else lines[-1]
            return _clean(pick)

        async def _do() -> str | None:
            resp = await self._complete(
                model=self.model,
                messages=cast("Any", [{"role": "user", "content": prompt}]),
                temperature=0.2,
                max_tokens=512,
            )
            if not resp.choices:
                raise RetryableError("empty choices")
            message = resp.choices[0].message
            title = _clean(message.content or "")
            if not title and isinstance(getattr(message, "reasoning_content", None), str):
                title = _extract_from_reasoning(str(message.reasoning_content))
            if not title:
                raise RetryableError("empty content")
            return title

        result = await _retry(_do, label=f"TITLE {query[:50]}", context=self.log_context)
        if result is None:
            logger.error("TITLE_FAILED query={}", query[:50])
        return cast("str | None", result)
