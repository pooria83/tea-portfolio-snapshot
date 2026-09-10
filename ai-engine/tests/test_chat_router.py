from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient

from app.services.llm_client import ToolCallResult


class TestChatRouter:
    async def test_chat_success(self, test_client: AsyncClient) -> None:
        payload = {"query": "red dress under 100 SAR", "locale": "en", "limit": 5}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Test answer"
        assert len(data["products"]) == 2
        assert data["products"][0]["id"] == "p1"
        assert data["products"][0]["name"] == "Product 1"

    async def test_chat_no_products(self, test_client: AsyncClient, mock_rag: AsyncMock) -> None:
        mock_rag.search.return_value = []

        payload = {"query": "unknown item"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "I couldn't find any matching products. Try a different search."
        assert data["products"] == []

    async def test_chat_no_products_arabic_message(self, test_client: AsyncClient, mock_rag: AsyncMock) -> None:
        mock_rag.search.return_value = []

        payload = {"query": "هل عندكم توب صيفي؟", "locale": "en"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "لم أجد منتجات مطابقة. جرّب بحثاً مختلفاً."
        assert data["products"] == []

    async def test_product_context_uses_detected_locale(self, test_client: AsyncClient, mock_rag: AsyncMock) -> None:
        payload = {"query": "هل عندكم توب صيفي؟", "locale": "en"}
        await test_client.post("/chat", json=payload)
        assert mock_rag.format_products_for_prompt.call_args.kwargs["locale"] == "ar"

    async def test_chat_502_on_embedding_failure(self, test_client: AsyncClient, mock_embedder: AsyncMock) -> None:
        mock_embedder.embed_query.return_value = None

        payload = {"query": "test"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 502
        assert "Embedding failed" in resp.text

    async def test_preflight_embedder_down_is_advisory_chat_proceeds(self, test_client: AsyncClient, mock_embedder: AsyncMock, mock_llm_client: MagicMock) -> None:
        mock_embedder.health.return_value = False

        payload = {"query": "test"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        assert resp.json()["answer"] == "Test answer"
        mock_llm_client.classify_intent.assert_awaited()
        mock_embedder.embed_query.assert_awaited()

    async def test_preflight_llm_down_is_advisory_chat_proceeds(self, test_client: AsyncClient, mock_llm_client: MagicMock, mock_embedder: AsyncMock) -> None:
        mock_llm_client.health.return_value = False

        payload = {"query": "test"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        assert resp.json()["answer"] == "Test answer"
        mock_llm_client.classify_intent.assert_awaited()

    async def test_preflight_embedder_down_stream_proceeds(self, test_client: AsyncClient, mock_embedder: AsyncMock, mock_llm_client: MagicMock) -> None:
        mock_embedder.health.return_value = False

        def fake_stream(_messages, **kwargs):
            async def gen():
                yield "Hel"
                yield "lo "

            return gen()

        mock_llm_client.chat_stream = MagicMock(side_effect=fake_stream)

        payload = {"query": "test", "stream": True}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        events = [json.loads(line) for line in resp.text.strip().splitlines()]
        types = [e["type"] for e in events]
        assert types[0] == "assistant_start"
        assert "product_cards" in types
        assert types[-1] == "assistant_end"
        mock_llm_client.classify_intent.assert_awaited()

    async def test_preflight_llm_down_stream_proceeds(self, test_client: AsyncClient, mock_llm_client: MagicMock, mock_embedder: AsyncMock) -> None:
        mock_llm_client.health.return_value = False

        def fake_stream(_messages, **kwargs):
            async def gen():
                yield "Hi "

            return gen()

        mock_llm_client.chat_stream = MagicMock(side_effect=fake_stream)

        payload = {"query": "test", "stream": True}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        events = [json.loads(line) for line in resp.text.strip().splitlines()]
        types = [e["type"] for e in events]
        assert types[0] == "assistant_start"
        assert "product_cards" in types
        assert types[-1] == "assistant_end"
        mock_llm_client.classify_intent.assert_awaited()

    async def test_preflight_healthy_chat_proceeds(self, test_client: AsyncClient, mock_llm_client: MagicMock) -> None:
        payload = {"query": "test"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        assert mock_llm_client.classify_intent.await_count == 1

    async def test_chat_502_on_llm_failure(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        mock_llm_client.chat_with_context.return_value = None

        payload = {"query": "test"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 502
        assert "Chat generation failed" in resp.text

    async def test_chat_locale_passthrough(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        payload = {"query": "فستان أحمر", "locale": "ar"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        assert mock_llm_client.chat_with_context.call_args.kwargs["locale"] == "ar"

    async def test_missing_query(self, test_client: AsyncClient) -> None:
        resp = await test_client.post("/chat", json={})
        assert resp.status_code == 422

    async def test_default_locale(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        payload = {"query": "test"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        assert mock_llm_client.chat_with_context.call_args.kwargs["locale"] == "en"

    async def test_custom_limit(self, test_client: AsyncClient, mock_rag: AsyncMock) -> None:
        payload = {"query": "test", "limit": 3}
        await test_client.post("/chat", json=payload)
        assert mock_rag.search.call_args.kwargs["limit"] == 3

    async def test_parse_failure_falls_back_to_raw_query(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.parse_search_query.return_value = None

        payload = {"query": "raw fallback test"}
        await test_client.post("/chat", json=payload)
        assert mock_rag.search.call_args.kwargs["filters"] is None

    async def test_rewritten_query_used_when_present(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock, mock_embedder: AsyncMock) -> None:
        mock_llm_client.parse_search_query.return_value = {"rewritten_query": "evening elegant", "filters": {}}

        payload = {"query": "evening dress elegant"}
        await test_client.post("/chat", json=payload)

        embed_calls = [c.args[0] for c in mock_embedder.embed_query.call_args_list]
        assert "evening elegant" in embed_calls[0]

    async def test_parse_dual_spec_searches_raw_query_too(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock, mock_embedder: AsyncMock) -> None:
        mock_llm_client.parse_search_query.return_value = {
            "rewritten_query": "automatic chronograph sapphire",
            "filters": {"category": ["Watches"]},
        }

        payload = {"query": "automatic chronograph watch with sapphire glass"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200

        embed_calls = [c.args[0] for c in mock_embedder.embed_query.call_args_list]
        assert embed_calls == [
            "automatic chronograph sapphire watch",
            "automatic chronograph watch with sapphire glass",
        ]
        assert mock_rag.search.call_count == 2
        last = mock_rag.search.call_args_list[-1]
        assert last.kwargs["filters"] == {"category": ["Watches", "watches", "WATCHES"]}

    async def test_parse_single_spec_when_rewrite_unchanged(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock, mock_embedder: AsyncMock) -> None:
        mock_llm_client.parse_search_query.return_value = {"rewritten_query": "", "filters": {}}

        payload = {"query": "green dress"}
        await test_client.post("/chat", json=payload)

        assert mock_embedder.embed_query.call_count == 1
        assert mock_rag.search.call_count == 1

    async def test_filters_passed_to_search(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.parse_search_query.return_value = {
            "rewritten_query": "dress",
            "filters": {"color": ["Red"], "material": ["Cotton"]},
        }

        payload = {"query": "red cotton dress"}
        await test_client.post("/chat", json=payload)

        search_kwargs = mock_rag.search.call_args.kwargs
        assert search_kwargs["filters"] == {"color_family": ["reds-pinks"], "material": ["Cotton", "cotton", "COTTON"]}

    async def test_unmapped_color_kept_with_case_variants(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.parse_search_query.return_value = {
            "rewritten_query": "dress",
            "filters": {"color": ["ecru"], "category": ["dresses"]},
        }

        payload = {"query": "ecru dress"}
        await test_client.post("/chat", json=payload)

        search_kwargs = mock_rag.search.call_args.kwargs
        assert search_kwargs["filters"]["color"] == ["ecru", "Ecru", "ECRU"]
        assert search_kwargs["filters"]["category"] == ["dresses", "Dresses", "DRESSES"]

    async def test_string_filter_normalized_to_list(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.parse_search_query.return_value = {
            "rewritten_query": "dress",
            "filters": {"color": "Red"},
        }

        payload = {"query": "red dress"}
        await test_client.post("/chat", json=payload)

        search_kwargs = mock_rag.search.call_args.kwargs
        assert search_kwargs["filters"] == {"color_family": ["reds-pinks"]}

    async def test_gender_filter_normalized_to_canonical(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.parse_search_query.return_value = {
            "rewritten_query": "dress",
            "filters": {"gender": ["Male", "girls"]},
        }

        payload = {"query": "men dress"}
        await test_client.post("/chat", json=payload)

        search_kwargs = mock_rag.search.call_args.kwargs
        assert sorted(search_kwargs["filters"]["gender"]) == ["girls", "men"]

    async def test_gender_filter_unknown_values_dropped(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.parse_search_query.return_value = {
            "rewritten_query": "dress",
            "filters": {"gender": ["unknown-value"]},
        }

        payload = {"query": "dress"}
        await test_client.post("/chat", json=payload)

        search_kwargs = mock_rag.search.call_args.kwargs
        assert search_kwargs["filters"] is None

    async def test_arabic_gender_normalized(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.parse_search_query.return_value = {
            "rewritten_query": "فستان",
            "filters": {"gender": ["رجال"]},
        }

        payload = {"query": "فستان رجالي"}
        await test_client.post("/chat", json=payload)

        search_kwargs = mock_rag.search.call_args.kwargs
        assert search_kwargs["filters"] == {"gender": ["men"]}

    async def test_color_family_mapped_to_bucket_and_drops_color(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.parse_search_query.return_value = {
            "rewritten_query": "dress",
            "filters": {"color": ["Red"], "color_family": ["red"]},
        }

        payload = {"query": "red dress"}
        await test_client.post("/chat", json=payload)

        search_kwargs = mock_rag.search.call_args.kwargs
        assert search_kwargs["filters"] == {"color_family": ["reds-pinks"]}

    async def test_color_family_unknown_value_falls_back_to_color_family_translation(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.parse_search_query.return_value = {
            "rewritten_query": "dress",
            "filters": {"color_family": ["unknown-color"], "color": ["Red"]},
        }

        payload = {"query": "dress"}
        await test_client.post("/chat", json=payload)

        search_kwargs = mock_rag.search.call_args.kwargs
        assert search_kwargs["filters"] == {"color_family": ["reds-pinks"]}

    async def test_color_family_printed_maps_to_specialty(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.parse_search_query.return_value = {
            "rewritten_query": "dress",
            "filters": {"color": ["Printed"], "color_family": ["printed"]},
        }

        payload = {"query": "printed dress"}
        await test_client.post("/chat", json=payload)

        search_kwargs = mock_rag.search.call_args.kwargs
        assert search_kwargs["filters"] == {"color_family": ["specialty"]}

    async def test_color_family_arabic_printed_maps_to_specialty(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.parse_search_query.return_value = {
            "rewritten_query": "فستان",
            "filters": {"color_family": ["مطبوع"]},
        }

        payload = {"query": "فستان مطبوع"}
        await test_client.post("/chat", json=payload)

        search_kwargs = mock_rag.search.call_args.kwargs
        assert search_kwargs["filters"] == {"color_family": ["specialty"]}

    async def test_embed_exception_returns_502(self, test_client: AsyncClient, mock_embedder: AsyncMock) -> None:
        mock_embedder.embed_query.side_effect = Exception("Connection refused")

        payload = {"query": "test"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 502

    # --- P1: tool-calling, history, streaming ---

    async def test_tool_call_used_for_search(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.chat_with_tools.return_value = ToolCallResult(tool_call_args=[{"query": "red cotton dress", "filters": {"color": ["Red"], "material": ["Cotton"]}}])

        payload = {"query": "red dress"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["search_context"]["tool_used"] is True
        assert data["search_context"]["rewritten_query"] == "red cotton dress"
        assert mock_rag.search.call_args.kwargs["filters"] == {"color_family": ["reds-pinks"], "material": ["Cotton", "cotton", "COTTON"]}

    async def test_tool_call_with_size_filter_normalized(
        self,
        test_client: AsyncClient,
        mock_llm_client: AsyncMock,
        mock_rag: AsyncMock,
    ) -> None:
        mock_llm_client.chat_with_tools.return_value = ToolCallResult(tool_call_args=[{"query": "denim jacket in size M", "filters": {"category": ["Jackets"], "size": ["M"]}}])

        payload = {"query": "size M jacket"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["search_context"]["tool_used"] is True
        assert data["search_context"]["rewritten_query"] == "denim jacket in size M"
        assert mock_rag.search.call_args.kwargs["filters"] == {
            "category": ["Jackets", "jackets", "JACKETS"],
            "size": ["m"],
        }

    async def test_tool_call_strips_assistant_history_but_answer_keeps_it(
        self,
        test_client: AsyncClient,
        mock_llm_client: AsyncMock,
        mock_rag: AsyncMock,
    ) -> None:
        mock_llm_client.chat_with_tools.return_value = ToolCallResult(tool_call_args=[{"query": "green short dress"}])

        payload = {
            "query": "a shorter ones",
            "history": [
                {"role": "user", "content": "wanting green dresses"},
                {"role": "assistant", "content": "Here are the matching green dresses currently available: ..."},
            ],
        }
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200

        tool_messages = mock_llm_client.chat_with_tools.call_args.args[0]
        assert [m["role"] for m in tool_messages] == ["system", "user", "user"]
        assert tool_messages[0]["role"] == "system"
        assert tool_messages[1]["content"] == "wanting green dresses"
        assert tool_messages[2]["content"] == "a shorter ones"
        assert all(m["role"] != "assistant" for m in tool_messages)

        answer_messages = mock_llm_client.chat_with_context.call_args.args[0]
        assert any(m["role"] == "assistant" for m in answer_messages)
        assert any(m["content"] == "a shorter ones" for m in answer_messages)

    async def test_tool_call_lowercase_color_maps_to_family(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.chat_with_tools.return_value = ToolCallResult(tool_call_args=[{"query": "red lace dress short", "filters": {"color": ["red"], "material": ["lace"]}}])

        payload = {"query": "i want shorter dresses"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        assert mock_rag.search.call_args.kwargs["filters"] == {"color_family": ["reds-pinks"], "material": ["lace", "Lace", "LACE"]}

    async def test_tool_call_unsupported_falls_back_to_parse(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.chat_with_tools.side_effect = Exception("model does not support tools")

        payload = {"query": "red dress"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["search_context"]["tool_used"] is False
        mock_llm_client.parse_search_query.assert_awaited_once()
        assert mock_rag.search.call_args.kwargs["filters"] == {"color_family": ["reds-pinks"]}

    async def test_tool_call_empty_query_falls_back_to_raw(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_embedder: AsyncMock) -> None:
        mock_llm_client.chat_with_tools.return_value = ToolCallResult(tool_call_args=[{"query": ""}])

        payload = {"query": "original query"}
        await test_client.post("/chat", json=payload)
        assert "original query" in mock_embedder.embed_query.call_args[0][0]

    async def test_multiple_tool_calls_all_executed_and_merged(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock, mock_embedder: AsyncMock) -> None:
        from app.schemas.chat import ProductRef

        mock_llm_client.chat_with_tools.return_value = ToolCallResult(
            tool_call_args=[
                {"query": "linen halter top backless", "filters": {"category": ["halter top"]}},
                {"query": "lace bra", "filters": {"category": ["bra"]}},
            ]
        )
        mock_rag.search = AsyncMock(
            side_effect=[
                [ProductRef(id="p1", name="Halter Top", price=10.0, currency="SAR", brand="Zara")],
                [
                    ProductRef(id="p2", name="Lace Bra", price=5.0, currency="SAR", brand="Zara"),
                    ProductRef(id="p1", name="Halter Top", price=10.0, currency="SAR", brand="Zara"),
                ],
            ]
        )

        payload = {
            "query": "i want bra lace bra",
            "history": [{"role": "user", "content": "I'm looking for a linen halter top with a backless design and beads"}],
        }
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        ids = [p["id"] for p in data["products"]]
        assert ids == ["p1", "p2"]
        assert data["search_context"]["tool_used"] is True
        assert mock_rag.search.await_count == 2
        assert mock_embedder.embed_query.await_args_list[0].args[0] == "linen halter top backless"
        assert mock_embedder.embed_query.await_args_list[1].args[0] == "lace bra"

    async def test_tool_call_color_family_name_kept(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.chat_with_tools.return_value = ToolCallResult(tool_call_args=[{"query": "red lace dress", "filters": {"color_family": ["reds-pinks"], "material": ["lace"]}}])

        payload = {"query": "red lace dress for night"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        assert mock_rag.search.call_args.kwargs["filters"] == {"color_family": ["reds-pinks"], "material": ["lace", "Lace", "LACE"]}

    async def test_tool_call_color_family_expands_concrete_color(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.chat_with_tools.return_value = ToolCallResult(tool_call_args=[{"query": "red dress", "filters": {"color_family": ["Red"]}}])

        payload = {"query": "red dress"}
        await test_client.post("/chat", json=payload)
        assert mock_rag.search.call_args.kwargs["filters"] == {"color_family": ["reds-pinks"]}

    async def test_tool_call_color_family_yellows_oranges_kept(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.chat_with_tools.return_value = ToolCallResult(tool_call_args=[{"query": "yellow shirt", "filters": {"color_family": ["yellows-oranges"]}}])

        payload = {"query": "yellow shirt"}
        await test_client.post("/chat", json=payload)
        assert mock_rag.search.call_args.kwargs["filters"] == {"color_family": ["yellows-oranges"]}

    async def test_tool_call_color_family_unknown_drops_family_keeps_color(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.chat_with_tools.return_value = ToolCallResult(tool_call_args=[{"query": "dress", "filters": {"color_family": ["unknown-color"], "color": ["Red"]}}])

        payload = {"query": "dress"}
        await test_client.post("/chat", json=payload)
        assert mock_rag.search.call_args.kwargs["filters"] == {"color_family": ["reds-pinks"]}

    async def test_tool_call_color_family_drops_color(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.chat_with_tools.return_value = ToolCallResult(tool_call_args=[{"query": "red dress", "filters": {"color": ["Red"], "color_family": ["reds-pinks"]}}])

        payload = {"query": "red dress"}
        await test_client.post("/chat", json=payload)
        assert mock_rag.search.call_args.kwargs["filters"] == {"color_family": ["reds-pinks"]}

    async def test_tool_call_omitting_color_filter_still_filters_by_color(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.chat_with_tools.return_value = ToolCallResult(tool_call_args=[{"query": "green lace dress"}])

        payload = {"query": "i want a green lace dress"}
        await test_client.post("/chat", json=payload)
        assert mock_rag.search.call_args.kwargs["filters"] == {"color_family": ["greens"]}

    async def test_tool_call_injects_color_and_preserves_other_filters(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.chat_with_tools.return_value = ToolCallResult(tool_call_args=[{"query": "green lace dress", "filters": {"material": ["Lace"]}}])

        payload = {"query": "i want a green lace dress"}
        await test_client.post("/chat", json=payload)
        assert mock_rag.search.call_args.kwargs["filters"] == {
            "color_family": ["greens"],
            "material": ["Lace", "lace", "LACE"],
        }

    async def test_parse_fallback_injects_color_when_filters_empty(self, test_client: AsyncClient, mock_llm_client: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.parse_search_query.return_value = {"rewritten_query": "", "filters": {}}

        payload = {"query": "green dress"}
        await test_client.post("/chat", json=payload)
        assert mock_rag.search.call_args.kwargs["filters"] == {"color_family": ["greens"]}

    async def test_history_and_summary_included_in_messages(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        payload = {
            "query": "and cheaper",
            "locale": "en",
            "history": [{"role": "user", "content": "show me red dresses"}, {"role": "assistant", "content": "Here are some"}],
            "summary": "User wants red dresses under 200 SAR",
        }
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        tool_messages = mock_llm_client.chat_with_tools.call_args.args[0]
        assert tool_messages[0]["role"] == "system"
        assert tool_messages[1] == {"role": "system", "content": "Previous conversation summary:\nUser wants red dresses under 200 SAR"}
        assert tool_messages[2] == {"role": "user", "content": "show me red dresses"}
        assert tool_messages[3] == {"role": "user", "content": "and cheaper"}
        assert all(m["role"] != "assistant" for m in tool_messages)
        answer_messages = mock_llm_client.chat_with_context.call_args.args[0]
        assert {"role": "assistant", "content": "Here are some"} in answer_messages

    async def test_streaming_returns_sse_frames(self, test_client: AsyncClient, mock_llm_client: MagicMock) -> None:
        def fake_stream(_messages, **kwargs):
            async def gen():
                yield "Hel"
                yield "lo "

            return gen()

        mock_llm_client.chat_stream = MagicMock(side_effect=fake_stream)

        payload = {"query": "test", "stream": True}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        events = [json.loads(line) for line in resp.text.strip().splitlines()]
        types = [e["type"] for e in events]
        assert types[0] == "assistant_start"
        assert "product_cards" in types
        assert types[-1] == "assistant_end"
        text = "".join(e["delta"] for e in events if e["type"] == "text_chunk")
        assert text == "Hello "

    async def test_streaming_empty_products_sends_end(self, test_client: AsyncClient, mock_rag: AsyncMock) -> None:
        mock_rag.search.return_value = []

        payload = {"query": "nothing", "stream": True}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        events = [json.loads(line) for line in resp.text.strip().splitlines()]
        assert events[0]["type"] == "assistant_start"
        assert events[1]["type"] == "product_cards"
        assert events[1]["products"] == []
        assert events[-1]["type"] == "assistant_end"

    async def test_streaming_product_cards_carry_detected_locale(self, test_client: AsyncClient, mock_rag: AsyncMock) -> None:
        from app.schemas.chat import ProductRef

        mock_rag.search.return_value = [ProductRef(id="p1", name="Top", price=99.0, currency="SAR", brand="Zara")]

        payload = {"query": "أريد توب نسائي", "stream": True}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        events = [json.loads(line) for line in resp.text.strip().splitlines()]
        cards = next(e for e in events if e["type"] == "product_cards")
        assert cards["locale"] == "ar"

        payload = {"query": "elegant sleeveless top", "stream": True}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        events = [json.loads(line) for line in resp.text.strip().splitlines()]
        cards = next(e for e in events if e["type"] == "product_cards")
        assert cards["locale"] == "en"

    async def test_streaming_multiple_tool_calls_merged_into_cards(self, test_client: AsyncClient, mock_llm_client: MagicMock, mock_rag: AsyncMock) -> None:
        from app.schemas.chat import ProductRef

        mock_llm_client.chat_with_tools.return_value = ToolCallResult(
            tool_call_args=[
                {"query": "linen halter top"},
                {"query": "lace bra"},
            ]
        )
        mock_rag.search = AsyncMock(
            side_effect=[
                [ProductRef(id="p1", name="Halter Top", price=10.0, currency="SAR", brand="Zara")],
                [ProductRef(id="p2", name="Lace Bra", price=5.0, currency="SAR", brand="Zara")],
            ]
        )

        payload = {"query": "i want bra lace bra", "stream": True}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        events = [json.loads(line) for line in resp.text.strip().splitlines()]
        cards = next(e for e in events if e["type"] == "product_cards")
        assert [p["id"] for p in cards["products"]] == ["p1", "p2"]

    async def test_streaming_dedupes_duplicate_products_in_cards(self, test_client: AsyncClient, mock_llm_client: MagicMock, mock_rag: AsyncMock) -> None:
        from app.schemas.chat import ProductRef

        dup = ProductRef(id="p1", name="Halter Top", price=10.0, currency="SAR", brand="Zara")
        mock_llm_client.chat_with_tools.return_value = ToolCallResult(tool_call_args=[{"query": "halter top"}, {"query": "lace top"}])
        mock_rag.search = AsyncMock(return_value=[dup])

        payload = {"query": "top", "stream": True}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        events = [json.loads(line) for line in resp.text.strip().splitlines()]
        cards = next(e for e in events if e["type"] == "product_cards")
        assert [p["id"] for p in cards["products"]] == ["p1"]

    async def test_streaming_embedding_failed_frame_terminates_with_newline(self, test_client: AsyncClient, mock_llm_client: MagicMock, mock_embedder: AsyncMock, mock_rag: AsyncMock) -> None:
        mock_llm_client.chat_with_tools.return_value = ToolCallResult(tool_call_args=[{"query": "red dress"}])
        mock_embedder.embed_query = AsyncMock(side_effect=Exception("embed down"))

        payload = {"query": "red dress", "stream": True}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        assert resp.text.endswith("\n")
        last_line = resp.text.rstrip("\n").splitlines()[-1]
        assert json.loads(last_line) == {"type": "error", "code": "embedding_failed"}

    async def test_debug_included_in_response(self, test_client: AsyncClient, mock_llm_client: MagicMock) -> None:
        mock_llm_client.take_captured_debug = MagicMock(
            return_value={
                "prompt": {"model": "test-model", "messages": [{"role": "user", "content": "red dress"}], "temperature": 0.1},
                "response": {"id": "chatcmpl-1", "choices": [{"message": {"content": '{"rewritten_query": "red dress", "filters": {}}'}}]},
            }
        )

        payload = {"query": "red dress"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        debug = resp.json()["debug"]
        assert debug["prompt"]["messages"][0]["content"] == "red dress"
        assert debug["response"]["id"] == "chatcmpl-1"

    async def test_debug_absent_when_not_captured(self, test_client: AsyncClient) -> None:
        payload = {"query": "red dress"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        assert resp.json().get("debug") is None

    async def test_streaming_emits_debug_frame_first(self, test_client: AsyncClient, mock_llm_client: MagicMock) -> None:
        mock_llm_client.take_captured_debug = MagicMock(
            return_value={
                "prompt": {"model": "test-model", "messages": [{"role": "user", "content": "red dress"}]},
                "response": {"choices": [{"message": {"content": '{"rewritten_query": "red dress", "filters": {}}'}}]},
            }
        )

        payload = {"query": "red dress", "stream": True}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        events = [json.loads(line) for line in resp.text.strip().splitlines()]
        assert events[0]["type"] == "debug"
        assert events[0]["debug"]["prompt"]["messages"][0]["content"] == "red dress"
        assert events[1]["type"] == "assistant_start"

    async def test_default_system_prompt_prepended(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        payload = {"query": "red dress"}
        await test_client.post("/chat", json=payload)
        messages = mock_llm_client.chat_with_context.call_args.args[0]
        assert messages[0]["role"] == "system"
        assert "DO NOT list or enumerate the products" in messages[0]["content"]

    async def test_custom_system_prompt_used(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        payload = {"query": "red dress", "system_prompt": "You are a concise stylist."}
        await test_client.post("/chat", json=payload)
        messages = mock_llm_client.chat_with_context.call_args.args[0]
        assert messages[0] == {"role": "system", "content": "You are a concise stylist."}

    async def test_parse_prompt_forwarded(self, test_client: AsyncClient, mock_llm_client: AsyncMock) -> None:
        payload = {"query": "red dress", "parse_prompt": "Strict parser. Query: {raw_query}"}
        await test_client.post("/chat", json=payload)
        assert mock_llm_client.parse_search_query.call_args.kwargs["prompt"] == "Strict parser. Query: {raw_query}"


class TestConversationRouter:
    async def test_greeting_returns_plain_reply_no_search(self, test_client: AsyncClient, mock_llm_client: MagicMock, mock_rag: AsyncMock, mock_embedder: AsyncMock) -> None:
        mock_llm_client.classify_intent = AsyncMock(return_value="greeting")
        mock_llm_client.chat_plain = AsyncMock(return_value="Hi there! How can I help you?")

        payload = {"query": "hi how are you?"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Hi there! How can I help you?"
        assert data["products"] == []
        assert data["search_context"]["intent"] == "greeting"
        assert data["search_context"]["tool_used"] is False
        mock_llm_client.chat_with_tools.assert_not_called()
        mock_llm_client.chat_with_context.assert_not_called()
        mock_rag.search.assert_not_called()
        mock_embedder.embed_query.assert_not_called()

    async def test_general_returns_plain_llm_answer_no_search(self, test_client: AsyncClient, mock_llm_client: MagicMock, mock_rag: AsyncMock, mock_embedder: AsyncMock) -> None:
        mock_llm_client.classify_intent = AsyncMock(return_value="general")
        mock_llm_client.chat_plain = AsyncMock(return_value="For a wedding, a silk midi dress works well.")

        payload = {"query": "what should i wear to a wedding?"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "For a wedding, a silk midi dress works well."
        assert data["products"] == []
        assert data["search_context"]["intent"] == "general"
        mock_llm_client.chat_with_tools.assert_not_called()
        mock_rag.search.assert_not_called()
        mock_embedder.embed_query.assert_not_called()

    async def test_search_intent_runs_full_search_flow(self, test_client: AsyncClient, mock_llm_client: MagicMock, mock_rag: AsyncMock, mock_embedder: AsyncMock) -> None:
        mock_llm_client.classify_intent = AsyncMock(return_value="search")

        payload = {"query": "green dress"}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["search_context"]["intent"] == "search"
        assert len(data["products"]) == 2
        mock_llm_client.chat_with_context.assert_awaited_once()
        mock_rag.search.assert_awaited_once()
        mock_embedder.embed_query.assert_awaited_once()

    async def test_classify_intent_receives_query_history_and_locale(self, test_client: AsyncClient, mock_llm_client: MagicMock) -> None:
        payload = {
            "query": "the red one",
            "locale": "ar",
            "history": [{"role": "user", "content": "show me dresses"}],
        }
        await test_client.post("/chat", json=payload)
        mock_llm_client.classify_intent.assert_awaited_once_with(
            "the red one",
            [{"role": "user", "content": "show me dresses"}],
            locale="ar",
        )

    async def test_greeting_streams_plain_answer(self, test_client: AsyncClient, mock_llm_client: MagicMock) -> None:
        mock_llm_client.classify_intent = AsyncMock(return_value="greeting")

        async def fake_stream(_messages, **kwargs):
            yield "Hel"
            yield "lo!"

        mock_llm_client.chat_plain_stream = MagicMock(side_effect=fake_stream)

        payload = {"query": "hello", "stream": True}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        events = [json.loads(line) for line in resp.text.strip().splitlines()]
        types = [e["type"] for e in events]
        assert types[0] == "assistant_start"
        assert types[1] == "product_cards"
        assert events[1]["products"] == []
        assert types[-1] == "assistant_end"
        text = "".join(e["delta"] for e in events if e["type"] == "text_chunk")
        assert text == "Hello!"

    async def test_general_streams_plain_answer(self, test_client: AsyncClient, mock_llm_client: MagicMock) -> None:
        mock_llm_client.classify_intent = AsyncMock(return_value="general")

        async def fake_stream(_messages, **kwargs):
            yield "Some answer"

        mock_llm_client.chat_plain_stream = MagicMock(side_effect=fake_stream)

        payload = {"query": "how do returns work?", "stream": True}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        events = [json.loads(line) for line in resp.text.strip().splitlines()]
        assert events[0]["type"] == "assistant_start"
        assert events[0]["search_context"]["intent"] == "general"
        assert events[-1]["type"] == "assistant_end"
        text = "".join(e["delta"] for e in events if e["type"] == "text_chunk")
        assert text == "Some answer"

    async def test_greeting_stream_failure_falls_back_to_plain(self, test_client: AsyncClient, mock_llm_client: MagicMock) -> None:
        mock_llm_client.classify_intent = AsyncMock(return_value="greeting")
        mock_llm_client.chat_plain_stream = AsyncMock(side_effect=Exception("stream broke"))
        mock_llm_client.chat_plain = AsyncMock(return_value="fallback reply")

        payload = {"query": "hello", "stream": True}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        events = [json.loads(line) for line in resp.text.strip().splitlines()]
        text = "".join(e["delta"] for e in events if e["type"] == "text_chunk")
        assert text == "fallback reply"
        assert events[-1]["type"] == "assistant_end"

    async def test_direct_answer_streams_sse_frames(self, test_client: AsyncClient, mock_llm_client: MagicMock, mock_rag: AsyncMock, mock_embedder: AsyncMock) -> None:
        mock_llm_client.chat_with_tools.return_value = ToolCallResult(answer="I can't help with that, but I can suggest outfits.")

        payload = {"query": "make me look sexy", "stream": True}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        events = [json.loads(line) for line in resp.text.strip().splitlines()]
        types = [e["type"] for e in events]
        assert types[0] == "assistant_start"
        assert events[0]["search_context"]["intent"] == "search"
        assert "product_cards" in types
        assert types[-1] == "assistant_end"
        text = "".join(e["delta"] for e in events if e["type"] == "text_chunk")
        assert text == "I can't help with that, but I can suggest outfits."
        mock_rag.search.assert_not_called()
        mock_embedder.embed_query.assert_not_called()

    async def test_direct_answer_non_streaming_returns_json(self, test_client: AsyncClient, mock_llm_client: MagicMock, mock_rag: AsyncMock, mock_embedder: AsyncMock) -> None:
        mock_llm_client.chat_with_tools.return_value = ToolCallResult(answer="Direct reply")

        payload = {"query": "make me look sexy", "stream": False}
        resp = await test_client.post("/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Direct reply"
        assert data["products"] == []
        assert data["search_context"]["intent"] == "search"
        mock_rag.search.assert_not_called()
