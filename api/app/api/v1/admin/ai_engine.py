from fastapi import APIRouter, Depends, Request
from loguru import logger

from app.ai.client import AIEngineClient
from app.core.deps import get_admin_user
from app.core.error_codes import E
from app.core.exceptions import ServiceUnavailableError
from app.core.response import APIResponse, success
from app.models.user import User
from app.schemas.ai_engine import EmbedTextRequest, EmbedTextResponse

router = APIRouter(prefix="/admin/ai-engine", tags=["admin-ai-engine"])


@router.post("/embed-text", response_model=APIResponse[EmbedTextResponse])
async def embed_text(
    body: EmbedTextRequest,
    request: Request,
    _user: User = Depends(get_admin_user),
) -> APIResponse[EmbedTextResponse]:
    ai_client: AIEngineClient = request.app.state.ai_client
    result = await ai_client.embed_text(body.text, request_id=request.scope.get("request_id", ""))
    if result is None or result.get("status") != "ok":
        logger.warning("AI Engine embed_text returned failure: {}", result)
        raise ServiceUnavailableError("AI Engine embedding failed", translation_key=E.AI_ENGINE_ERROR)

    model_raw = result.get("model")
    dimensions_raw = result.get("dimensions")
    embedding_raw = result.get("embedding")
    response = EmbedTextResponse(
        model=str(model_raw) if isinstance(model_raw, str) else "",
        dimensions=dimensions_raw if isinstance(dimensions_raw, int) else 0,
        embedding=list(embedding_raw) if isinstance(embedding_raw, list) else [],
    )

    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["action"] = "CREATE"
        activity["resource_type"] = "ai_engine"
        activity["message"] = f"admin embed-text test ({len(response.embedding)} dims, model={response.model})"

    return success(response)
