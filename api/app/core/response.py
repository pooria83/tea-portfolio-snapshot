from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class PaginationMeta(BaseModel):
    skip: int
    limit: int
    total: int
    has_next: bool
    has_previous: bool


class APIResponse[T](BaseModel):
    success: bool = True
    data: T
    meta: dict[str, Any] | None = None


class APIError(BaseModel):
    code: str
    message: str
    translation_key: str | None = None
    details: dict[str, Any] | None = None
    request_id: str | None = None


class APIErrorResponse(BaseModel):
    success: bool = False
    error: APIError


def success[T](data: T, meta: dict[str, Any] | None = None) -> APIResponse[T]:
    return APIResponse(data=data, meta=meta)


def paginated[T](
    items: list[T],
    total: int,
    skip: int,
    limit: int,
) -> APIResponse[list[T]]:
    return APIResponse(
        data=items,
        meta=PaginationMeta(
            skip=skip,
            limit=limit,
            total=total,
            has_next=(skip + limit) < total,
            has_previous=skip > 0,
        ).model_dump(),
    )


def error_response(
    request: Request | None,
    status_code: int,
    code: str,
    message: str,
    translation_key: str | None = None,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    request_id = getattr(getattr(request, "state", None), "request_id", None) if request else None
    return JSONResponse(
        status_code=status_code,
        content=APIErrorResponse(
            error=APIError(
                code=code,
                message=message,
                translation_key=translation_key,
                details=details,
                request_id=request_id,
            )
        ).model_dump(),
    )
