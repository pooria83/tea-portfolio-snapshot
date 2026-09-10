import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from loguru import logger
from pydantic import BaseModel
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIEngineClient
from app.core.cache import invalidate_tables
from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import verify_webhook_secret
from app.repositories.embedding import EmbedModelRepository, ProductEmbeddingRepository
from app.repositories.llm import LLMSettingRepository
from app.repositories.settings import SystemSettingRepository
from app.services import llm_service
from app.services.embedding_config import get_active_embedding_model

router = APIRouter(tags=["webhooks"])


class EmbeddingResultRequest(BaseModel):
    product_id: str
    lang: str
    status: str
    error: str | None = None
    model: str | None = None


def _parse_embedding_provider_config(raw: str) -> dict[str, object] | None:
    """Parse the stored embedding_provider system setting into a config dict.

    Accepts the JSON dict form (provider, model, base_url, api_key) and
    returns None for legacy plain provider names or invalid values.
    """
    try:
        parsed: Any = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict) or not parsed.get("provider"):
        return None
    return parsed


@router.post("/webhook/embedding-result", dependencies=[Depends(verify_webhook_secret)])
async def embedding_result_webhook(
    body: EmbeddingResultRequest,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> dict[str, str]:
    logger.info(
        "Embedding webhook received: product={} lang={} status={} model={} error={}",
        body.product_id,
        body.lang,
        body.status,
        body.model,
        body.error,
    )

    if body.model:
        model_name = body.model
    else:
        model_name, _ = await get_active_embedding_model(db, redis)
    status = "done" if body.status == "done" else "error"
    error = None if status == "done" else (body.error or "embedding failed")

    model_id = await EmbedModelRepository(db).get_id_by_name(model_name)

    await ProductEmbeddingRepository(db).upsert_status(
        product_id=body.product_id,
        model_id=model_id,
        model_name=model_name,
        status=status,
        error=error,
    )
    await invalidate_tables(redis, {"product_embeddings"})
    return {"status": "ok"}


@router.post("/webhook/ai-engine-bootstrap", dependencies=[Depends(verify_webhook_secret)])
async def ai_engine_bootstrap(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> dict[str, str]:
    logger.info("AI Engine bootstrap webhook received")

    config: dict[str, object] = {}

    sys_settings = await SystemSettingRepository(db, redis).list_by_keys(["tei_tunnel_url", "embedding_provider"])
    settings_by_key = {s["key"]: s["value"] for s in sys_settings}

    tunnel_url = settings_by_key.get("tei_tunnel_url", "")
    if tunnel_url:
        config["tei_base_url"] = tunnel_url

    embedding_provider_raw = settings_by_key.get("embedding_provider", "")
    ep_cfg = _parse_embedding_provider_config(embedding_provider_raw)
    if ep_cfg:
        if ep_cfg.get("provider") == "tei" and not ep_cfg.get("base_url") and tunnel_url:
            ep_cfg["base_url"] = tunnel_url
        config["embedding_provider"] = ep_cfg

    llm_setting = await LLMSettingRepository(db, redis).get_single_dto()

    if llm_setting:
        default_id = llm_setting.get("default_llm_model_id")
        if default_id:
            cfg = await llm_service.resolve_model_config(db, default_id, redis)
            if cfg:
                config["default_llm_model"] = cfg
        user_comm_id = llm_setting.get("user_comm_model_id")
        if user_comm_id:
            cfg = await llm_service.resolve_model_config(db, user_comm_id, redis)
            if cfg:
                config["user_comm_model"] = cfg

    ai_client: AIEngineClient = request.app.state.ai_client
    await ai_client.update_config(config, request_id=request.scope.get("request_id", ""))

    logger.info("AI Engine bootstrap config pushed: {}", list(config.keys()))
    return {"status": "ok"}
