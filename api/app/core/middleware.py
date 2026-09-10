import asyncio
import uuid
from collections.abc import MutableMapping
from typing import Any

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.asgi import wrap_send
from app.core.config import settings
from app.core.error_codes import E
from app.core.logging import log_source_var, request_id_var, user_id_var
from app.core.response import error_response

_SECURITY_HEADERS = {
    "strict-transport-security": "max-age=31536000; includeSubDomains",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "x-xss-protection": "0",
    "referrer-policy": "strict-origin-when-cross-origin",
    "content-security-policy": "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    "permissions-policy": "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "cross-origin",
}


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, debug: bool = False) -> None:
        self.app = app
        self.headers = {
            **_SECURITY_HEADERS,
            "content-security-policy": (
                "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
                if not debug
                else (
                    "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none';"
                    " script-src 'self' 'unsafe-inline' cdn.jsdelivr.net;"
                    " style-src 'self' 'unsafe-inline' cdn.jsdelivr.net;"
                    " img-src 'self' data:; font-src 'self' data:; connect-src 'self'"
                )
            ),
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                original_headers = message.get("headers", [])
                extra = [(k.encode(), v.encode()) for k, v in self.headers.items()]
                message["headers"] = [*original_headers, *extra]
            await send(message)

        await self.app(scope, receive, send_with_headers)


class RequestIDMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers_list: list[tuple[bytes, bytes]] = scope.get("headers", [])
        headers: dict[bytes, bytes] = dict(headers_list)
        request_id = headers.get(b"x-request-id", b"").decode() or str(uuid.uuid4())

        request_id_var.set(request_id)
        user_id_var.set("")
        log_source_var.set("anonymous")
        scope["request_id"] = request_id

        def on_start(message: MutableMapping[str, Any]) -> None:
            original_headers = message.get("headers", [])
            message["headers"] = [
                *original_headers,
                (b"x-request-id", request_id.encode()),
            ]

        await self.app(scope, receive, wrap_send(send, on_start))


class ShutdownCheckMiddleware:
    def __init__(self, app: ASGIApp, shutdown_event: asyncio.Event) -> None:
        self.app = app
        self.shutdown_event = shutdown_event

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if self.shutdown_event.is_set():
            response = error_response(
                request=Request(scope),
                status_code=503,
                code="SERVICE_UNAVAILABLE",
                message="Server shutting down",
                translation_key=E.SERVER_SHUTTING_DOWN,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


class RestrictDocsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if not settings.debug:
            path: str = scope.get("path", "")
            if path in ("/docs", "/redoc", "/openapi.json"):
                response = error_response(
                    request=Request(scope),
                    status_code=404,
                    code="NOT_FOUND",
                    message="Not found",
                    translation_key=E.NOT_FOUND,
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
