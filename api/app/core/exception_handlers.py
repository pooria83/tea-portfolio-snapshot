from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy.exc import MissingGreenlet

from app.core.error_codes import E
from app.core.exceptions import AppError, AuthenticationError
from app.core.response import error_response


def _get_activity(request: Request) -> dict[str, object] | None:
    scope = getattr(request, "scope", None)
    if isinstance(scope, dict):
        activity = scope.get("_activity")
        if isinstance(activity, dict):
            return activity
    return None


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "app_error",
        code=exc.code,
        detail=exc.detail,
        status=exc.status_code,
        path=request.url.path,
        translation_key=exc.translation_key,
        extra=exc.extra,
    )
    activity = _get_activity(request)
    if activity is not None:
        activity["error_code"] = exc.code
        activity["translation_key"] = exc.translation_key
        activity["error_message"] = exc.detail
    return error_response(
        request=request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.detail,
        translation_key=exc.translation_key,
        details=exc.extra if exc.extra else None,
    )


async def auth_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
    activity = _get_activity(request)
    if activity is not None:
        activity["error_code"] = exc.code
        activity["translation_key"] = exc.translation_key
        activity["error_message"] = exc.detail
    return error_response(
        request=request,
        status_code=401,
        code="UNAUTHORIZED",
        message=exc.detail,
        translation_key=exc.translation_key,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {
            "loc": list(err.get("loc", [])),
            "msg": err.get("msg", "Invalid value"),
            "type": err.get("type", "value_error"),
        }
        for err in exc.errors()
    ]
    logger.warning(
        "validation_error",
        path=request.url.path,
        status=422,
        errors=errors,
    )
    activity = _get_activity(request)
    if activity is not None:
        activity["error_code"] = "VALIDATION_ERROR"
        activity["translation_key"] = E.VALIDATION_ERROR
        activity["error_message"] = "Validation failed"
    return error_response(
        request=request,
        status_code=422,
        code="VALIDATION_ERROR",
        message="Validation failed",
        translation_key=E.VALIDATION_ERROR,
        details={"errors": errors},
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    error_code = "INTERNAL_ERROR"
    translation_key: str | None = "internal_error"
    error_message = "Internal server error"
    if isinstance(exc, MissingGreenlet):
        logger.error(
            "async_lazy_load_violation",
            path=request.url.path,
            detail="Lazy loading attempted outside async greenlet context. Add joinedload/selectinload to the query.",
            exc_info=exc,
        )
        error_code = "LAZY_LOAD_VIOLATION"
        translation_key = None
        error_message = str(exc)
    else:
        logger.error("unhandled_exception", path=request.url.path, exc_info=exc)
        error_message = str(exc) or "Internal server error"
    activity = _get_activity(request)
    if activity is not None:
        activity["error_code"] = error_code
        activity["translation_key"] = translation_key
        activity["error_message"] = error_message
    return error_response(
        request=request,
        status_code=500,
        code=error_code,
        message="Internal server error",
        translation_key=translation_key,
    )
