import warnings
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict  # noqa: I001

_SECRET_DEFAULTS = {"change-me", "change-me-jwt", "change-me-api-key"}
_CREDENTIAL_DEFAULTS = {"minioadmin", "change-me", "postgres"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
    )

    app_name: str = "Product Graph API"
    debug: bool = False
    secret_key: str = Field(default="change-me", min_length=8)
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"
    allowed_origin_regex: str = "https?://([a-zA-Z0-9-]+\\.)*portfolio\\.example\\.invalid"
    allowed_redirect_uris: str = Field(
        default="http://localhost:8001/auth/google/callback,https://portfolio.example.invalid/auth/google/callback,https://portfolio.example.invalid/auth/google/callback,https://portfolio.example.invalid/auth/google/callback",
        description="Comma-separated allowlist of Google OAuth redirect URIs",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://<REDACTED>@localhost/portfolio",
    )
    database_url_sync: str = Field(
        default="postgresql://<REDACTED>@localhost/portfolio",
    )

    redis_url: str = Field(default="redis://localhost:6379/0", pattern=r"^redis://.+")

    rabbitmq_url: str = Field(default="amqp://<REDACTED>@localhost/portfolio", pattern=r"^amqps?://.+")

    mongo_url: str = Field(
        default="",
        description="MongoDB Atlas connection string (empty disables chat history)",
    )
    mongo_db_name: str = Field(default="tea-dev", min_length=1, description="MongoDB database name per environment (tea-dev / tea-production)")

    chat_max_messages: int = Field(default=20, ge=1, le=100, description="Max user messages per conversation before auto-close")
    chat_history_window: int = Field(default=12, ge=1, le=100, description="Full-fidelity message window sent to the engine")
    chat_compact_threshold_tokens: int = Field(default=4000, ge=500, description="Unsummarized token threshold that triggers rolling compaction")

    jwt_secret_key: str = Field(default="change-me-jwt", min_length=8)
    jwt_algorithm: str = "HS256"
    jwt_audience: str = "product-graph-api"
    jwt_issuer: str = "product-graph-api"

    cookie_secure: bool = Field(
        default=False,
        description="Set the Secure flag on auth cookies. Must be enabled in staging/production (HTTPS).",
    )
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    oauth_state_expire_seconds: int = Field(default=600, ge=60, le=3600)

    environment: str = Field(default="development", pattern=r"^(development|staging|production)$")
    git_sha: str = Field(default="dev", description="Git commit SHA baked in at Docker build time; 'dev' when running locally")
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=90)

    api_key: str = Field(default="change-me-api-key", min_length=8)

    ai_engine_url: str = Field(default="http://ai-engine:8001", pattern=r"^https?://.+")
    api_base_url: str = Field(default="http://localhost:8000", pattern=r"^https?://.+")
    webhook_secret: str = Field(default="", min_length=0, description="Shared secret for AI Engine webhook callbacks; empty disables webhook verification")
    llm_encryption_key: str = Field(default="")

    zara_scraper_api_base_url: str = Field(default="http://localhost:8000", pattern=r"^https?://.+")
    zara_scraper_store_id: str = Field(default="4c937155-aa37-4057-a629-45e29b118c33", min_length=1)
    zara_scraper_api_token: str = Field(default="")

    minio_endpoint: str = Field(default="localhost:9000", pattern=r"^[a-zA-Z0-9.-]+:\d+$")
    minio_access_key: str = Field(default="minioadmin", min_length=3)
    minio_secret_key: str = Field(default="minioadmin", min_length=3)
    minio_secure: bool = False
    minio_public_url: str = Field(
        default="https://portfolio.example.invalid", description="Public-facing base URL for direct file access (e.g. https://portfolio.example.invalid; dev may override with https://portfolio.example.invalid)"
    )
    minio_bucket: str = Field(default="product-graph", min_length=1)
    minio_temp_bucket: str = Field(default="temp-files", min_length=1)
    minio_profile_bucket: str = Field(default="profile-photos", min_length=1)
    minio_store_bucket: str = Field(default="store-photos", min_length=1)

    max_upload_size: int = Field(default=10 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)  # 10 MiB default

    rate_limit_default: str = "100/minute"
    login_max_attempts: int = Field(default=5, ge=1, le=100)
    login_lockout_minutes: int = Field(default=15, ge=1, le=1440)
    login_lockout_multiplier: int = Field(default=2, ge=1, le=10)

    twilio_account_sid: str = Field(default="")
    twilio_auth_token: str = Field(default="")
    twilio_phone_number: str = Field(default="")
    twilio_bypass: bool = Field(default=False)

    google_web_client_id: str = Field(default="")
    google_android_client_id: str = Field(default="")
    google_ios_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")

    otp_code_length: int = Field(default=6, ge=4, le=8)
    otp_expire_seconds: int = Field(default=300, ge=60, le=600)
    otp_max_send_per_phone: int = Field(default=3, ge=1, le=10)
    otp_max_verify_attempts: int = Field(default=5, ge=1, le=10)

    tea_image_cache_dir: str = Field(default="/tmp/tea-assist-img-cache", description="Directory for image cache in scraper transformer")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError("database_url must be a PostgreSQL connection string")
        return v

    @field_validator("mongo_url")
    @classmethod
    def validate_mongo_url(cls, v: str) -> str:
        if v and not v.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError("mongo_url must be a MongoDB connection string")
        return v

    @field_validator("allowed_origins")
    @classmethod
    def validate_allowed_origins(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("allowed_origins must not be empty")
        return v

    @model_validator(mode="after")
    def warn_production_origins(self) -> "Settings":
        if not self.debug:
            local_origins = [o for o in self.origins_list if "localhost" in o or "127.0.0.1" in o]
            if local_origins and len(self.origins_list) == len(local_origins):
                warnings.warn(
                    "ALLOWED_ORIGINS only contains localhost/127.0.0.1 addresses but debug=False. Set ALLOWED_ORIGINS env var to your production frontend URL(s).",
                    stacklevel=2,
                )
            if "*" in self.origins_list:
                warnings.warn(
                    "Wildcard origin '*' in ALLOWED_ORIGINS is insecure. List specific origins for production.",
                    stacklevel=2,
                )
            for field, _default in [("secret_key", "change-me"), ("jwt_secret_key", "change-me-jwt")]:
                value = getattr(self, field, None)
                if value in _SECRET_DEFAULTS:
                    warnings.warn(
                        f"{field.upper()} is still set to the default value. Change it in production.",
                        stacklevel=2,
                    )
        return self

    @model_validator(mode="after")
    def validate_cors_credentials(self) -> "Settings":
        if "*" in self.origins_list:
            warnings.warn(
                "CORS allow_origins contains '*'. Combined with allow_credentials=True, this is insecure per the CORS spec.",
                stacklevel=2,
            )
        return self

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def allowed_redirect_uris_set(self) -> frozenset[str]:
        return frozenset(u.strip() for u in self.allowed_redirect_uris.split(",") if u.strip())


settings = Settings()
