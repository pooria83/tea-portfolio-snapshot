from fastapi import APIRouter, Depends, Query, Request
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_admin_user
from app.core.redis import get_redis
from app.core.response import APIResponse, success
from app.models.search_eval import SearchEvalQuery
from app.models.user import User
from app.schemas.search_eval import (
    EvalImportResult,
    EvalJudgmentsRequest,
    EvalMetricsResponse,
    EvalQueriesGenerateRequest,
    EvalQueriesImportRequest,
    EvalQueryItem,
    EvalQueryListResponse,
    EvalQueryUpdate,
    EvalSearchRequest,
    EvalSearchResponse,
)
from app.services import search_eval_service

router = APIRouter(prefix="/admin/search-eval", tags=["admin-search-eval"])


def _to_item(q: SearchEvalQuery) -> EvalQueryItem:
    return EvalQueryItem(
        id=q.id,
        text=q.text,
        locale=q.locale,
        source=q.source,  # type: ignore[arg-type]
        status=q.status,  # type: ignore[arg-type]
        rewritten_query=q.rewritten_query,
        filters=q.filters,
        created_by=q.created_by,
        created_at=q.created_at,
        updated_at=q.updated_at,
    )


@router.post("/queries/generate", response_model=APIResponse[list[EvalQueryItem]])
async def generate_queries(
    body: EvalQueriesGenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
    _user: User = Depends(get_admin_user),
) -> APIResponse[list[EvalQueryItem]]:
    created = await search_eval_service.generate_queries(
        db,
        request.app.state.ai_client,
        body.count,
        body.locales,
        _user.id,
        request_id=request.scope.get("request_id", ""),
        redis=redis,
    )

    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["action"] = "CREATE"
        activity["resource_type"] = "search_eval_query"
        activity["message"] = f"generated {len(created)} eval queries from LLM"

    return success([_to_item(q) for q in created])


@router.post("/queries/import", response_model=APIResponse[EvalImportResult])
async def import_queries(
    body: EvalQueriesImportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
    _user: User = Depends(get_admin_user),
) -> APIResponse[EvalImportResult]:
    created, skipped, judgments_created = await search_eval_service.import_queries(db, body.queries, _user.id, redis=redis)

    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["action"] = "CREATE"
        activity["resource_type"] = "search_eval_query"
        activity["message"] = f"imported {created} eval queries ({judgments_created} judgments), {skipped} skipped"

    return success(EvalImportResult(created=created, skipped=skipped, judgments_created=judgments_created))


@router.get("/queries", response_model=APIResponse[EvalQueryListResponse])
async def list_queries(
    locale: str | None = Query(default=None, max_length=5),
    source: str | None = Query(default=None, max_length=10),
    status: str | None = Query(default=None, max_length=12),
    q: str | None = Query(default=None, max_length=200, description="Text search"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_admin_user),
) -> APIResponse[EvalQueryListResponse]:
    items, total = await search_eval_service.list_queries(db, locale, source, status, q, skip, limit)

    return success(
        EvalQueryListResponse(items=[_to_item(q) for q in items], total=total, skip=skip, limit=limit),
        meta={"locale": locale, "source": source, "status": status},
    )


@router.patch("/queries/{query_id}", response_model=APIResponse[EvalQueryItem])
async def update_query(
    query_id: str,
    body: EvalQueryUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
    _user: User = Depends(get_admin_user),
) -> APIResponse[EvalQueryItem]:
    query = await search_eval_service.update_query(db, query_id, body.status, body.rewritten_query, body.filters, redis=redis)

    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["action"] = "UPDATE"
        activity["resource_type"] = "search_eval_query"
        activity["resource_id"] = query_id
        activity["message"] = f"updated search eval query (status={query.status})"

    return success(_to_item(query))


@router.put("/queries/{query_id}/judgments", response_model=APIResponse[EvalQueryItem])
async def save_judgments(
    query_id: str,
    body: EvalJudgmentsRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
    _user: User = Depends(get_admin_user),
) -> APIResponse[EvalQueryItem]:
    query = await search_eval_service.save_judgments(db, query_id, body.judgments, redis=redis)

    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["action"] = "UPDATE"
        activity["resource_type"] = "search_eval_judgment"
        activity["resource_id"] = query_id
        activity["message"] = f"saved {len(body.judgments)} judgments for eval query"

    return success(_to_item(query))


@router.get("/metrics", response_model=APIResponse[EvalMetricsResponse])
async def get_metrics(
    db: AsyncSession = Depends(get_db),
    redis: AsyncRedis = Depends(get_redis),
    _user: User = Depends(get_admin_user),
) -> APIResponse[EvalMetricsResponse]:
    overall, per_locale = await search_eval_service.get_metrics(db, redis)
    return success(EvalMetricsResponse(overall=overall, per_locale=per_locale))


@router.post("/search", response_model=APIResponse[EvalSearchResponse])
async def eval_search(
    body: EvalSearchRequest,
    request: Request,
    _user: User = Depends(get_admin_user),
) -> APIResponse[EvalSearchResponse]:
    response = await search_eval_service.eval_search(
        request.app.state.ai_client,
        body,
        request_id=request.scope.get("request_id", ""),
    )
    return success(response)
