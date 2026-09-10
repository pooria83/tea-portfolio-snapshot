from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm_client import LLMClient


def _make_usage(total: int) -> MagicMock:
    u = MagicMock()
    u.total_tokens = total
    return u


def _make_choice(content: str | None) -> MagicMock:
    c = MagicMock()
    c.message.content = content
    return c


def _make_response(choices: list[MagicMock], usage: MagicMock | None = None) -> MagicMock:
    r = MagicMock()
    r.choices = choices
    r.usage = usage
    return r


class TestGenerateDescriptions:
    async def test_success(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice('{"en": "Test EN", "ar": "Test AR"}')]
        mock_openai_chat.usage = _make_usage(100)

        result, tokens, prompt = await llm_client.generate_descriptions("Product: Test")
        assert result is not None
        assert result["en"] == "Test EN"
        assert result["ar"] == "Test AR"
        assert tokens == 100
        assert "Product: Test" in prompt

    async def test_empty_content(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice(None)]
        mock_openai_chat.usage = _make_usage(50)

        result, tokens, prompt = await llm_client.generate_descriptions("Product: Test")
        assert result is None
        assert tokens == 50
        assert prompt is not None

    async def test_api_exception(self, llm_client: LLMClient) -> None:
        llm_client.client.chat.completions.create = AsyncMock(side_effect=Exception("API error"))

        result, tokens, prompt = await llm_client.generate_descriptions("Product: Test")
        assert result is None
        assert tokens == 0
        assert prompt is not None

    async def test_prompt_structure(self, llm_client: LLMClient) -> None:
        mock_response = _make_response(
            choices=[_make_choice('{"en": "Desc", "ar": "وصف"}')],
            usage=_make_usage(50),
        )
        llm_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        _, _, prompt = await llm_client.generate_descriptions("Product: Silk Dress")
        assert "You are a product description writer" in prompt
        assert "fashion e-commerce platform" in prompt
        assert "2-3 sentences" in prompt
        assert "English and Arabic" in prompt
        assert "JSON" in prompt
        assert '"en"' in prompt
        assert '"ar"' in prompt
        assert "Product: Silk Dress" in prompt
        assert "material" in prompt or "fit" in prompt

    async def test_prompt_has_product_text(self, llm_client: LLMClient) -> None:
        mock_response = _make_response(
            choices=[_make_choice('{"en": "Desc", "ar": "وصف"}')],
            usage=_make_usage(50),
        )
        llm_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        _, _, prompt = await llm_client.generate_descriptions("Product: Name (EN): Silk Gown\nBrand: Gucci\nPrice: 500.0 SAR")
        assert "Product:" in prompt
        assert "Name (EN): Silk Gown" in prompt
        assert "Gucci" in prompt
        assert "500.0 SAR" in prompt

    async def test_no_usage_returns_zero(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice('{"en": "Desc"}')]
        mock_openai_chat.usage = None

        _, tokens, _ = await llm_client.generate_descriptions("Product: Test")
        assert tokens == 0


class TestGenerateWithRawPrompt:
    async def test_success(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice('{"en": "Raw EN", "ar": "Raw AR"}')]
        mock_openai_chat.usage = _make_usage(30)

        result, tokens = await llm_client.generate_with_raw_prompt("Custom prompt here")
        assert result is not None
        assert result["en"] == "Raw EN"
        assert result["ar"] == "Raw AR"
        assert tokens == 30

    async def test_empty_content(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice(None)]
        mock_openai_chat.usage = _make_usage(20)

        result, tokens = await llm_client.generate_with_raw_prompt("Custom prompt")
        assert result is None
        assert tokens == 20

    async def test_api_exception(self, llm_client: LLMClient) -> None:
        llm_client.client.chat.completions.create = AsyncMock(side_effect=Exception("API error"))

        result, tokens = await llm_client.generate_with_raw_prompt("Custom prompt")
        assert result is None
        assert tokens == 0

    async def test_passed_directly_to_api(self, llm_client: LLMClient) -> None:
        mock_response = _make_response(
            choices=[_make_choice('{"en": "Result"}')],
            usage=_make_usage(10),
        )
        mock_create = AsyncMock(return_value=mock_response)
        llm_client.client.chat.completions.create = mock_create

        await llm_client.generate_with_raw_prompt("My exact prompt")
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["messages"][0]["content"] == "My exact prompt"
        assert call_kwargs["response_format"]["type"] == "json_object"

    async def test_no_usage_returns_zero(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice('{"en": "Desc"}')]
        mock_openai_chat.usage = None

        _, tokens = await llm_client.generate_with_raw_prompt("Custom prompt")
        assert tokens == 0


