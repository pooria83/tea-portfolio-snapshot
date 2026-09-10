from typing import Any

from fastapi.openapi.utils import get_openapi

from app.core.config import settings


def custom_openapi(app: Any) -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema  # type: ignore[no-any-return]

    schema = get_openapi(
        title=f"{settings.app_name} API",
        version="0.1.0",
        description="AI-powered product search and discovery API. Supports JWT authentication for users and X-API-Key for service-to-service communication.",
        routes=list(app.routes) + list(app.webhooks.routes),
    )
    schema["servers"] = [
        {"url": "/", "description": "Local development"},
    ]
    schema["tags"] = [
        {"name": "health", "description": "Service health and readiness checks"},
        {"name": "auth", "description": "User registration, login, token refresh"},
        {"name": "users", "description": "User profile management"},
        {"name": "products", "description": "Product CRUD operations"},
        {"name": "search", "description": "AI-powered product search"},
        {"name": "chat", "description": "Real-time WebSocket chat"},
    ]
    app.openapi_schema = schema
    return app.openapi_schema  # type: ignore[no-any-return]
