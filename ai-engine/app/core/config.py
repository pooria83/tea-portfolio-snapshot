from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
    )

    app_name: str = "Product Graph AI Engine"
    debug: bool = False

    ai_engine_port: int = 8003

    engine_api_key: str = Field(
        default="",
        description="Shared secret the backend API sends as X-API-Key. Empty disables the auth guard (local dev only).",
    )

    opencode_zen_api_key: str = Field(default="")
    openrouter_api_key: str = Field(default="")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_encryption_key: str = Field(default="")

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "products"
    qdrant_api_key: str | None = None

    database_url: str = Field(
        default="postgresql+asyncpg://<REDACTED>@localhost/portfolio",
    )

    llm_model: str = "deepseek-v4-flash-free"
    embedding_provider: str = Field(
        default="sentence_transformer",
        description="Embedding provider: sentence_transformer (local CPU), tei (remote/Colab tunnel), or openrouter",
    )
    tei_base_url: str = Field(
        default="http://localhost:8080/v1",
        description="TEI base URL. Set to Colab tunnel URL (https://xxx.trycloudflare.com/v1) for remote GPU embeddings",
    )
    embedding_model: str = "Qwen/Qwen3-Embedding-4B"
    embedding_dimensions: int = 2560

    ai_engine_config_path: str = Field(
        default="/data/engine-config.json",
        description="Path to the runtime config JSON file. Set to ./engine-config.json for local dev without Docker.",
    )

    user_comm_model: str = Field(
        default="deepseek-v4-flash-free",
        description="Default model for chatbot conversations (can be overridden at runtime via /config)",
    )

    activity_log_dir: str = Field(
        default="./logs",
        description="Directory for JSONL activity log files",
    )

    api_bootstrap_url: str = Field(
        default="http://api:8000/api/v1/webhook/ai-engine-bootstrap",
        description="URL for the API bootstrap webhook called when no runtime config file exists",
    )

    @property
    def opencode_zen_base_url(self) -> str:
        return "https://opencode.ai/zen/v1"
