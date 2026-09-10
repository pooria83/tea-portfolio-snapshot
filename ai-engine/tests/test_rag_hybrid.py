from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from qdrant_client.models import Fusion, PointStruct, SparseVector

from app.core.config import Settings
from app.services.rag import (
    HYBRID_POOL_MAX,
    HYBRID_POOL_MULTIPLIER,
    SPARSE_VECTOR_NAME,
    RAGService,
    _fnv1a,
    _sparse_tf_vector,
    _tokenize,
)


def _hit(pid: str, score: float, name: str = "Product", lang: str | None = None) -> MagicMock:
    hit = MagicMock()
    hit.id = f"{pid}_{lang or 'en'}"
    hit.score = score
    payload: dict[str, object] = {"product_id": pid, "name_en": name, "price": 10.0, "currency": "SAR"}
    if lang is not None:
        payload["lang"] = lang
    hit.payload = payload
    return hit


class TestSparseTokenizer:
    def test_tokenizes_english_and_digits(self) -> None:
        assert _tokenize("Red Lace Dress size 42") == ["red", "lace", "dress", "size", "42"]

    def test_tokenizes_arabic_script(self) -> None:
        assert _tokenize("فستان دانتيل أحمر") == ["فستان", "دانتيل", "احمر"]

    def test_drops_short_tokens(self) -> None:
        assert _tokenize("a 1 x") == []

    def test_normalizes_combining_marks(self) -> None:
        assert _tokenize("مرحبا")  # no crash on Arabic letters
        assert "فستان" in _tokenize("فستان")

    def test_returns_empty_for_empty_text(self) -> None:
        assert _tokenize("") == []

    def test_drops_english_stopwords(self) -> None:
        assert _tokenize("the red dress for her") == ["red", "dress"]

    def test_drops_arabic_stopwords(self) -> None:
        assert _tokenize("فستان أحمر مع حقيبة") == ["فستان", "احمر", "حقيب"]

    def test_stems_english_plurals(self) -> None:
        assert _tokenize("dresses earrings shoes jeans") == ["dress", "earring", "shoe", "jean"]
        assert _tokenize("accessories") == ["accessory"]

    def test_stems_english_verb_suffixes(self) -> None:
        assert _tokenize("sorted lined dress") == ["sort", "lined", "dress"]

    def test_keeps_ss_and_us_words_intact(self) -> None:
        assert _tokenize("dress glass status bonus") == ["dress", "glass", "status", "bonus"]

    def test_stems_arabic_suffixes(self) -> None:
        assert _tokenize("فساتين حقيبة ساعة") == ["فسات", "حقيب", "ساع"]
        assert _tokenize("فستانات") == ["فستان"]

    def test_keeps_short_arabic_words_intact(self) -> None:
        assert _tokenize("قميص") == ["قميص"]

    def test_hamza_variants_collapse(self) -> None:
        assert _tokenize("أحمر احمر") == ["احمر", "احمر"]


class TestSparseTfVector:
    def test_counts_term_frequencies(self) -> None:
        vec = _sparse_tf_vector(["dress", "dress", "red"])
        assert isinstance(vec, SparseVector)
        assert vec.indices == sorted(vec.indices)
        assert len(vec.indices) == len(vec.values) == 2
        by_index = dict(zip(vec.indices, vec.values, strict=True))
        assert by_index[_fnv1a("dress")] == 2.0
        assert by_index[_fnv1a("red")] == 1.0

    def test_none_for_no_tokens(self) -> None:
        assert _sparse_tf_vector([]) is None

    def test_boosts_name_tokens(self) -> None:
        vec = _sparse_tf_vector(["dress", "dress", "red"], boost_tokens=["dress"])
        assert isinstance(vec, SparseVector)
        by_index = dict(zip(vec.indices, vec.values, strict=True))
        assert by_index[_fnv1a("dress")] == 3.0
        assert by_index[_fnv1a("red")] == 1.0

    def test_boost_adds_name_tokens_not_in_passage(self) -> None:
        vec = _sparse_tf_vector(["dress"], boost_tokens=["lace"])
        assert isinstance(vec, SparseVector)
        by_index = dict(zip(vec.indices, vec.values, strict=True))
        assert by_index[_fnv1a("lace")] == 1.0


