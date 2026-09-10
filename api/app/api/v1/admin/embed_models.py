from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_admin_user
from app.core.response import APIResponse, success
from app.models.user import User
from app.repositories.embedding import EmbedModelRepository
from app.schemas.embed_model import EmbedModelResponse

router = APIRouter(prefix="/admin/embed-models", tags=["admin-embed-models"])


@router.get("", response_model=APIResponse[list[EmbedModelResponse]])
async def list_embed_models(
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[EmbedModelResponse]]:
    models = await EmbedModelRepository(db).list_active()
    return success([EmbedModelResponse.model_validate(m) for m in models])
