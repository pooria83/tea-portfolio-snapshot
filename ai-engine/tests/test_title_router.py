from __future__ import annotations

from unittest.mock import AsyncMock

from httpx import AsyncClient


class TestTitleRouter:
    async def test_title_success(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        mock_llm_client.generate_title.return_value = "Red dresses"
        resp = await test_client.post("/title", json={"query": "i want a red dress", "locale": "en"})
        assert resp.status_code == 200
        assert resp.json() == {"title": "Red dresses"}
        assert mock_llm_client.generate_title.call_args.kwargs["locale"] == "en"

    async def test_title_passes_locale(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        mock_llm_client.generate_title.return_value = "فستان أحمر"
        resp = await test_client.post("/title", json={"query": "أريد فستانا أحمر", "locale": "ar"})
        assert resp.status_code == 200
        assert resp.json() == {"title": "فستان أحمر"}
        assert mock_llm_client.generate_title.call_args.kwargs["locale"] == "ar"

    async def test_title_fallback_on_llm_failure(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        mock_llm_client.generate_title.return_value = None
        resp = await test_client.post("/title", json={"query": "show me red dresses under 200 SAR", "locale": "en"})
        assert resp.status_code == 200
        assert resp.json() == {"title": "show me red dresses under 200 SAR"}

    async def test_title_need_title_false_skips_llm(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        mock_llm_client.generate_title.return_value = "Should not be used"
        resp = await test_client.post("/title", json={"query": "show me red dresses under 200 SAR", "locale": "en", "need_title": False})
        assert resp.status_code == 200
        assert resp.json() == {"title": "show me red dresses under 200 SAR"}
        mock_llm_client.generate_title.assert_not_called()

    async def test_title_fallback_truncates_long_query(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        mock_llm_client.generate_title.return_value = None
        long_query = " ".join(["word"] * 100)
        resp = await test_client.post("/title", json={"query": long_query, "locale": "en"})
        assert resp.status_code == 200
        title = resp.json()["title"]
        assert len(title) <= 50

    async def test_title_rejects_empty_query(self, test_client: AsyncClient) -> None:
        resp = await test_client.post("/title", json={"query": "", "locale": "en"})
        assert resp.status_code == 422

    async def test_title_prompt_passthrough(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        mock_llm_client.generate_title.return_value = "Red dresses"
        resp = await test_client.post("/title", json={"query": "i want a red dress", "prompt": "Title it: {query}\n{locale_hint}"})
        assert resp.status_code == 200
        assert mock_llm_client.generate_title.call_args.kwargs["prompt"] == "Title it: {query}\n{locale_hint}"
