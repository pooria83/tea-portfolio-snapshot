from dataclasses import dataclass, field
from typing import Any


@dataclass(kw_only=True)
class AppError(Exception):
    detail: str
    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    translation_key: str | None = None
    headers: dict[str, str] | None = None
    extra: dict[str, Any] | None = field(default_factory=dict)


class NotFoundError(AppError):
    def __init__(self, detail: str = "Resource not found", **kwargs: Any) -> None:
        super().__init__(detail=detail, code="NOT_FOUND", status_code=404, **kwargs)


class AuthenticationError(AppError):
    def __init__(self, detail: str = "Not authenticated", **kwargs: Any) -> None:
        super().__init__(detail=detail, code="AUTHENTICATION_ERROR", status_code=401, **kwargs)


class AuthorizationError(AppError):
    def __init__(self, detail: str = "Forbidden", **kwargs: Any) -> None:
        super().__init__(detail=detail, code="FORBIDDEN", status_code=403, **kwargs)


class ConflictError(AppError):
    def __init__(self, detail: str = "Resource already exists", **kwargs: Any) -> None:
        super().__init__(detail=detail, code="CONFLICT", status_code=409, **kwargs)


class ValidationError(AppError):
    def __init__(self, detail: str = "Validation failed", **kwargs: Any) -> None:
        super().__init__(detail=detail, code="VALIDATION_ERROR", status_code=422, **kwargs)


class ServiceUnavailableError(AppError):
    def __init__(self, detail: str = "Service unavailable", **kwargs: Any) -> None:
        super().__init__(detail=detail, code="SERVICE_UNAVAILABLE", status_code=503, **kwargs)
