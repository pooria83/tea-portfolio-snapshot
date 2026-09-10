from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from qdrant_client.models import PointStruct

from app.schemas.chat import ProductRef
from app.services.rag import RAGService, _size_overlap


def _distinct_hit(i: int, name: str = "Product") -> MagicMock:
    """A hit with a unique product id (search dedupes by product_id)."""
    hit = MagicMock()
    hit.id = f"p{i}"
    hit.payload = {"product_id": f"p{i}", "name_en": f"{name} {i}"}
    return hit


class TestRAGService:
    def test_init(self, rag_service: RAGService) -> None:
        assert rag_service.collection == "products"
        assert rag_service.dimensions == 1024

    async def test_ensure_collection_creates_when_missing(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_qdrant_client.get_collections = AsyncMock()
        mock_qdrant_client.get_collections.return_value.collections = []
        mock_qdrant_client.create_collection = AsyncMock()

        await rag_service.ensure_collection()
        mock_qdrant_client.create_collection.assert_awaited_once()

    async def test_ensure_collection_skips_when_exists(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        coll = MagicMock()
        coll.name = "products"
        mock_qdrant_client.get_collections = AsyncMock()
        mock_qdrant_client.get_collections.return_value.collections = [coll]

        collection_info = MagicMock()
        collection_info.config.params.vectors.size = 1024
        mock_qdrant_client.get_collection = AsyncMock(return_value=collection_info)

        mock_qdrant_client.create_collection = AsyncMock()

        await rag_service.ensure_collection()
        mock_qdrant_client.create_collection.assert_not_called()

    async def test_ensure_collection_other_collection_exists(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        coll = MagicMock()
        coll.name = "other_collection"
        mock_qdrant_client.get_collections = AsyncMock()
        mock_qdrant_client.get_collections.return_value.collections = [coll]
        mock_qdrant_client.create_collection = AsyncMock()

        await rag_service.ensure_collection()
        mock_qdrant_client.create_collection.assert_awaited_once()

    async def test_close(self, rag_service: RAGService, mock_qdrant_client: MagicMock) -> None:
        await rag_service.close()
        mock_qdrant_client.close.assert_awaited_once()

    async def test_ensure_collection_exception(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_qdrant_client.get_collections = AsyncMock(side_effect=Exception("connection refused"))

        with pytest.raises(Exception, match="connection refused"):
            await rag_service.ensure_collection()

    async def test_ensure_collection_vector_config_none(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        coll = MagicMock()
        coll.name = "products"
        mock_qdrant_client.get_collections = AsyncMock()
        mock_qdrant_client.get_collections.return_value.collections = [coll]

        collection_info = MagicMock()
        collection_info.config.params.vectors = None
        mock_qdrant_client.get_collection = AsyncMock(return_value=collection_info)

        with pytest.raises(RuntimeError, match="no vector configuration"):
            await rag_service.ensure_collection()

    async def test_ensure_collection_named_vectors_dict(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        coll = MagicMock()
        coll.name = "products"
        mock_qdrant_client.get_collections = AsyncMock()
        mock_qdrant_client.get_collections.return_value.collections = [coll]

        collection_info = MagicMock()
        named = MagicMock()
        named.size = 1024
        collection_info.config.params.vectors = {"": named}
        mock_qdrant_client.get_collection = AsyncMock(return_value=collection_info)

        await rag_service.ensure_collection()
        mock_qdrant_client.create_collection.assert_not_called()

    async def test_ensure_collection_dimension_mismatch(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        coll = MagicMock()
        coll.name = "products"
        mock_qdrant_client.get_collections = AsyncMock()
        mock_qdrant_client.get_collections.return_value.collections = [coll]

        collection_info = MagicMock()
        collection_info.config.params.vectors.size = 512
        mock_qdrant_client.get_collection = AsyncMock(return_value=collection_info)

        with pytest.raises(RuntimeError, match="dim=512"):
            await rag_service.ensure_collection()

    def test_set_collection_snapshots_and_restores(
        self,
        rag_service: RAGService,
    ) -> None:
        assert rag_service.collection == "products"
        assert rag_service.dimensions == 1024

        rag_service.set_collection("products-qwen3", 2560)
        assert rag_service.collection == "products-qwen3"
        assert rag_service.dimensions == 2560

        rag_service.restore_collection()
        assert rag_service.collection == "products"
        assert rag_service.dimensions == 1024

    def test_restore_collection_without_snapshot_is_noop(
        self,
        rag_service: RAGService,
    ) -> None:
        rag_service.restore_collection()
        assert rag_service.collection == "products"
        assert rag_service.dimensions == 1024

    async def test_upsert_product(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_qdrant_client.upsert = AsyncMock()

        await rag_service.upsert_product(
            product_id="p1",
            vector=[0.1, 0.2, 0.3],
            payload={"name_en": "Test", "price": 100.0},
        )
        mock_qdrant_client.upsert.assert_awaited_once()
        args = mock_qdrant_client.upsert.call_args[1]
        assert args["collection_name"] == "products"
        points = args["points"]
        assert len(points) == 1
        assert isinstance(points[0], PointStruct)
        assert points[0].id == "p1"
        assert points[0].vector == [0.1, 0.2, 0.3]
        assert points[0].payload == {"name_en": "Test", "price": 100.0}

    async def test_upsert_embedding_basic(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_qdrant_client.upsert = AsyncMock()

        await rag_service.upsert_embedding("p1_en", [0.1, 0.2], "p1", "en", "silk dress")

        mock_qdrant_client.upsert.assert_awaited_once()
        args = mock_qdrant_client.upsert.call_args[1]
        points = args["points"]
        assert len(points) == 1
        assert points[0].id == "p1_en"
        assert points[0].vector == [0.1, 0.2]
        assert points[0].payload == {"product_id": "p1", "lang": "en", "text": "silk dress"}

    async def test_upsert_embedding_with_payload_and_filters(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_qdrant_client.upsert = AsyncMock()

        payload = {"en": {"name": "Silk Dress"}}
        filters = {"_color": ["red"], "_material": ["cotton"]}
        await rag_service.upsert_embedding("p1_en", [0.1], "p1", "en", "dress", payload, filters)

        mock_qdrant_client.upsert.assert_awaited_once()
        args = mock_qdrant_client.upsert.call_args[1]
        points = args["points"]
        assert points[0].payload["product_data"] == payload
        assert points[0].payload["_color"] == ["red"]
        assert points[0].payload["_material"] == ["cotton"]

    async def test_search(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_hit_1 = MagicMock()
        mock_hit_1.id = "p1"
        mock_hit_1.payload = {"name_en": "Product 1", "price": 10.0, "currency": "SAR", "brand": "Brand A"}

        mock_hit_2 = MagicMock()
        mock_hit_2.id = "p2"
        mock_hit_2.payload = {"name_en": "Product 2", "price": 20.0, "currency": "USD", "brand": "Brand B"}

        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.return_value.points = [mock_hit_1, mock_hit_2]

        results = await rag_service.search(vector=[0.1, 0.2], limit=5)
        assert len(results) == 2
        assert results[0].id == "p1"
        assert results[0].name == "Product 1"
        assert results[0].price == 10.0
        assert results[0].currency == "SAR"
        assert results[0].brand == "Brand A"
        assert results[1].id == "p2"
        assert results[1].price == 20.0
        assert results[1].currency == "USD"

        mock_qdrant_client.query_points.assert_awaited_once()
        call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
        assert call_kwargs["collection_name"] == "products"
        assert call_kwargs["query"] == [0.1, 0.2]
        assert call_kwargs["limit"] == 10  # limit + 5 from _query()
        assert call_kwargs["with_payload"] is True
        assert call_kwargs.get("score_threshold") == 0.3

    async def test_search_with_product_data_parsed(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_hit = MagicMock()
        mock_hit.id = "p1"
        mock_hit.payload = {
            "product_id": "p1",
            "product_data": {
                "en": {
                    "name": "EN Name",
                    "price": 99.0,
                    "currency": "USD",
                    "brand": "Nike",
                    "image_url": "http://example.com/img.jpg",
                },
                "ar": {"name": "AR Name"},
                "store_id": "store1",
            },
        }

        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.return_value.points = [mock_hit]

        results = await rag_service.search(vector=[0.1])
        assert len(results) == 1
        assert results[0].name == "EN Name"
        assert results[0].price == 99.0
        assert results[0].currency == "USD"
        assert results[0].brand == "Nike"
        assert results[0].image_url == "http://example.com/img.jpg"
        assert results[0].store_id == "store1"

    async def test_search_empty_results(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.return_value.points = []

        results = await rag_service.search(vector=[0.1], limit=10)
        assert results == []

    async def test_search_missing_payload_fields(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_hit = MagicMock()
        mock_hit.id = "p1"
        mock_hit.payload = None

        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.return_value.points = [mock_hit]

        results = await rag_service.search(vector=[0.1])
        assert len(results) == 1
        assert results[0].name is None
        assert results[0].price is None
        assert results[0].currency == "SAR"

    async def test_search_with_filters_normalizes_keys_to_underscore(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_qdrant_client.query_points = AsyncMock(return_value=MagicMock(points=[_distinct_hit(i) for i in range(5)]))

        await rag_service.search(
            vector=[0.1],
            limit=5,
            filters={"color": ["red"], "gender": ["men"], "_brand": ["Zara"]},
        )

        call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
        query_filter = call_kwargs["query_filter"]
        must = query_filter.must
        assert {c.key for c in must} == {"_color", "_gender", "_brand"}
        color_cond = next(c for c in must if c.key == "_color")
        assert color_cond.match.any == ["red"]
        gender_cond = next(c for c in must if c.key == "_gender")
        assert gender_cond.match.any == ["men"]

    async def test_search_skips_empty_filter_values_after_normalization(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_hit = MagicMock()
        mock_hit.id = "p1"
        mock_hit.payload = {"name_en": "Product 1"}

        mock_qdrant_client.query_points = AsyncMock(return_value=MagicMock(points=[mock_hit]))

        await rag_service.search(vector=[0.1], limit=5, filters={"gender": []})

        call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
        assert call_kwargs.get("query_filter") is None

    async def test_search_with_filters_sufficient(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_hit = MagicMock()
        mock_hit.id = "p1"
        mock_hit.payload = {"name_en": "Product 1"}

        mock_qdrant_client.query_points = AsyncMock(return_value=MagicMock(points=[_distinct_hit(i) for i in range(10)]))

        results = await rag_service.search(vector=[0.1], limit=5, filters={"color": ["red"]})
        assert len(results) == 10

        call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
        assert call_kwargs["query_filter"] is not None

    async def test_search_with_filters_fallback(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        hit_1 = MagicMock()
        hit_1.id = "p1"
        hit_1.payload = {"name_en": "Product 1"}
        hit_2 = MagicMock()
        hit_2.id = "p2"
        hit_2.payload = {"name_en": "Product 2"}
        hit_3 = MagicMock()
        hit_3.id = "p3"
        hit_3.payload = {"name_en": "Product 3"}

        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.side_effect = [
            MagicMock(points=[hit_1]),  # filtered: 1 hit
            MagicMock(points=[hit_2, hit_3, hit_1]),  # fallback: 3 hits (p1 is dup)
        ]

        results = await rag_service.search(vector=[0.1], limit=3, filters={"brand": ["Nike"]})
        assert len(results) == 3
        assert {p.id for p in results} == {"p1", "p2", "p3"}

    async def test_search_color_tier_fills_before_unfiltered_fallback(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        hit_1 = MagicMock()
        hit_1.id = "p1"
        hit_1.payload = {"name_en": "Red Dress 1"}
        hit_2 = MagicMock()
        hit_2.id = "p2"
        hit_2.payload = {"name_en": "Red Dress 2"}

        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.side_effect = [
            MagicMock(points=[hit_1]),  # full AND: 1 hit
            MagicMock(points=[hit_2]),  # color tier: fills the remaining slot
        ]

        results = await rag_service.search(
            vector=[0.1],
            limit=2,
            filters={"color_family": ["reds-pinks"], "category": ["Dresses"]},
        )
        assert {p.id for p in results} == {"p1", "p2"}

        calls = mock_qdrant_client.query_points.await_args_list
        assert len(calls) == 2
        color_tier_filter = calls[1].kwargs["query_filter"]
        assert color_tier_filter is not None
        assert color_tier_filter.must[0].key == "_color_family"
        assert color_tier_filter.must[0].match.any == ["reds-pinks"]

    async def test_search_color_tier_underfills_then_unfiltered(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        hit_1 = MagicMock()
        hit_1.id = "p1"
        hit_1.payload = {"name_en": "Red Dress 1"}
        hit_2 = MagicMock()
        hit_2.id = "p2"
        hit_2.payload = {"name_en": "Other 2"}

        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.side_effect = [
            MagicMock(points=[hit_1]),  # full AND: 1 hit
            MagicMock(points=[]),  # color tier: 0 hits
            MagicMock(points=[hit_2]),  # unfiltered: fills the remaining slot
        ]

        results = await rag_service.search(
            vector=[0.1],
            limit=2,
            filters={"color_family": ["reds-pinks"]},
        )
        assert {p.id for p in results} == {"p1", "p2"}

        calls = mock_qdrant_client.query_points.await_args_list
        assert len(calls) == 3
        assert calls[2].kwargs["query_filter"] is None

    async def test_search_size_hard_filter_when_sufficient(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_qdrant_client.query_points = AsyncMock(return_value=MagicMock(points=[_distinct_hit(i, name="Dress") for i in range(10)]))

        results = await rag_service.search(vector=[0.1], limit=5, filters={"size": ["m"]})
        assert len(results) == 10

        call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
        query_filter = call_kwargs["query_filter"]
        size_cond = next(c for c in query_filter.must if c.key == "_size")
        assert size_cond.match.any == ["m"]

    async def test_search_size_fallback_ranks_matching_higher(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        hit_1 = MagicMock()
        hit_1.id = "p1"
        hit_1.payload = {"name_en": "Dress 1", "_size": ["m"]}
        hit_1.score = 0.9
        hit_2 = MagicMock()
        hit_2.id = "p2"
        hit_2.payload = {"name_en": "Dress 2", "_size": ["m"]}
        hit_2.score = 0.5
        hit_3 = MagicMock()
        hit_3.id = "p3"
        hit_3.payload = {"name_en": "Dress 3", "_size": ["l"]}
        hit_3.score = 0.6

        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.side_effect = [
            MagicMock(points=[hit_1]),  # hard _size tier: 1 hit (under limit)
            MagicMock(points=[hit_2, hit_3]),  # unfiltered fill, size boost
        ]

        results = await rag_service.search(vector=[0.1], limit=3, filters={"size": ["m"]})
        assert [p.id for p in results] == ["p1", "p2", "p3"]

        calls = mock_qdrant_client.query_points.await_args_list
        assert len(calls) == 2
        hard_filter = calls[0].kwargs["query_filter"]
        assert hard_filter.must[0].key == "_size"
        assert calls[1].kwargs["query_filter"] is None

    async def test_search_size_fallback_no_boost_when_none_match(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        hit_1 = MagicMock()
        hit_1.id = "p1"
        hit_1.payload = {"name_en": "Dress 1", "_size": ["l"]}
        hit_1.score = 0.5
        hit_2 = MagicMock()
        hit_2.id = "p2"
        hit_2.payload = {"name_en": "Dress 2"}
        hit_2.score = 0.6

        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.side_effect = [
            MagicMock(points=[]),  # hard tier: 0 hits
            MagicMock(points=[hit_1, hit_2]),  # unfiltered: no size match to boost
        ]

        results = await rag_service.search(vector=[0.1], limit=2, filters={"size": ["m"]})
        assert [p.id for p in results] == ["p2", "p1"]

    async def test_search_size_color_tier_with_size_boost(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        hit_1 = MagicMock()
        hit_1.id = "p1"
        hit_1.payload = {"name_en": "Red Dress", "_size": ["m"]}
        hit_1.score = 0.4
        hit_2 = MagicMock()
        hit_2.id = "p2"
        hit_2.payload = {"name_en": "Red Dress 2", "_size": ["l"]}
        hit_2.score = 0.5

        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.side_effect = [
            MagicMock(points=[]),  # hard AND: 0 hits
            MagicMock(points=[hit_2]),  # color tier: underfills
            MagicMock(points=[hit_1, hit_2]),  # unfiltered: size boost lifts p1
        ]

        results = await rag_service.search(
            vector=[0.1],
            limit=2,
            filters={"size": ["m"], "color_family": ["reds-pinks"]},
        )
        assert [p.id for p in results] == ["p1", "p2"]

        calls = mock_qdrant_client.query_points.await_args_list
        assert len(calls) == 3
        color_tier_filter = calls[1].kwargs["query_filter"]
        assert color_tier_filter.must[0].key == "_color_family"
        assert calls[2].kwargs["query_filter"] is None

    async def test_search_size_color_tier_fills_immediately(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        hit_1 = MagicMock()
        hit_1.id = "p1"
        hit_1.payload = {"name_en": "Red Dress", "_size": ["m"]}
        hit_1.score = 0.4
        hit_2 = MagicMock()
        hit_2.id = "p2"
        hit_2.payload = {"name_en": "Red Dress 2", "_size": ["l"]}
        hit_2.score = 0.5

        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.side_effect = [
            MagicMock(points=[]),  # hard AND: 0 hits
            MagicMock(points=[hit_1, hit_2]),  # color tier fills the limit
        ]

        results = await rag_service.search(
            vector=[0.1],
            limit=2,
            filters={"size": ["m"], "color_family": ["reds-pinks"]},
        )
        assert [p.id for p in results] == ["p1", "p2"]

        calls = mock_qdrant_client.query_points.await_args_list
        assert len(calls) == 2

    async def test_search_with_empty_filters_no_must_conditions(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_hit = MagicMock()
        mock_hit.id = "p1"
        mock_hit.payload = {"name_en": "Product 1"}

        mock_qdrant_client.query_points = AsyncMock(return_value=MagicMock(points=[mock_hit]))

        results = await rag_service.search(vector=[0.1], limit=5, filters={"color": []})
        assert len(results) == 1
        call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
        assert call_kwargs.get("query_filter") is None

    async def test_search_scored_returns_product_score_pairs(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_hit_1 = MagicMock()
        mock_hit_1.id = "p1"
        mock_hit_1.score = 0.91
        mock_hit_1.payload = {"name_en": "Product 1", "price": 10.0, "currency": "SAR", "brand": "Brand A"}
        mock_hit_2 = MagicMock()
        mock_hit_2.id = "p2"
        mock_hit_2.score = 0.87
        mock_hit_2.payload = {"name_en": "Product 2", "price": 20.0, "currency": "USD", "brand": "Brand B"}

        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.return_value.points = [mock_hit_1, mock_hit_2]

        results = await rag_service.search_scored(vector=[0.1, 0.2], limit=5)
        assert len(results) == 2
        assert results[0][0].id == "p1"
        assert results[0][1] == 0.91
        assert results[1][0].id == "p2"
        assert results[1][1] == 0.87

        mock_qdrant_client.query_points.assert_awaited_once()
        call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
        assert call_kwargs["collection_name"] == "products"
        assert call_kwargs["query"] == [0.1, 0.2]
        assert call_kwargs["limit"] == 10  # limit + 5 from _query_hits()

    async def test_search_scored_size_boost_keeps_raw_score(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        hit_1 = MagicMock()
        hit_1.id = "p1"
        hit_1.payload = {"name_en": "Dress 1", "_size": ["m"]}
        hit_1.score = 0.9
        hit_2 = MagicMock()
        hit_2.id = "p2"
        hit_2.payload = {"name_en": "Dress 2", "_size": ["m"]}
        hit_2.score = 0.5
        hit_3 = MagicMock()
        hit_3.id = "p3"
        hit_3.payload = {"name_en": "Dress 3", "_size": ["l"]}
        hit_3.score = 0.6

        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.side_effect = [
            MagicMock(points=[hit_1]),  # hard _size tier: 1 hit (under limit)
            MagicMock(points=[hit_2, hit_3]),  # unfiltered fill, size boost
        ]

        results = await rag_service.search_scored(vector=[0.1], limit=3, filters={"size": ["m"]})
        # Order reflects the size bonus (p2 boosted above p3) but scores are raw.
        assert [p.id for p, _ in results] == ["p1", "p2", "p3"]
        assert [score for _, score in results] == [0.9, 0.5, 0.6]

    async def test_search_query_exception_returns_empty(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_qdrant_client.query_points = AsyncMock(side_effect=Exception("Qdrant down"))

        results = await rag_service.search(vector=[0.1], limit=5)
        assert results == []

    async def test_search_fallback_to_name_ar(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_hit = MagicMock()
        mock_hit.id = "p1"
        mock_hit.payload = {"name_ar": "منتج", "price": 5.0}

        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.return_value.points = [mock_hit]

        results = await rag_service.search(vector=[0.1])
        assert results[0].name == "منتج"

    async def test_similar_queries_by_reference_point_and_excludes_ref(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        ref_point = MagicMock()
        ref_point.id = "3f2b7a1e-0000-0000-0000-000000000000"
        mock_qdrant_client.scroll = AsyncMock()
        mock_qdrant_client.scroll.return_value = ([ref_point], None)

        hit_ref = MagicMock()
        hit_ref.id = "3f2b7a1e-0000-0000-0000-000000000000"
        hit_ref.payload = {"product_id": "p1", "name_en": "Ref Product", "price": 10.0}

        hit_sim = MagicMock()
        hit_sim.id = "3f2b7a1e-0000-0000-0000-000000000001"
        hit_sim.payload = {"product_id": "p2", "name_en": "Similar", "price": 20.0}

        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.return_value.points = [hit_ref, hit_sim]

        results = await rag_service.similar(product_id="p1", limit=5)

        assert len(results) == 1
        assert results[0].id == "p2"
        assert results[0].name == "Similar"

        scroll_kwargs = mock_qdrant_client.scroll.call_args.kwargs
        assert scroll_kwargs["collection_name"] == "products"
        assert scroll_kwargs["limit"] == 5
        must = scroll_kwargs["scroll_filter"].must
        assert must[0].key == "product_id"
        assert must[0].match.value == "p1"

        mock_qdrant_client.query_points.assert_awaited_once()
        call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
        assert call_kwargs["query"] == "3f2b7a1e-0000-0000-0000-000000000000"
        assert call_kwargs["limit"] == 10  # limit + 5 from _query()
        assert call_kwargs["score_threshold"] == 0.3

    async def test_similar_prefers_reference_point_matching_requested_lang(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        fa_point = MagicMock()
        fa_point.id = "fa-0000-0000-0000-000000000000"
        fa_point.payload = {"product_id": "p1", "lang": "fa", "_category": ["کفش"]}

        en_point = MagicMock()
        en_point.id = "en-0000-0000-0000-000000000000"
        en_point.payload = {"product_id": "p1", "lang": "en", "_category": ["Shoes"]}

        mock_qdrant_client.scroll = AsyncMock()
        mock_qdrant_client.scroll.return_value = ([fa_point, en_point], None)

        hit = MagicMock()
        hit.id = "en-0000-0000-0000-000000000001"
        hit.payload = {"product_id": "p2", "name_en": "Similar", "price": 20.0}
        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.return_value.points = [fa_point, hit]

        results = await rag_service.similar(product_id="p1", limit=5, lang="fa")

        assert results[0].id == "p2"
        call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
        assert call_kwargs["query"] == "fa-0000-0000-0000-000000000000"

    async def test_similar_reference_falls_back_to_first_point_when_lang_mismatch(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        ar_point = MagicMock()
        ar_point.id = "ar-0000-0000-0000-000000000000"
        ar_point.payload = {"product_id": "p1", "lang": "ar"}
        en_point = MagicMock()
        en_point.id = "en-0000-0000-0000-000000000000"
        en_point.payload = {"product_id": "p1", "lang": "en"}

        mock_qdrant_client.scroll = AsyncMock()
        mock_qdrant_client.scroll.return_value = ([ar_point, en_point], None)

        hit = MagicMock()
        hit.id = "en-0000-0000-0000-000000000001"
        hit.payload = {"product_id": "p2", "name_en": "Similar", "price": 20.0}
        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.return_value.points = [ar_point, hit]

        results = await rag_service.similar(product_id="p1", limit=5, lang="de")

        assert results[0].id == "p2"
        call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
        assert call_kwargs["query"] == "ar-0000-0000-0000-000000000000"

    async def test_similar_not_indexed_returns_empty(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_qdrant_client.scroll = AsyncMock()
        mock_qdrant_client.scroll.return_value = ([], None)

        results = await rag_service.similar(product_id="missing", limit=5)
        assert results == []
        mock_qdrant_client.query_points.assert_not_called()

    async def test_similar_scroll_exception_returns_empty(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_qdrant_client.scroll = AsyncMock(side_effect=Exception("Qdrant down"))

        results = await rag_service.similar(product_id="p1", limit=5)
        assert results == []
        mock_qdrant_client.query_points.assert_not_called()

    async def test_similar_ladder_uses_api_categories_and_ref_category(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        ref_point = MagicMock()
        ref_point.id = "ref-point-id"
        ref_point.payload = {"product_id": "p1", "_category": ["Dresses", "فساتين"]}
        mock_qdrant_client.scroll = AsyncMock(return_value=([ref_point], None))

        hit = MagicMock()
        hit.id = "similar-point-id"
        hit.payload = {"product_id": "p2", "name_en": "Similar", "price": 20.0}

        def qp_side_effect(**kwargs: object) -> MagicMock:
            result = MagicMock()
            result.points = [] if kwargs.get("query_filter") is not None else [hit]
            return result

        mock_qdrant_client.query_points = AsyncMock(side_effect=qp_side_effect)

        results = await rag_service.similar(
            product_id="p1",
            limit=5,
            categories=[["Evening Dresses", "فساتين أنيقة"], ["Casual Dresses", "فساتين كاجوال"]],
        )

        assert len(results) == 1
        assert results[0].id == "p2"
        assert mock_qdrant_client.query_points.await_count == 4

        level1 = mock_qdrant_client.query_points.await_args_list[0].kwargs["query_filter"]
        level2 = mock_qdrant_client.query_points.await_args_list[1].kwargs["query_filter"]
        ref_level = mock_qdrant_client.query_points.await_args_list[2].kwargs["query_filter"]
        unfiltered = mock_qdrant_client.query_points.await_args_list[3].kwargs["query_filter"]
        assert unfiltered is None
        for level in (level1, level2, ref_level):
            assert any(cond.key == "_category" for cond in level.must)
        first_any = [c for c in level1.must if c.key == "_category"][0].match.any
        assert "Evening Dresses" in first_any
        ref_any = [c for c in ref_level.must if c.key == "_category"][0].match.any
        assert "Dresses" in ref_any
        assert "فساتين" in ref_any

    async def test_similar_color_family_stage_is_category_constrained(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        ref_point = MagicMock()
        ref_point.id = "ref-point-id"
        ref_point.payload = {
            "product_id": "p1",
            "_category": ["Dresses", "فساتين"],
            "_color_family": ["reds-pinks"],
        }
        mock_qdrant_client.scroll = AsyncMock(return_value=([ref_point], None))

        hit = MagicMock()
        hit.id = "similar-point-id"
        hit.payload = {"product_id": "p2", "name_en": "Similar", "price": 20.0}

        def qp_side_effect(**kwargs: object) -> MagicMock:
            result = MagicMock()
            result.points = [] if kwargs.get("query_filter") is not None else [hit]
            return result

        mock_qdrant_client.query_points = AsyncMock(side_effect=qp_side_effect)

        results = await rag_service.similar(product_id="p1", limit=5)

        assert len(results) == 1
        assert results[0].id == "p2"
        assert mock_qdrant_client.query_points.await_count == 3

        family_stage = mock_qdrant_client.query_points.await_args_list[1].kwargs["query_filter"]
        assert sorted(cond.key for cond in family_stage.must) == ["_category", "_color_family"]

    async def test_similar_ref_category_fallback_when_api_categories_absent(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        ref_point = MagicMock()
        ref_point.id = "ref-point-id"
        ref_point.payload = {"product_id": "p1", "_category": ["Dresses", "فساتين"]}
        mock_qdrant_client.scroll = AsyncMock(return_value=([ref_point], None))

        hit = MagicMock()
        hit.id = "similar-point-id"
        hit.payload = {"product_id": "p2", "name_en": "Similar", "price": 20.0}

        def qp_side_effect(**kwargs: object) -> MagicMock:
            result = MagicMock()
            result.points = [] if kwargs.get("query_filter") is not None else [hit]
            return result

        mock_qdrant_client.query_points = AsyncMock(side_effect=qp_side_effect)

        results = await rag_service.similar(product_id="p1", limit=5)

        assert len(results) == 1
        assert results[0].id == "p2"
        assert mock_qdrant_client.query_points.await_count == 2

        only_level = mock_qdrant_client.query_points.await_args_list[0].kwargs["query_filter"]
        assert any(cond.key == "_category" for cond in only_level.must)
        level_any = [c for c in only_level.must if c.key == "_category"][0].match.any
        assert "Dresses" in level_any


class TestFormatProductsForPrompt:
    def test_basic(self, rag_service: RAGService) -> None:
        products = [
            ProductRef(id="p1", name="Silk Dress", price=150.0, currency="SAR", brand="Zara"),
            ProductRef(id="p2", name="Cotton Shirt", price=80.0, currency="SAR", brand="H&M"),
        ]
        result = rag_service.format_products_for_prompt(products)
        assert "1. Silk Dress" in result
        assert "- 150.0 SAR" in result
        assert "- Zara" in result
        assert "2. Cotton Shirt" in result
        assert "- 80.0 SAR" in result
        assert "- H&M" in result

    def test_no_price(self, rag_service: RAGService) -> None:
        products = [ProductRef(id="p1", name="Dress", brand="Zara")]
        result = rag_service.format_products_for_prompt(products)
        assert "1. Dress" in result
        assert "- Zara" in result
        assert "SAR" not in result

    def test_no_brand(self, rag_service: RAGService) -> None:
        products = [ProductRef(id="p1", name="Dress", price=50.0)]
        result = rag_service.format_products_for_prompt(products)
        assert "1. Dress" in result
        assert "- 50.0 SAR" in result

    def test_unnamed_product(self, rag_service: RAGService) -> None:
        products = [ProductRef(id="p1", name=None)]
        result = rag_service.format_products_for_prompt(products)
        assert "1. Unnamed" in result

    def test_empty_list(self, rag_service: RAGService) -> None:
        result = rag_service.format_products_for_prompt([])
        assert result == ""

    def test_multiple_products(self, rag_service: RAGService) -> None:
        products = [ProductRef(id=f"p{i}", name=f"Product {i}", price=float(i * 10)) for i in range(1, 6)]
        result = rag_service.format_products_for_prompt(products)
        lines = result.split("\n")
        assert len(lines) == 5
        assert lines[0].startswith("1. Product 1")
        assert lines[4].startswith("5. Product 5")

    def test_with_product_data(self, rag_service: RAGService) -> None:
        products = [
            ProductRef(
                id="p1",
                name="Silk Dress",
                price=150.0,
                currency="SAR",
                brand="Zara",
                product_data={
                    "en": {
                        "name": "Silk Dress",
                        "category": {"name": "Dresses"},
                        "attributes": [{"name": "color", "value": "red"}],
                        "available_sizes": ["S", "M", "L"],
                    },
                    "store_id": "store1",
                },
            ),
        ]
        result = rag_service.format_products_for_prompt(products)
        assert "Silk Dress" in result
        assert "Brand: Zara" in result
        assert "Price: 150.0 SAR" in result
        assert "Category: Dresses" in result
        assert "Attributes: color: red" in result
        assert "Sizes: S, M, L" in result

    def test_with_product_data_locale_arabic(self, rag_service: RAGService) -> None:
        products = [
            ProductRef(
                id="p1",
                name="فستان حريري",
                price=150.0,
                currency="SAR",
                brand="زارا",
                product_data={
                    "ar": {
                        "name": "فستان حريري",
                        "category": {"name": "فساتين"},
                    },
                    "en": {"name": "Silk Dress", "category": {"name": "Dresses"}},
                    "store_id": "store1",
                },
            ),
        ]
        result = rag_service.format_products_for_prompt(products, locale="ar")
        assert "فساتين" in result
        assert "Dresses" not in result

    def test_with_product_data_missing_locale_falls_back_to_en(self, rag_service: RAGService) -> None:
        products = [
            ProductRef(
                id="p1",
                name="Fallback",
                product_data={
                    "en": {"name": "EN Product", "category": {"name": "EN Cat"}},
                },
            ),
        ]
        result = rag_service.format_products_for_prompt(products, locale="fr")
        assert "EN Cat" in result

    def test_with_product_data_and_no_extra_fields(self, rag_service: RAGService) -> None:
        products = [
            ProductRef(
                id="p1",
                product_data={"en": {}, "store_id": "s1"},
            ),
        ]
        result = rag_service.format_products_for_prompt(products)
        assert "Unnamed" in result
        assert "Brand" not in result
        assert "Price" not in result

    def test_with_product_data_category_as_string(self, rag_service: RAGService) -> None:
        products = [
            ProductRef(
                id="p1",
                name="Test",
                product_data={
                    "en": {"category": "Shoes"},
                },
            ),
        ]
        result = rag_service.format_products_for_prompt(products)
        assert "Category: Shoes" in result

    def test_with_product_data_multiple_attributes(self, rag_service: RAGService) -> None:
        products = [
            ProductRef(
                id="p1",
                name="Shirt",
                product_data={
                    "en": {
                        "attributes": [
                            {"name": "color", "value": "blue"},
                            {"name": "size", "value": "M"},
                        ],
                    },
                },
            ),
        ]
        result = rag_service.format_products_for_prompt(products)
        assert "color: blue" in result
        assert "size: M" in result
        assert "|" in result


class TestSizeOverlap:
    def test_matching_size_returns_1(self) -> None:
        assert _size_overlap(["m"], {"_size": ["m", "l"]}) == 1

    def test_no_matching_size_returns_0(self) -> None:
        assert _size_overlap(["m"], {"_size": ["l"]}) == 0
        assert _size_overlap(["m"], {"_color": ["red"]}) == 0

    def test_empty_tokens_or_payload_returns_0(self) -> None:
        assert _size_overlap([], {"_size": ["m"]}) == 0
        assert _size_overlap(["m"], None) == 0
        assert _size_overlap(["m"], {"_size": []}) == 0
