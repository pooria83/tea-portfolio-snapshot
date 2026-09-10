from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_admin_user
from app.core.redis import get_redis
from app.core.response import APIResponse, success
from app.models.user import User
from app.schemas.prompt_template import PromptTemplateResponse, PromptTemplateUpdate
from app.services import prompt_template_service

router = APIRouter(prefix="/admin/llm/prompt-templates", tags=["admin-prompt-templates"])


@router.get("", response_model=APIResponse[PromptTemplateResponse])
async def get_prompt_templates(
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[PromptTemplateResponse]:
    return success(await prompt_template_service.get_prompt_response(db, redis))


@router.put("", response_model=APIResponse[PromptTemplateResponse])
async def update_prompt_templates(
    body: PromptTemplateUpdate,
    request: Request,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
) -> APIResponse[PromptTemplateResponse]:
    response = await prompt_template_service.update_templates(db, body, redis)

    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["action"] = "UPDATE"
        activity["resource_type"] = "prompt_template"
        activity["message"] = "admin update prompt templates"

    return success(response)
