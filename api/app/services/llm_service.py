from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIEngineClient
from app.core.cache import CacheKeys, cache_or_fetch, invalidate_tables
from app.core.crypto import decrypt_api_key, encrypt_api_key
from app.core.error_codes import E
from app.core.exceptions import NotFoundError
from app.models.llm import LLMApiKey, LLMModel
from app.models.llm_setting import LLMSetting
from app.repositories.llm import LLMApiKeyRepository, LLMModelRepository, LLMSettingRepository

PROVIDER_BASE_URLS: dict[str, str] = {
    "opencode_zen": "https://opencode.ai/zen/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


async def list_models(db: AsyncSession) -> list[LLMModel]:
    return await LLMModelRepository(db).list_with_api_keys()


async def get_model_or_404(db: AsyncSession, model_id: str) -> LLMModel:
    model = await LLMModelRepository(db).get(model_id)
    if not model:
        raise NotFoundError("LLM model not found", translation_key=E.LLM_MODEL_NOT_FOUND)
    return model


async def add_api_key(
    db: AsyncSession,
    model_id: str,
    name: str | None,
    api_key: str,
    redis: AsyncRedis | None = None,
) -> LLMApiKey:
    model = await get_model_or_404(db, model_id)
    encrypted = encrypt_api_key(api_key)
    api_key_row = LLMApiKey(model_id=model.id, name=name, api_key_encrypted=encrypted)
    db.add(api_key_row)
    await db.commit()
    await db.refresh(api_key_row)
    if redis is not None:
        await invalidate_tables(redis, {"llm_api_keys", "llm_models"})
    return api_key_row


async def get_api_key_or_404(db: AsyncSession, key_id: str) -> LLMApiKey:
    api_key = await LLMApiKeyRepository(db).get(key_id)
    if not api_key:
        raise NotFoundError("API key not found", translation_key=E.API_KEY_NOT_FOUND)
    return api_key


async def toggle_api_key(db: AsyncSession, key_id: str, redis: AsyncRedis | None = None) -> LLMApiKey:
    api_key = await get_api_key_or_404(db, key_id)
    api_key.is_active = not api_key.is_active
    await db.commit()
    await db.refresh(api_key)
    if redis is not None:
        await invalidate_tables(redis, {"llm_api_keys"})
    return api_key


async def delete_api_key(db: AsyncSession, key_id: str, redis: AsyncRedis | None = None) -> None:
    api_key = await get_api_key_or_404(db, key_id)
    await db.delete(api_key)
    await db.commit()
    if redis is not None:
        await invalidate_tables(redis, {"llm_api_keys"})


async def get_settings(db: AsyncSession) -> LLMSetting | None:
    return await LLMSettingRepository(db).get_single()


async def get_settings_dto(db: AsyncSession, redis: AsyncRedis | None = None) -> dict[str, str | None] | None:
    """Cached id-only view of the LLM settings row (hot read paths)."""
    return await LLMSettingRepository(db, redis).get_single_dto()


async def update_settings(
    db: AsyncSession,
    default_llm_model_id: str | None,
    user_comm_model_id: str | None,
    include_default: bool,
    include_user_comm: bool,
    redis: AsyncRedis | None = None,
) -> LLMSetting:
    repo = LLMSettingRepository(db, redis)
    setting = await repo.get_single()
    if not setting:
        setting = LLMSetting()
        db.add(setting)

    if include_default:
        if default_llm_model_id is not None:
            await get_model_or_404(db, default_llm_model_id)
            setting.default_llm_model_id = default_llm_model_id
        else:
            setting.default_llm_model_id = None
    if include_user_comm:
        if user_comm_model_id is not None:
            await get_model_or_404(db, user_comm_model_id)
            setting.user_comm_model_id = user_comm_model_id
        else:
            setting.user_comm_model_id = None

    await db.commit()
    await db.refresh(setting)
    if redis is not None:
        await invalidate_tables(redis, {"llm_settings"})
    return setting


async def resolve_model_config(db: AsyncSession, model_id: str, redis: AsyncRedis | None = None) -> dict[str, str] | None:
    """Return {model, api_key, base_url} for an active model with an active key.

    Cached per model (short TTL) and invalidated on any ``llm_models`` /
    ``llm_api_keys`` write; fails open to the database when Redis is down.
    """

    async def _fetch() -> dict[str, str] | None:
        from loguru import logger

        model = await LLMModelRepository(db).get_active_with_api_keys(model_id)
        if not model:
            return None
        active_key = next((k for k in model.api_keys if k.is_active), None)
        if not active_key:
            return None
        try:
            api_key = decrypt_api_key(active_key.api_key_encrypted)
        except Exception as exc:
            logger.warning("Failed to decrypt API key for model {}: {}", model.model, exc)
            return None
        base_url = PROVIDER_BASE_URLS.get(model.provider)
        if not base_url:
            logger.warning("Unknown provider {} for model {}", model.provider, model.model)
            return None
        return {"model": model.model, "api_key": api_key, "base_url": base_url}

    if redis is None:
        return await _fetch()
    return await cache_or_fetch(redis, CacheKeys.llm_model_config(model_id), CacheKeys.LLM_MODEL_CONFIG.ttl, _fetch)


async def forward_model_to_ai(
    ai_client: AIEngineClient,
    db: AsyncSession,
    model_id: str,
    config_key: str,
    request_id: str = "",
    redis: AsyncRedis | None = None,
) -> None:
    """Push a model's active API key + base URL to the AI Engine config."""
    from loguru import logger

    config = await resolve_model_config(db, model_id, redis)
    if not config:
        logger.warning(
            "Cannot forward model {} ({}): no resolvable active key — AI Engine keeps its previous config",
            model_id,
            config_key,
        )
        return
    try:
        await ai_client.update_config({config_key: config}, request_id=request_id)
    except Exception as exc:
        logger.warning("Failed to forward model {} ({}) to AI Engine: {}", model_id, config_key, exc)
