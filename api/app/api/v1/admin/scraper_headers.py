from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_admin_user
from app.core.error_codes import E
from app.core.response import APIResponse, error_response, success
from app.models.user import User
from app.schemas.scraper_header import ScraperHeaderClearResponse, ScraperHeaderResponse, ScraperHeaderUpdate
from app.services import scraper_header_service

router = APIRouter(prefix="/admin/scraper-headers", tags=["admin-scraper-headers"])


@router.get("", response_model=APIResponse[list[ScraperHeaderResponse]])
async def list_scraper_headers(
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[ScraperHeaderResponse]]:
    headers = await scraper_header_service.list_headers(db)
    return success([ScraperHeaderResponse.model_validate(h, from_attributes=True) for h in headers])


@router.get("/{name}", response_model=APIResponse[ScraperHeaderResponse])
async def get_scraper_header(
    name: str,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ScraperHeaderResponse]:
    header = await scraper_header_service.get_header(db, name)
    return success(ScraperHeaderResponse.model_validate(header, from_attributes=True))


@router.put("/{name}", response_model=APIResponse[ScraperHeaderResponse])
async def upsert_scraper_header(
    name: str,
    body: ScraperHeaderUpdate,
    request: Request,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ScraperHeaderResponse] | JSONResponse:
    try:
        header = await scraper_header_service.upsert_header(db, name, body.header)
    except ValueError as exc:
        return error_response(
            request=request,
            status_code=422,
            code="scraper_header_invalid",
            message=str(exc),
            translation_key=E.SCRAPER_HEADER_INVALID,
        )

    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["action"] = "UPDATE"
        activity["resource_type"] = "scraper_header"
        activity["message"] = f"admin update scraper header for {name}"

    return success(ScraperHeaderResponse.model_validate(header, from_attributes=True))


@router.delete("/{name}", response_model=APIResponse[ScraperHeaderClearResponse])
async def clear_scraper_header(
    name: str,
    request: Request,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ScraperHeaderClearResponse]:
    header = await scraper_header_service.clear_header(db, name)

    activity = request.scope.get("_activity")
    if isinstance(activity, dict):
        activity["action"] = "DELETE"
        activity["resource_type"] = "scraper_header"
        activity["message"] = f"admin clear scraper header for {name}"

    return success(
        ScraperHeaderClearResponse(
            name=header.name,
            header=header.header,
            status=header.status,
        )
    )
