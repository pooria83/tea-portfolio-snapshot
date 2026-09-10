from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.ai.client import AIEngineClient


@pytest.fixture
def client() -> AIEngineClient:
    return AIEngineClient()


@pytest.mark.asyncio
async def test_health_returns_true_when_200(client: AIEngineClient):
    with patch("app.ai.client.httpx.AsyncClient") as mock_httpx:
        mock_instance = AsyncMock()
        mock_httpx.return_value = mock_instance
        mock_instance.get.return_value = httpx.Response(200)

        assert await client.health() is True


@pytest.mark.asyncio
async def test_health_returns_false_when_not_200(client: AIEngineClient):
    with patch("app.ai.client.httpx.AsyncClient") as mock_httpx:
        mock_instance = AsyncMock()
        mock_httpx.return_value = mock_instance
        mock_instance.get.return_value = httpx.Response(503)

        assert await client.health() is False


@pytest.mark.asyncio
async def test_health_returns_false_on_exception(client: AIEngineClient):
    with patch("app.ai.client.httpx.AsyncClient") as mock_httpx:
        mock_instance = AsyncMock()
        mock_httpx.return_value = mock_instance
        mock_instance.get.side_effect = httpx.ConnectError("connection failed")

        assert await client.health() is False


@pytest.mark.asyncio
async def test_close_cleans_up_client(client: AIEngineClient):
    with patch("app.ai.client.httpx.AsyncClient") as mock_httpx:
        mock_instance = AsyncMock()
        mock_httpx.return_value = mock_instance
        mock_instance.get.return_value = httpx.Response(200)

        await client.health()
        assert client._client is not None

        await client.close()
        mock_instance.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_conversational_forwards_prompts(client: AIEngineClient):
    with patch("app.ai.client.httpx.AsyncClient") as mock_httpx:
        mock_instance = AsyncMock()
        mock_httpx.return_value = mock_instance
        mock_instance.post.return_value = httpx.Response(200, json={"answer": "ok", "products": []}, request=httpx.Request("POST", "http://test"))

        await client.chat_conversational(
            query="red dress",
            locale="en",
            history=[],
            summary="",
            system_prompt="You are a stylist.",
            parse_prompt="Strict parser. Query: {raw_query}",
        )
        sent = mock_instance.post.call_args.kwargs["json"]
        assert sent["system_prompt"] == "You are a stylist."
        assert sent["parse_prompt"] == "Strict parser. Query: {raw_query}"
        assert sent["query"] == "red dress"


@pytest.mark.asyncio
async def test_chat_conversational_omits_prompts_when_none(client: AIEngineClient):
    with patch("app.ai.client.httpx.AsyncClient") as mock_httpx:
        mock_instance = AsyncMock()
        mock_httpx.return_value = mock_instance
        mock_instance.post.return_value = httpx.Response(200, json={"answer": "ok", "products": []}, request=httpx.Request("POST", "http://test"))

        await client.chat_conversational(query="red dress", locale="en", history=[], summary="")
        sent = mock_instance.post.call_args.kwargs["json"]
        assert "system_prompt" not in sent
        assert "parse_prompt" not in sent


@pytest.mark.asyncio
async def test_chat_conversational_stream_forwards_prompts(client: AIEngineClient):
    with patch("app.ai.client.httpx.AsyncClient") as mock_httpx:
        mock_instance = AsyncMock()
        mock_httpx.return_value = mock_instance
        ctx_mgr = AsyncMock()
        response_mock = MagicMock()
        response_mock.status_code = 200

        async def _lines():
            if False:
                yield ""

        response_mock.aiter_lines = MagicMock(side_effect=_lines)
        ctx_mgr.__aenter__.return_value = response_mock
        ctx_mgr.__aexit__.return_value = None
        mock_instance.stream = MagicMock(return_value=ctx_mgr)

        chunks = [
            chunk
            async for chunk in client.chat_conversational_stream(
                query="red dress",
                locale="en",
                history=[],
                summary="",
                system_prompt="You are a stylist.",
                parse_prompt="Strict parser. Query: {raw_query}",
            )
        ]
        assert chunks == []
        sent = mock_instance.stream.call_args.kwargs["json"]
        assert sent["system_prompt"] == "You are a stylist."
        assert sent["parse_prompt"] == "Strict parser. Query: {raw_query}"
        assert sent["stream"] is True


@pytest.mark.asyncio
async def test_summarize_forwards_prompt(client: AIEngineClient):
    with patch("app.ai.client.httpx.AsyncClient") as mock_httpx:
        mock_instance = AsyncMock()
        mock_httpx.return_value = mock_instance
        mock_instance.post.return_value = httpx.Response(200, json={"summary": "s", "tokens_used": 1}, request=httpx.Request("POST", "http://test"))

        await client.summarize([{"role": "user", "content": "hi"}], previous_summary="", locale="en", prompt="Summarize: {history_text}")
        sent = mock_instance.post.call_args.kwargs["json"]
        assert sent["prompt"] == "Summarize: {history_text}"
        assert sent["messages"] == [{"role": "user", "content": "hi"}]


@pytest.mark.asyncio
async def test_summarize_omits_prompt_when_none(client: AIEngineClient):
    with patch("app.ai.client.httpx.AsyncClient") as mock_httpx:
        mock_instance = AsyncMock()
        mock_httpx.return_value = mock_instance
        mock_instance.post.return_value = httpx.Response(200, json={"summary": "s", "tokens_used": 1}, request=httpx.Request("POST", "http://test"))

        await client.summarize([{"role": "user", "content": "hi"}])
        assert "prompt" not in mock_instance.post.call_args.kwargs["json"]


@pytest.mark.asyncio
async def test_title_forwards_prompt(client: AIEngineClient):
    with patch("app.ai.client.httpx.AsyncClient") as mock_httpx:
        mock_instance = AsyncMock()
        mock_httpx.return_value = mock_instance
        mock_instance.post.return_value = httpx.Response(200, json={"title": "Red dresses"}, request=httpx.Request("POST", "http://test"))

        await client.title("i want a red dress", locale="en", prompt="Title it: {query}\n{locale_hint}")
        sent = mock_instance.post.call_args.kwargs["json"]
        assert sent["prompt"] == "Title it: {query}\n{locale_hint}"
        assert sent["query"] == "i want a red dress"
        assert sent["need_title"] is True


@pytest.mark.asyncio
async def test_title_omits_prompt_when_none(client: AIEngineClient):
    with patch("app.ai.client.httpx.AsyncClient") as mock_httpx:
        mock_instance = AsyncMock()
        mock_httpx.return_value = mock_instance
        mock_instance.post.return_value = httpx.Response(200, json={"title": "Red dresses"}, request=httpx.Request("POST", "http://test"))

        await client.title("i want a red dress")
        assert "prompt" not in mock_instance.post.call_args.kwargs["json"]


@pytest.mark.asyncio
async def test_title_forwards_need_title_false(client: AIEngineClient):
    with patch("app.ai.client.httpx.AsyncClient") as mock_httpx:
        mock_instance = AsyncMock()
        mock_httpx.return_value = mock_instance
        mock_instance.post.return_value = httpx.Response(200, json={"title": "i want a red dress"}, request=httpx.Request("POST", "http://test"))

        await client.title("i want a red dress", need_title=False)
        assert mock_instance.post.call_args.kwargs["json"]["need_title"] is False
