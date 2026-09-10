from app.core.config import Settings


def test_default_values() -> None:
    s = Settings(_env_file=None, opencode_zen_api_key="", openrouter_api_key="")
    assert s.app_name == "Product Graph AI Engine"
    assert s.debug is False
    assert s.ai_engine_port == 8003
    assert s.opencode_zen_api_key == ""
    assert s.openrouter_api_key == ""
    assert s.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert s.qdrant_url == "http://localhost:6333"
    assert s.qdrant_collection == "products"
    assert s.llm_model == "deepseek-v4-flash-free"
    assert s.embedding_model == "Qwen/Qwen3-Embedding-4B"
    assert s.embedding_dimensions == 2560


def test_opencode_zen_base_url() -> None:
    s = Settings()
    assert s.opencode_zen_base_url == "https://opencode.ai/zen/v1"


def test_custom_values() -> None:
    s = Settings(
        app_name="Custom AI Engine",
        debug=True,
        ai_engine_port=9000,
        opencode_zen_api_key="custom-key",
        openrouter_api_key="custom-router-key",
        qdrant_url="http://qdrant:6333",
        qdrant_collection="custom_collection",
        llm_model="gpt-4",
        embedding_model="text-embedding-3",
        embedding_dimensions=1536,
    )
    assert s.app_name == "Custom AI Engine"
    assert s.debug is True
    assert s.ai_engine_port == 9000
    assert s.opencode_zen_api_key == "custom-key"
    assert s.openrouter_api_key == "custom-router-key"
    assert s.qdrant_url == "http://qdrant:6333"
    assert s.qdrant_collection == "custom_collection"
    assert s.llm_model == "gpt-4"
    assert s.embedding_model == "text-embedding-3"
    assert s.embedding_dimensions == 1536
