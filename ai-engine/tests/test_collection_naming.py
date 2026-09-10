from app.services.collection_naming import collection_name_for, collection_slug


class TestCollectionSlug:
    def test_simple_model(self) -> None:
        assert collection_slug("Qwen/Qwen3-Embedding-0.6B") == "qwen-qwen3-embedding-0-6b"

    def test_collapses_runs(self) -> None:
        assert collection_slug("BAAI/bge-m3") == "baai-bge-m3"

    def test_trims_edges(self) -> None:
        assert collection_slug("/BAAI/bge-m3/") == "baai-bge-m3"

    def test_empty(self) -> None:
        assert collection_slug("!!!") == ""


class TestCollectionNameFor:
    def test_regular_model(self) -> None:
        assert collection_name_for("Qwen/Qwen3-Embedding-0.6B") == "products-qwen-qwen3-embedding-0-6b"

    def test_falls_back_to_hash_for_very_long_model(self) -> None:
        long_model = "x" * 300
        name = collection_name_for(long_model)
        assert name.startswith("products-")
        assert len(name) <= 200
        assert name == collection_name_for(long_model)

    def test_falls_back_to_hash_for_empty(self) -> None:
        name = collection_name_for("!!!")
        assert name.startswith("products-")
        assert len(name) == len("products-") + 12

    def test_hash_fallback_stable(self) -> None:
        assert collection_name_for("a" * 300) == collection_name_for("a" * 300)
