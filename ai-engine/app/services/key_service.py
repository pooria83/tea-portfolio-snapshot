from __future__ import annotations

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.crypto import decrypt_api_key
from app.services.llm_client import LLMClient

PROVIDER_BASE_URLS: dict[str, str] = {
    "opencode_zen": "https://opencode.ai/zen/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


async def build_llm_client(
    db_engine: AsyncEngine,
    model_name: str,
    settings: Settings,
) -> LLMClient:
    """Build the default OpenCode Zen LLM client, resolving the key from DB or env.

    Shared by the startup lifespan and ``POST /config`` refresh so both paths
    construct the client identically.
    """
    api_key = await resolve_active_api_key(
        db_engine,
        model_name,
        settings.llm_encryption_key,
        settings.opencode_zen_api_key,
    )
    return LLMClient(
        api_key=api_key or settings.opencode_zen_api_key,
        base_url=settings.opencode_zen_base_url,
        model=model_name,
        provider="opencode_zen",
    )


async def resolve_active_api_key(
    db_engine: AsyncEngine,
    model_name: str,
    encryption_key: str | None,
    fallback_key: str | None = None,
) -> str | None:
    query = text("""
        SELECT k.api_key_encrypted
        FROM llm_api_keys k
        JOIN llm_models m ON m.id = k.model_id
        WHERE m.model = :model_name
          AND k.is_active = true
          AND m.is_active = true
        LIMIT 1
    """)
    async with db_engine.connect() as conn:
        result = await conn.execute(query, {"model_name": model_name})
        row = result.fetchone()

    if row:
        try:
            return decrypt_api_key(row[0], encryption_key)
        except Exception as exc:
            logger.error("Failed to decrypt API key for model '{}': {}", model_name, exc)

    if fallback_key:
        logger.info("No active DB key for model '{}'; using env fallback", model_name)
        return fallback_key

    logger.warning("No active API key found for model '{}'", model_name)
    return None


async def resolve_model_info(
    db_engine: AsyncEngine,
    model_name: str,
    encryption_key: str | None,
) -> dict[str, str] | None:
    query = text("""
        SELECT k.api_key_encrypted, m.provider
        FROM llm_api_keys k
        JOIN llm_models m ON m.id = k.model_id
        WHERE m.model = :model_name
          AND k.is_active = true
          AND m.is_active = true
        LIMIT 1
    """)
    async with db_engine.connect() as conn:
        result = await conn.execute(query, {"model_name": model_name})
        row = result.fetchone()

    if not row:
        logger.warning("No active API key found for model '{}'", model_name)
        return None

    encrypted_key, provider = row
    try:
        api_key = decrypt_api_key(encrypted_key, encryption_key)
    except Exception as exc:
        logger.error("Failed to decrypt API key for model '{}': {}", model_name, exc)
        return None

    base_url = PROVIDER_BASE_URLS.get(provider)
    if not base_url:
        logger.error("Unknown provider '{}' for model '{}'", provider, model_name)
        return None

    return {"api_key": api_key, "base_url": base_url, "provider": provider}
