import json
import uuid

from loguru import logger
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIEngineClient
from app.core.cache import invalidate_tables
from app.core.crypto import encrypt_api_key
from app.core.error_codes import E
from app.core.exceptions import ValidationError
from app.models.system_setting import SystemSetting
from app.repositories.embedding import EmbedModelRepository
from app.repositories.settings import SystemSettingRepository
from app.schemas.system_setting import SystemSettingResponse

VALID_EMBEDDING_PROVIDERS = ("sentence_transformer", "tei", "openrouter")


def _parse_embedding_provider(raw: str) -> dict[str, object]:
    """Accept either a JSON config dict or a legacy plain provider name."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"provider": raw}
    if isinstance(parsed, dict):
        return parsed
    return {"provider": raw}


async def _validate_embedding_provider(
    conf: dict[str, object],
    existing_conf: dict[str, object] | None,
    db: AsyncSession,
    redis: AsyncRedis | None = None,
) -> dict[str, object]:
    provider = conf.get("provider")
    if provider not in VALID_EMBEDDING_PROVIDERS:
        raise ValidationError("Invalid embedding provider", translation_key=E.EMBED_PROVIDER_INVALID)

    if provider == "tei":
        model = str(conf.get("model") or "").strip()
        if not model:
            raise ValidationError("Embedding model is required", translation_key=E.EMBED_MODEL_REQUIRED)
        repo = EmbedModelRepository(db, redis)
        if not await repo.get_active_by_name(model):
            raise ValidationError("Embedding model not found", translation_key=E.EMBED_MODEL_NOT_FOUND)
        if not str(conf.get("base_url") or "").strip():
            raise ValidationError("TEI tunnel URL is required", translation_key=E.EMBED_TUNNEL_URL_REQUIRED)

        api_key = str(conf.get("api_key") or "").strip()
        need_api_key = bool(conf.get("need_api_key"))
        if need_api_key and not api_key:
            stored_key = str(existing_conf.get("api_key") or "") if existing_conf else ""
            if not existing_conf or not existing_conf.get("api_key_encrypted") or not stored_key:
                raise ValidationError("API key is required", translation_key=E.EMBED_API_KEY_REQUIRED)
            conf["api_key"] = stored_key
            conf["api_key_encrypted"] = True
        elif api_key and len(api_key) < 5:
            raise ValidationError("API key must be at least 5 characters", translation_key=E.EMBED_API_KEY_TOO_SHORT)
        elif api_key:
            conf["api_key"] = encrypt_api_key(api_key)
            conf["api_key_encrypted"] = True
        else:
            conf["api_key"] = ""
            conf["api_key_encrypted"] = False

        conf["model"] = model
        conf["base_url"] = str(conf.get("base_url") or "").strip()

    return conf


async def list_settings(db: AsyncSession, redis: AsyncRedis | None = None) -> list[dict[str, str]]:
    return await SystemSettingRepository(db, redis).list_all()


async def update_setting(
    db: AsyncSession,
    ai_client: AIEngineClient,
    key: str,
    value: str,
    request_id: str = "",
    redis: AsyncRedis | None = None,
) -> SystemSetting:
    repo = SystemSettingRepository(db, redis)
    setting = await repo.get_by_key_orm(key)
    old_conf = _parse_embedding_provider(setting.value) if setting else None

    if key == "embedding_provider":
        conf = await _validate_embedding_provider(_parse_embedding_provider(value), old_conf, db, redis)
        value = json.dumps(conf)

    if not setting:
        setting = SystemSetting(id=str(uuid.uuid4()), key=key, value=value)
        db.add(setting)
    else:
        setting.value = value

    await db.commit()
    await db.refresh(setting)

    if redis is not None:
        await invalidate_tables(redis, {"system_settings"})

    await apply_setting_to_ai_engine(db, ai_client, key, value, old_conf, request_id, redis)
    return setting


async def apply_setting_to_ai_engine(
    db: AsyncSession,
    ai_client: AIEngineClient,
    key: str,
    value: str,
    old_conf: dict[str, object] | None,
    request_id: str = "",
    redis: AsyncRedis | None = None,
) -> None:
    """Forward embedding config to the AI Engine, re-indexing when the model changed."""
    if key not in ("tei_tunnel_url", "embedding_provider"):
        return
    try:
        payload: dict[str, object] = {}
        if key == "tei_tunnel_url":
            payload["tei_base_url"] = value
        elif key == "embedding_provider":
            new_conf = _parse_embedding_provider(value)
            payload["embedding_provider"] = new_conf
            new_model = str(new_conf.get("model") or "")
            old_model = str(old_conf.get("model") or "") if old_conf else ""
            if new_model and new_model != old_model:
                from app.services.embedding_config import get_active_embedding_model
                from app.services.embedding_cron import reindex_active_model

                try:
                    active_model, _ = await get_active_embedding_model(db, redis)
                    affected = await reindex_active_model(db, active_model)
                    await db.commit()
                    logger.info(
                        "Embedding model changed ({} -> {}), {} products re-indexed",
                        old_model,
                        active_model,
                        affected,
                    )
                except Exception as exc:
                    logger.warning("Auto re-index after model switch failed: {}", exc)
        await ai_client.update_config(payload, request_id=request_id)
        logger.info("Forwarded {} to AI Engine config", key)
    except Exception as exc:
        logger.warning("Failed to forward config to AI Engine: {}", exc)


def to_response(setting: SystemSetting) -> SystemSettingResponse:
    return SystemSettingResponse(key=setting.key, value=setting.value)
