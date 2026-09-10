"""Engine API-key auth middleware.

The backend API (product-graph-api) calls the AI Engine with an
``X-API-Key`` header matching its own ``settings.api_key``. This middleware
verifies that header against the engine's ``engine_api_key`` setting using a
constant-time compare. When the setting is empty the guard is disabled so
local development can run without a key (mirrors the API's webhook-secret
pattern). The ``/health`` endpoint is exempt so Docker HEALTHCHECK works.
"""

from hmac import compare_digest

from loguru import logger
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

ENGINE_API_KEY_HEADER = "X-API-Key"

_EXEMPT_PATHS = {"/health"}


class EngineAuthMiddleware:
    def __init__(self, app: ASGIApp, secret: str = "") -> None:
        self.app = app
        self.secret = secret

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in _EXEMPT_PATHS or not self.secret:
            await self.app(scope, receive, send)
            return
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        candidate = headers.get(b"x-api-key", b"").decode()
        if not candidate or not compare_digest(candidate, self.secret):
            logger.warning("ENGINE_AUTH_REJECTED path={}", scope.get("path"))
            response = JSONResponse({"detail": "Invalid or missing API key"}, status_code=401)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