class TestChat:
    async def test_success(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice("I found some products for you")]
        mock_openai_chat.usage = _make_usage(80)

        result = await llm_client.chat("find dress", "1. Silk Dress - 100 SAR")
        assert result == "I found some products for you"

    async def test_empty_response(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice(None)]

        result = await llm_client.chat("find dress", "products here")
        assert result is None

    async def test_api_exception(self, llm_client: LLMClient) -> None:
        llm_client.client.chat.completions.create = AsyncMock(side_effect=Exception("API error"))

        result = await llm_client.chat("find dress", "products")
        assert result is None

    async def test_message_language_wins_over_locale(
        self,
        llm_client: LLMClient,
        mock_openai_chat: AsyncMock,
    ) -> None:
        mock_openai_chat.choices = [_make_choice("Answer")]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        await llm_client.chat("هل عندكم توب صيفي؟", "products", locale="en")
        sent = mock_create.call_args.kwargs["messages"][0]["content"]
        assert "Respond in Arabic" in sent

    @pytest.mark.parametrize("locale", ["en", "ar", "fa"])
    async def test_english_message_gets_english_hint(
        self,
        llm_client: LLMClient,
        mock_openai_chat: AsyncMock,
        locale: str,
    ) -> None:
        mock_openai_chat.choices = [_make_choice("Answer")]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        await llm_client.chat("query", "products", locale=locale)
        sent = mock_create.call_args.kwargs["messages"][0]["content"]
        assert "Respond in English" in sent

    async def test_unknown_locale_with_latin_message_defaults_english(
        self,
        llm_client: LLMClient,
        mock_openai_chat: AsyncMock,
    ) -> None:
        mock_openai_chat.choices = [_make_choice("Answer")]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        await llm_client.chat("query", "products", locale="fr")
        sent = mock_create.call_args.kwargs["messages"][0]["content"]
        assert "Respond in English" in sent

    async def test_inconclusive_message_falls_back_to_locale(
        self,
        llm_client: LLMClient,
        mock_openai_chat: AsyncMock,
    ) -> None:
        mock_openai_chat.choices = [_make_choice("Answer")]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        await llm_client.chat("🛍️", "products", locale="ar")
        sent = mock_create.call_args.kwargs["messages"][0]["content"]
        assert "Respond in Arabic" in sent

    async def test_prompt_structure(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice("Answer")]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        await llm_client.chat("red dress under 200", "1. Red Dress - 150 SAR - Zara")
        sent = mock_create.call_args.kwargs["messages"][0]["content"]
        assert "fashion assistant" in sent
        assert "Available products:" in sent
        assert "1. Red Dress - 150 SAR - Zara" in sent
        assert "red dress under 200" in sent
        assert "Respond in English" in sent

    async def test_no_json_response_format(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice("Answer")]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        await llm_client.chat("query", "products")
        call_kwargs = mock_create.call_args.kwargs
        assert "response_format" not in call_kwargs
        assert call_kwargs["temperature"] == 0.5


