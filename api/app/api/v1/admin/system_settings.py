from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_admin_user
from app.core.redis import get_redis
from app.core.response import APIResponse, success
from app.models.user import User
from app.schemas.system_setting import SystemSettingResponse, SystemSettingUpdate
from app.services import system_setting_service

router = APIRouter(prefix="/admin/system-settings", tags=["admin-system-settings"])


@router.get("", response_model=APIResponse[list[SystemSettingResponse]])
async def list_system_settings(
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[list[SystemSettingResponse]]:
    settings = await system_setting_service.list_settings(db, redis)
    return success([SystemSettingResponse(**s) for s in settings])


@router.put("", response_model=APIResponse[SystemSettingResponse])
async def update_system_setting(
    body: SystemSettingUpdate,
    request: Request,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[SystemSettingResponse]:
    setting = await system_setting_service.update_setting(
        db,
        request.app.state.ai_client,
        body.key,
        body.value,
        request_id=request.scope.get("request_id", ""),
        redis=redis,
    )

    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["action"] = "UPDATE"
        activity["resource_type"] = "system_setting"
        activity["message"] = f"admin update system setting {body.key}"

    return success(system_setting_service.to_response(setting))
