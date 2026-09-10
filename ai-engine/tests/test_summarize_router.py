from __future__ import annotations

from unittest.mock import AsyncMock

from httpx import AsyncClient


class TestSummarizeRouter:
    async def test_summarize_success(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        payload = {
            "messages": [
                {"role": "user", "content": "show me red dresses"},
                {"role": "assistant", "content": "Here are three red dresses"},
            ],
            "previous_summary": "User likes red dresses",
            "locale": "en",
        }
        resp = await test_client.post("/summarize", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"] == "conversation summary"
        assert data["tokens_used"] == 10
        assert mock_llm_client.summarize.call_args.kwargs["previous_summary"] == "User likes red dresses"

    async def test_summarize_empty_messages_returns_previous(self, test_client: AsyncClient) -> None:
        payload = {"messages": [], "previous_summary": "keep me"}
        resp = await test_client.post("/summarize", json=payload)
        assert resp.status_code == 200
        assert resp.json() == {"summary": "keep me", "tokens_used": 0}

    async def test_summarize_502_on_llm_failure(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        mock_llm_client.summarize.return_value = (None, 0)
        payload = {"messages": [{"role": "user", "content": "hello"}]}
        resp = await test_client.post("/summarize", json=payload)
        assert resp.status_code == 502

    async def test_summarize_prompt_passthrough(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        payload = {
            "messages": [{"role": "user", "content": "hello"}],
            "prompt": "You summarize.\nPrevious:\n{previous_summary}\nHistory:\n{history_text}\n{locale_hint}",
        }
        resp = await test_client.post("/summarize", json=payload)
        assert resp.status_code == 200
        assert mock_llm_client.summarize.call_args.kwargs["prompt"] == payload["prompt"]