class TestParseSearchQuery:
    async def test_success_with_filters(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice('{"rewritten_query": "lace sleepwear comfortable", "filters": {"color": ["Red"], "material": ["Lace"], "category": ["Dresses"]}}')]
        mock_openai_chat.usage = _make_usage(40)

        result = await llm_client.parse_search_query("red lace dress")
        assert result is not None
        assert result["rewritten_query"] == "lace sleepwear comfortable"
        assert result["filters"] == {"color": ["Red"], "material": ["Lace"], "category": ["Dresses"]}

    async def test_success_no_filters(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice('{"rewritten_query": "evening dress elegant", "filters": {}}')]
        mock_openai_chat.usage = _make_usage(30)

        result = await llm_client.parse_search_query("evening dress")
        assert result is not None
        assert result["filters"] == {}

    async def test_empty_content_returns_none(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice(None)]
        mock_openai_chat.usage = _make_usage(10)

        result = await llm_client.parse_search_query("test")
        assert result is None

    async def test_api_exception_returns_none(self, llm_client: LLMClient) -> None:
        llm_client.client.chat.completions.create = AsyncMock(side_effect=Exception("API error"))

        result = await llm_client.parse_search_query("test")
        assert result is None

    async def test_empty_choices_returns_none(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = []

        result = await llm_client.parse_search_query("test")
        assert result is None

    async def test_prompt_contains_examples(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice('{"rewritten_query": "x", "filters": {}}')]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        await llm_client.parse_search_query("red dress")
        sent = mock_create.call_args.kwargs["messages"][0]["content"]
        assert "rewritten_query" in sent
        assert "filters" in sent
        assert "User query: red dress" in sent
        assert "temperature" in mock_create.call_args.kwargs
        assert mock_create.call_args.kwargs["temperature"] == 0.1


class _TransientError(Exception):
    status_code = 429


class _PermanentError(Exception):
    status_code = 400


class TestRetry:
    async def test_retry_success_on_first_attempt(self) -> None:
        from app.services.llm_client import _retry

        async def ok() -> str:
            return "done"

        result = await _retry(ok, "TEST")
        assert result == "done"

    async def test_retry_succeeds_on_second_attempt(self) -> None:
        from app.services.llm_client import _retry

        call_count = 0

        async def eventually_ok() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise _TransientError("first attempt fails")
            return "done"

        with patch("app.services.llm_client.asyncio.sleep", new=AsyncMock()):
            result = await _retry(eventually_ok, "TEST")
        assert result == "done"
        assert call_count == 2

    async def test_retry_fails_after_all_attempts(self) -> None:
        from app.services.llm_client import _retry

        call_count = 0

        async def always_fails() -> str:
            nonlocal call_count
            call_count += 1
            raise _TransientError("persistent transient error")

        with patch("app.services.llm_client.asyncio.sleep", new=AsyncMock()):
            result = await _retry(always_fails, "TEST")
        assert result is None
        assert call_count == 3  # MAX_RETRIES + 1 attempts

    async def test_retry_does_not_retry_permanent_error(self) -> None:
        from app.services.llm_client import _retry

        call_count = 0

        async def always_permanent() -> str:
            nonlocal call_count
            call_count += 1
            raise _PermanentError("bad request")

        result = await _retry(always_permanent, "TEST")
        assert result is None
        assert call_count == 1  # fail fast, no retries


class TestMaskApiKey:
    def test_masks_long_key(self) -> None:
        from app.services.llm_client import mask_api_key

        assert mask_api_key("sk-sds1234567890yrut") == "sk-sds........yrut"

    def test_short_key_fully_masked(self) -> None:
        from app.services.llm_client import mask_api_key

        assert mask_api_key("shortkey") == "****"

    def test_empty_key(self) -> None:
        from app.services.llm_client import mask_api_key

        assert mask_api_key("") == ""


class TestRedactSensitive:
    def test_redacts_nested_sensitive_fields(self) -> None:
        from app.services.llm_client import redact_sensitive

        payload = {
            "model": "deepseek-v4-flash-free",
            "messages": [{"role": "user", "content": "hello"}],
            "api_key": "sk-super-secret",
            "nested": {"Authorization": "Bearer abc", "keep": "ok"},
        }
        out = redact_sensitive(payload)
        assert out["api_key"] == "[REDACTED]"
        assert out["nested"]["Authorization"] == "[REDACTED]"
        assert out["nested"]["keep"] == "ok"
        assert out["model"] == "deepseek-v4-flash-free"
        assert out["messages"][0]["content"] == "hello"

    def test_redacts_items_in_lists(self) -> None:
        from app.services.llm_client import redact_sensitive

        out = redact_sensitive([{"api_key": "x"}, "plain"])
        assert out[0]["api_key"] == "[REDACTED]"
        assert out[1] == "plain"


class TestLogContext:
    def test_log_context_includes_provider_and_masked_key(self, llm_client: LLMClient) -> None:
        ctx = llm_client.log_context
        assert "provider=opencode_zen" in ctx
        assert "api_key=****" in ctx or "api_key=" in ctx


class TestCaptureDebug:
    async def test_capture_debug_not_forwarded_to_sdk_and_stored(
        self,
        llm_client: LLMClient,
        mock_openai_chat: AsyncMock,
    ) -> None:
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        await llm_client._complete(
            model="m",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.1,
            capture_debug=True,
        )

        assert mock_create.call_count == 1
        assert "capture_debug" not in mock_create.call_args.kwargs
        assert mock_create.call_args.kwargs["model"] == "m"
        captured = llm_client.take_captured_debug()
        assert captured is not None
        assert captured["prompt"]["model"] == "m"
        assert captured["response"] is not None
        assert llm_client.take_captured_debug() is None

    async def test_no_capture_debug_keeps_nothing(
        self,
        llm_client: LLMClient,
        mock_openai_chat: AsyncMock,
    ) -> None:
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        await llm_client._complete(
            model="m",
            messages=[{"role": "user", "content": "hi"}],
        )

        assert "capture_debug" not in mock_create.call_args.kwargs
        assert llm_client.take_captured_debug() is None

    async def test_concurrent_captures_pair_with_callers(
        self,
        llm_client: LLMClient,
        mock_openai_chat: AsyncMock,
    ) -> None:
        import asyncio
        from unittest.mock import AsyncMock as AMock

        async def _capture(tag: str) -> tuple[str, dict[str, object] | None]:
            mock = AMock(return_value=mock_openai_chat)
            llm_client.client.chat.completions.create = mock
            await llm_client._complete(
                model=tag,
                messages=[{"role": "user", "content": tag}],
                capture_debug=True,
            )
            return tag, llm_client.take_captured_debug()

        results = await asyncio.gather(_capture("a"), _capture("b"), _capture("c"))
        by_tag = {tag: cast(dict, debug)["prompt"]["model"] for tag, debug in results if debug}
        assert by_tag == {"a": "a", "b": "b", "c": "c"}
        assert llm_client.take_captured_debug() is None


class _FakeStream:
    def __init__(self, chunks: list[MagicMock]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> _FakeStream:
        return self

    async def __anext__(self) -> MagicMock:
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


class TestChatStreamAndContextHints:
    async def test_chat_with_context_follows_message_language(
        self,
        llm_client: LLMClient,
        mock_openai_chat: AsyncMock,
    ) -> None:
        mock_openai_chat.choices = [_make_choice("Answer")]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        await llm_client.chat_with_context([{"role": "user", "content": "هل عندكم توب صيفي؟"}], "1. Dress", locale="en")
        sent = mock_create.call_args.kwargs["messages"][-1]["content"]
        assert "Respond in Arabic" in sent

    async def test_chat_stream_follows_message_language(self, llm_client: LLMClient) -> None:
        mock_create = AsyncMock(return_value=_FakeStream([]))
        llm_client.client.chat.completions.create = mock_create

        deltas = [d async for d in llm_client.chat_stream([{"role": "user", "content": "پیراهن قرمز میخواهم"}], locale="en")]
        assert deltas == []
        sent = mock_create.call_args.kwargs["messages"][-1]["content"]
        assert "Respond in Farsi" in sent


class TestPromptOverrides:
    async def test_parse_search_query_custom_prompt(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice('{"rewritten_query": "x", "filters": {}}')]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        await llm_client.parse_search_query("red dress", prompt="Strict parser. Query: {raw_query}")
        sent = mock_create.call_args.kwargs["messages"][0]["content"]
        assert sent == "Strict parser. Query: red dress"

    async def test_parse_search_query_custom_prompt_without_placeholder(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice('{"rewritten_query": "x", "filters": {}}')]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        await llm_client.parse_search_query("red dress", prompt="Parse carefully.")
        sent = mock_create.call_args.kwargs["messages"][0]["content"]
        assert sent == "Parse carefully.\n\nUser query: red dress"

    async def test_summarize_custom_prompt(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice("Summary")]
        mock_openai_chat.usage = _make_usage(20)
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        await llm_client.summarize(
            [{"role": "user", "content": "hi"}],
            prompt="You summarize.\nPrevious:\n{previous_summary}\nHistory:\n{history_text}\n{locale_hint}",
        )
        sent = mock_create.call_args.kwargs["messages"][0]["content"]
        assert "You summarize." in sent
        assert "History:\nuser: hi" in sent

    async def test_generate_title_custom_prompt(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice("Summer dresses")]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        await llm_client.generate_title("red dress", prompt="Title it: {query}\n{locale_hint}")
        sent = mock_create.call_args.kwargs["messages"][0]["content"]
        assert "Title it: red dress" in sent
        assert mock_create.call_args.kwargs["max_tokens"] == 512

    async def test_generate_title_empty_content_raises(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice("")]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        assert await llm_client.generate_title("red dress") is None

    async def test_generate_title_reasoning_fallback(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        choice = _make_choice("")
        choice.message.reasoning_content = 'The user wants a red dress. Possible title: "Red summer dress".\n\nFinal title: "فستان أحمر صيفي"'
        mock_openai_chat.choices = [choice]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        assert await llm_client.generate_title("red dress") == "فستان أحمر صيفي"

    async def test_generate_title_reasoning_prefers_target_script(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        choice = _make_choice("")
        choice.message.reasoning_content = 'Possible: "توب كتان بظهر مكشوف" (linen top with open back) or "توب نسائي صيفي أنيق".\nLet\'s craft the final choice. The user also'
        mock_openai_chat.choices = [choice]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        assert await llm_client.generate_title("أريد توب كتان") == "توب نسائي صيفي أنيق"


class TestHealth:
    async def test_health_reachable(self, llm_client: LLMClient) -> None:
        mock_get = AsyncMock(return_value=MagicMock())
        with patch("app.core.health.create_http_client", return_value=_FakeHealthClient(mock_get)):
            assert await llm_client.health() is True
        assert mock_get.call_args.args[0] == f"{llm_client.base_url.rstrip('/')}/models"

    async def test_health_unreachable(self, llm_client: LLMClient) -> None:
        async def _boom(_url: str) -> None:
            raise TimeoutError("router down")

        with patch("app.core.health.create_http_client", return_value=_FakeHealthClient(AsyncMock(side_effect=_boom))):
            assert await llm_client.health() is False

    async def test_health_retries_transient_failure(self, llm_client: LLMClient) -> None:
        mock_get = AsyncMock(side_effect=[TimeoutError("transient blip"), MagicMock()])
        with patch("app.core.health.create_http_client", return_value=_FakeHealthClient(mock_get)):
            assert await llm_client.health() is True
        assert mock_get.call_count == 2

    async def test_health_cached_within_ttl(self, llm_client: LLMClient) -> None:
        mock_get = AsyncMock(return_value=MagicMock())
        with patch("app.core.health.create_http_client", return_value=_FakeHealthClient(mock_get)):
            assert await llm_client.health() is True
            assert await llm_client.health() is True
        assert mock_get.call_count == 1

    async def test_health_probes_again_after_unhealthy(self, llm_client: LLMClient) -> None:
        mock_get = AsyncMock(side_effect=TimeoutError("down"))
        with patch("app.core.health.create_http_client", return_value=_FakeHealthClient(mock_get)):
            assert await llm_client.health() is False
        mock_get.side_effect = None
        mock_get.return_value = MagicMock()
        fresh = LLMClient(api_key="test-key", base_url=llm_client.base_url, model=llm_client.model)
        with patch("app.core.health.create_http_client", return_value=_FakeHealthClient(mock_get)):
            assert await fresh.health() is True


class _FakeHealthClient:
    def __init__(self, get: AsyncMock) -> None:
        self._get = get

    async def __aenter__(self) -> _FakeHealthClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, url: str) -> MagicMock:
        return await self._get(url)


class TestClassifyIntent:
    async def test_returns_intent(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice('{"intent": "greeting"}')]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        result = await llm_client.classify_intent("hi how are you?")
        assert result == "greeting"
        sent = mock_create.call_args.kwargs["messages"][0]["content"]
        assert "hi how are you?" in sent
        assert mock_create.call_args.kwargs["response_format"] == {"type": "json_object"}
        assert mock_create.call_args.kwargs["temperature"] == 0.0

    async def test_unknown_intent_defaults_to_search(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice('{"intent": "bogus"}')]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        assert await llm_client.classify_intent("test") == "search"

    async def test_empty_content_retries_then_search(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice("")]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        assert await llm_client.classify_intent("test") == "search"
        assert mock_create.await_count > 1

    async def test_exception_retries_then_search(self, llm_client: LLMClient) -> None:
        llm_client.client.chat.completions.create = AsyncMock(side_effect=Exception("API error"))

        assert await llm_client.classify_intent("test") == "search"

    async def test_history_appended_to_prompt(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice('{"intent": "search"}')]
        mock_create = AsyncMock(return_value=mock_openai_chat)
        llm_client.client.chat.completions.create = mock_create

        await llm_client.classify_intent("the red one", history=[{"role": "user", "content": "show me dresses"}])
        sent = mock_create.call_args.kwargs["messages"][0]["content"]
        assert "user: show me dresses" in sent
        assert "the red one" in sent


class TestChatPlain:
    async def test_plain_answer(self, llm_client: LLMClient, mock_openai_chat: AsyncMock) -> None:
        mock_openai_chat.choices = [_make_choice("Nice to meet you!")]

        result = await llm_client.chat_plain([{"role": "user", "content": "hello"}])
        assert result == "Nice to meet you!"

    async def test_plain_answer_none_on_failure(self, llm_client: LLMClient) -> None:
        llm_client.client.chat.completions.create = AsyncMock(side_effect=Exception("API error"))

        assert await llm_client.chat_plain([{"role": "user", "content": "hello"}]) is None
