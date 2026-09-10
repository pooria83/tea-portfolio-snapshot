from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_admin_user
from app.core.redis import get_redis
from app.core.response import APIResponse, success
from app.models.llm import LLMApiKey, LLMModel
from app.models.llm_setting import LLMSetting
from app.models.user import User
from app.schemas.llm import AddApiKeyRequest, AddApiKeyResponse, LLMApiKeyResponse, LLMModelResponse, LLMSettingsResponse, LLMSettingsUpdate
from app.services import llm_service

router = APIRouter(prefix="/admin/llm", tags=["admin-llm"])


def _mask_key(raw: str) -> str:
    raw = raw.strip()
    if len(raw) <= 8:
        return raw[:2] + "****" + raw[-2:]
    return raw[:3] + "****" + raw[-4:]


def _to_api_key_response(key: LLMApiKey) -> LLMApiKeyResponse:
    return LLMApiKeyResponse(
        id=key.id,
        model_id=key.model_id,
        name=key.name,
        is_active=key.is_active,
        masked_key=_mask_key(key.api_key_encrypted),
        created_at=key.created_at,
    )


def _to_model_response(m: LLMModel) -> LLMModelResponse:
    return LLMModelResponse(
        id=m.id,
        provider=m.provider,
        model=m.model,
        is_active=m.is_active,
        context_window=m.context_window,
        api_keys=[_to_api_key_response(k) for k in m.api_keys],
    )


def _to_settings_response_from_model(setting: LLMSetting | None) -> LLMSettingsResponse:
    def _model_response(m: LLMModel | None) -> LLMModelResponse | None:
        if m is None:
            return None
        return LLMModelResponse(
            id=m.id,
            provider=m.provider,
            model=m.model,
            is_active=m.is_active,
            context_window=m.context_window,
            api_keys=[],
        )

    if setting is None:
        return LLMSettingsResponse(
            default_llm_model_id=None,
            default_llm_model=None,
            user_comm_model_id=None,
            user_comm_model=None,
        )
    return LLMSettingsResponse(
        default_llm_model_id=setting.default_llm_model_id,
        default_llm_model=_model_response(setting.default_llm_model),
        user_comm_model_id=setting.user_comm_model_id,
        user_comm_model=_model_response(setting.user_comm_model),
    )


@router.get("/models", response_model=APIResponse[list[LLMModelResponse]])
async def list_models(
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[LLMModelResponse]]:
    models = await llm_service.list_models(db)
    return success([_to_model_response(m) for m in models])


@router.post("/api-keys", response_model=APIResponse[AddApiKeyResponse], status_code=201)
async def add_api_key(
    body: AddApiKeyRequest,
    request: Request,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[AddApiKeyResponse]:
    api_key = await llm_service.add_api_key(db, body.model_id, body.name or None, body.api_key, redis=redis)

    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = api_key.id
        activity["message"] = f"admin create api_key {api_key.id} for model {api_key.model_id}"

    return success(
        AddApiKeyResponse(
            id=api_key.id,
            model_id=api_key.model_id,
            name=api_key.name,
            is_active=api_key.is_active,
            masked_key=_mask_key(body.api_key),
            created_at=api_key.created_at,
        )
    )


@router.patch("/api-keys/{key_id}/toggle", response_model=APIResponse[LLMApiKeyResponse])
async def toggle_api_key(
    key_id: str,
    request: Request,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[LLMApiKeyResponse]:
    api_key = await llm_service.toggle_api_key(db, key_id, redis=redis)

    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = key_id
        activity["action"] = "TOGGLE"
        activity["message"] = f"admin toggle api_key {key_id} active={api_key.is_active}"

    return success(_to_api_key_response(api_key))


@router.delete("/api-keys/{key_id}", status_code=204)
async def delete_api_key(
    key_id: str,
    request: Request,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> None:
    await llm_service.delete_api_key(db, key_id, redis=redis)
    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["resource_id"] = key_id
        activity["message"] = f"admin delete api_key {key_id}"


@router.get("/settings", response_model=APIResponse[LLMSettingsResponse])
async def get_llm_settings(
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[LLMSettingsResponse]:
    setting = await llm_service.get_settings(db)
    return success(_to_settings_response_from_model(setting))


@router.put("/settings", response_model=APIResponse[LLMSettingsResponse])
async def update_llm_settings(
    body: LLMSettingsUpdate,
    request: Request,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[LLMSettingsResponse]:
    updated = body.model_dump(exclude_unset=True)
    setting = await llm_service.update_settings(
        db,
        body.default_llm_model_id,
        body.user_comm_model_id,
        include_default="default_llm_model_id" in updated,
        include_user_comm="user_comm_model_id" in updated,
        redis=redis,
    )

    ai_client = request.app.state.ai_client
    if setting.default_llm_model_id:
        await llm_service.forward_model_to_ai(ai_client, db, setting.default_llm_model_id, "default_llm_model", request_id=request.scope.get("request_id", ""), redis=redis)
    if setting.user_comm_model_id:
        await llm_service.forward_model_to_ai(ai_client, db, setting.user_comm_model_id, "user_comm_model", request_id=request.scope.get("request_id", ""), redis=redis)

    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["action"] = "UPDATE"
        activity["resource_type"] = "llm_config"
        activity["message"] = "admin update llm settings"

    return success(_to_settings_response_from_model(setting))
