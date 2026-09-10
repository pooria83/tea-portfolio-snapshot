import uuid

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.logging import log_source_var, request_id_var, user_id_var


def _new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


class LogContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers_list: list[tuple[bytes, bytes]] = scope.get("headers", [])
        headers: dict[bytes, bytes] = dict(headers_list)

        rid = headers.get(b"x-request-id", b"").decode() or _new_id("req-")
        uid = headers.get(b"x-user-id", b"").decode() or _new_id("anon-")

        request_id_var.set(rid)
        user_id_var.set(uid)
        if headers.get(b"x-user-id"):
            log_source_var.set("authenticated")

        scope.setdefault("state", {})["request_id"] = rid
        scope.setdefault("state", {})["user_id"] = uid

        await self.app(scope, receive, send)