class TestSparseCollectionConfig:
    async def test_create_includes_sparse_config(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_qdrant_client.get_collections = AsyncMock()
        mock_qdrant_client.get_collections.return_value.collections = []
        mock_qdrant_client.create_collection = AsyncMock()

        await rag_service.ensure_collection()

        create_kwargs = mock_qdrant_client.create_collection.call_args.kwargs
        assert SPARSE_VECTOR_NAME in create_kwargs["sparse_vectors_config"]
        assert rag_service._sparse_enabled is True

    async def test_existing_collection_with_sparse_stays_enabled(
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
        collection_info.config.params.sparse_vectors = {SPARSE_VECTOR_NAME: MagicMock()}
        mock_qdrant_client.get_collection = AsyncMock(return_value=collection_info)
        mock_qdrant_client.update_collection = AsyncMock()

        await rag_service.ensure_collection()

        assert rag_service._sparse_enabled is True
        mock_qdrant_client.update_collection.assert_not_called()

    async def test_existing_collection_adds_sparse_when_missing(
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
        collection_info.config.params.sparse_vectors = {}
        mock_qdrant_client.get_collection = AsyncMock(return_value=collection_info)
        mock_qdrant_client.update_collection = AsyncMock()

        await rag_service.ensure_collection()

        assert rag_service._sparse_enabled is True
        update_kwargs = mock_qdrant_client.update_collection.call_args.kwargs
        assert SPARSE_VECTOR_NAME in update_kwargs["sparse_vectors_config"]

    async def test_update_failure_disables_sparse_gracefully(
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
        collection_info.config.params.sparse_vectors = {}
        mock_qdrant_client.get_collection = AsyncMock(return_value=collection_info)
        mock_qdrant_client.update_collection = AsyncMock(side_effect=Exception("unsupported"))

        await rag_service.ensure_collection()

        assert rag_service._sparse_enabled is False

    async def test_upsert_includes_sparse_vector_when_enabled(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        rag_service._sparse_enabled = True
        mock_qdrant_client.upsert = AsyncMock()

        await rag_service.upsert_embedding("p1_en", [0.1, 0.2], "p1", "en", "silk dress")

        points = mock_qdrant_client.upsert.call_args.kwargs["points"]
        point = points[0]
        assert isinstance(point, PointStruct)
        assert isinstance(point.vector, dict)
        assert point.vector[""] == [0.1, 0.2]
        assert SPARSE_VECTOR_NAME in point.vector

    async def test_upsert_stays_dense_when_disabled(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_qdrant_client.upsert = AsyncMock()

        await rag_service.upsert_embedding("p1_en", [0.1, 0.2], "p1", "en", "silk dress")

        points = mock_qdrant_client.upsert.call_args.kwargs["points"]
        assert points[0].vector == [0.1, 0.2]


class TestHybridSearch:
    async def test_search_scored_hybrid_uses_prefetch_and_rrf(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        rag_service._sparse_enabled = True
        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.return_value.points = [_hit("p1", 0.9), _hit("p2", 0.8)]

        results = await rag_service.search_scored([0.1, 0.2], limit=10, query_text="red lace dress")

        assert [p.id for p, _ in results] == ["p1", "p2"]
        mock_qdrant_client.query_points.assert_awaited_once()
        kwargs = mock_qdrant_client.query_points.call_args.kwargs
        prefetch = kwargs["prefetch"]
        assert len(prefetch) == 2
        assert prefetch[0].using == ""
        assert prefetch[1].using == SPARSE_VECTOR_NAME
        assert prefetch[1].query == _sparse_tf_vector(_tokenize("red lace dress"))
        assert kwargs["query"].fusion == Fusion.RRF
        assert kwargs["limit"] == 15  # limit + 5
        expected_pool = min(10 * HYBRID_POOL_MULTIPLIER, HYBRID_POOL_MAX)
        assert prefetch[0].limit == expected_pool
        assert prefetch[1].limit == expected_pool

    async def test_search_scored_hybrid_dense_when_disabled(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.return_value.points = [_hit("p1", 0.9)]

        results = await rag_service.search_scored([0.1, 0.2], limit=10, query_text="red lace dress")

        assert [p.id for p, _ in results] == ["p1"]
        kwargs = mock_qdrant_client.query_points.call_args.kwargs
        assert "prefetch" not in kwargs
        assert kwargs["query"] == [0.1, 0.2]
        assert kwargs["score_threshold"] == 0.3

    async def test_search_scored_hybrid_dense_when_no_tokens(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        rag_service._sparse_enabled = True
        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.return_value.points = [_hit("p1", 0.9)]

        await rag_service.search_scored([0.1, 0.2], limit=10, query_text="!! 1 a")

        kwargs = mock_qdrant_client.query_points.call_args.kwargs
        assert "prefetch" not in kwargs

    async def test_search_scored_hybrid_exception_returns_empty(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        rag_service._sparse_enabled = True
        mock_qdrant_client.query_points = AsyncMock(side_effect=Exception("boom"))

        results = await rag_service.search_scored([0.1, 0.2], limit=10, query_text="red dress")

        assert results == []

    async def test_search_hybrid_threads_query_text(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        rag_service._sparse_enabled = True
        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.return_value.points = [_hit("p1", 0.9)]

        results = await rag_service.search([0.1, 0.2], limit=10, query_text="silk dress")

        assert [p.id for p in results] == ["p1"]
        kwargs = mock_qdrant_client.query_points.call_args.kwargs
        assert "prefetch" in kwargs

    async def test_filtered_search_hybrid_uses_prefetch(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        rag_service._sparse_enabled = True
        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.return_value.points = [_hit("p1", 0.9), _hit("p2", 0.8)]

        results = await rag_service.search_scored(
            [0.1, 0.2],
            limit=10,
            filters={"color": ["Red"]},
            query_text="red dress",
        )

        assert [p.id for p, _ in results] == ["p1", "p2"]
        first_call = mock_qdrant_client.query_points.call_args_list[0]
        kwargs = first_call.kwargs
        assert "prefetch" in kwargs
        assert kwargs["prefetch"][0].filter is not None


class TestSearchQualityPlan:
    async def test_search_scored_prefer_lang_replaces_same_product_point(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        en_hit = _hit("p1", 0.9, name="Dress", lang="en")
        ar_hit = _hit("p1", 0.7, name="فستان", lang="ar")

        mock_qdrant_client.query_points = AsyncMock(return_value=MagicMock(points=[en_hit, ar_hit]))

        results = await rag_service.search_scored(
            [0.1, 0.2],
            limit=10,
            query_text="red dress",
            prefer_lang="ar",
        )

        assert len(results) == 1
        ref, score = results[0]
        assert ref.id == "p1"
        assert ref.name == "فستان"
        assert score == 0.7

    async def test_search_scored_prefer_lang_keeps_first_when_no_lang_match(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        en_hit = _hit("p1", 0.9, name="Dress", lang="en")
        ar_hit = _hit("p1", 0.7, name="فستان", lang="ar")

        mock_qdrant_client.query_points = AsyncMock(return_value=MagicMock(points=[ar_hit, en_hit]))

        results = await rag_service.search_scored(
            [0.1, 0.2],
            limit=10,
            query_text="red dress",
            prefer_lang="en",
        )

        assert len(results) == 1
        ref, score = results[0]
        assert ref.name == "Dress"
        assert score == 0.9

    async def test_search_scored_dedupe_across_tiers(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        tier1 = [_hit(f"p{i}", 0.9, lang="en") for i in range(3)]
        tier2 = [_hit("p1", 0.5, lang="ar"), _hit("p9", 0.4, lang="ar")]

        mock_qdrant_client.query_points = AsyncMock()
        mock_qdrant_client.query_points.side_effect = [
            MagicMock(points=tier1),
            MagicMock(points=tier2),
        ]

        results = await rag_service.search_scored(
            [0.1, 0.2],
            limit=10,
            filters={"color": ["Red"]},
            query_text="red dress",
            prefer_lang="ar",
        )

        assert [p.id for p, _ in results] == ["p0", "p1", "p2", "p9"]

    async def test_upsert_embeds_sparse_with_boosted_name_tokens(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        rag_service._sparse_enabled = True
        await rag_service.upsert_embedding(
            point_id="pt-1",
            vector=[0.1, 0.2],
            product_id="p1",
            lang="en",
            text="Red lace dress",
            payload={"product_data": {"en": {"name": "Red Lace Dress"}}},
        )

        mock_qdrant_client.upsert.assert_awaited_once()
        point = mock_qdrant_client.upsert.call_args.kwargs["points"][0]
        sparse = point.vector[SPARSE_VECTOR_NAME]
        by_index = dict(zip(sparse.indices, sparse.values, strict=True))
        assert by_index[_fnv1a("red")] == 2.0
        assert by_index[_fnv1a("lace")] == 2.0
        assert by_index[_fnv1a("dress")] == 2.0

    async def test_fusion_and_pool_knobs_reach_query_points(
        self,
        settings: Settings,
        mock_qdrant_client: MagicMock,
    ) -> None:
        rag_service = RAGService(
            settings,
            client=mock_qdrant_client,
            hybrid_pool_multiplier=2,
            hybrid_pool_max=50,
            fusion=Fusion.DBSF,
        )
        rag_service._sparse_enabled = True
        mock_qdrant_client.query_points = AsyncMock(return_value=MagicMock(points=[]))

        await rag_service.search_scored([0.1, 0.2], limit=10, query_text="red dress")

        kwargs = mock_qdrant_client.query_points.call_args.kwargs
        assert kwargs["query"].fusion == Fusion.DBSF
        pool = 10 * 2
        assert kwargs["prefetch"][0].limit == pool
        assert kwargs["prefetch"][1].limit == pool
        assert kwargs["prefetch"][0].limit <= 50

    async def test_default_pool_cap_is_100(
        self,
        rag_service: RAGService,
        mock_qdrant_client: MagicMock,
    ) -> None:
        mock_qdrant_client.query_points = AsyncMock(return_value=MagicMock(points=[]))
        rag_service._sparse_enabled = True

        await rag_service.search_scored([0.1, 0.2], limit=60, query_text="red dress")

        kwargs = mock_qdrant_client.query_points.call_args.kwargs
        assert kwargs["prefetch"][0].limit == HYBRID_POOL_MAX
