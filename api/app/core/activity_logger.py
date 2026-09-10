import asyncio
import json
import time
from collections.abc import MutableMapping
from typing import Any, cast

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.logging import user_id_var
from app.models.activity_log import ActivityLog
from app.repositories.misc import ActivityLogRepository

BODY_CAPTURE_LIMIT = 64 * 1024

_activity_tasks: set[asyncio.Task[None]] = set()


def _spawn_activity_task(coro: Any) -> None:
    task = asyncio.ensure_future(coro)
    _activity_tasks.add(task)
    task.add_done_callback(_activity_tasks.discard)


async def drain_activity_tasks(timeout: float = 2.0) -> None:
    tasks = list(_activity_tasks)
    if not tasks:
        return
    done, pending = await asyncio.wait(tasks, timeout=timeout)
    for task in pending:
        task.cancel()


def _append_capped(chunks: list[bytes], total: int, chunk: bytes) -> int:
    if not chunk or total >= BODY_CAPTURE_LIMIT:
        return total
    take = min(len(chunk), BODY_CAPTURE_LIMIT - total)
    chunks.append(chunk[:take])
    return total + take


ACTIONS_BY_METHOD: dict[str, str] = {
    "GET": "READ",
    "POST": "CREATE",
    "PUT": "UPDATE",
    "PATCH": "UPDATE",
    "DELETE": "DELETE",
}

RESOURCE_TYPE_PREFIXES: list[tuple[str, str]] = [
    ("/api/v1/admin/llm/prompt-templates", "prompt_template"),
    ("/api/v1/admin/llm", "llm_config"),
    ("/api/v1/admin/system-settings", "system_setting"),
    ("/api/v1/admin/cron", "cron"),
    ("/api/v1/admin", "admin"),
    ("/api/v1/stores/", "store"),
    ("/api/v1/products", "product"),
    ("/api/v1/users", "user"),
    ("/api/v1/auth", "auth"),
    ("/api/v1/files", "file"),
    ("/api/v1/webhook", "webhook"),
]


def infer_resource_type(path: str) -> str | None:
    for prefix, rtype in RESOURCE_TYPE_PREFIXES:
        if path.startswith(prefix):
            return rtype
    return None


SENSITIVE_KEYWORDS: tuple[str, ...] = (
    "password",
    "token",
    "secret",
    "authorization",
    "api_key",
    "api-key",
    "apikey",
    "jwt",
    "refresh_token",
    "access_token",
)


def _pii_filter(body: str) -> str:
    if not body:
        return body
    body_lower = body.lower()
    for word in SENSITIVE_KEYWORDS:
        if word in body_lower:
            try:
                parsed = json.loads(body)
                return json.dumps(_redact_dict(parsed), ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                return f'"{{...redacted {word}...}}"'
    return body


def _redact_dict(obj: object) -> object:
    if isinstance(obj, dict):
        return {k: _redact_dict(v) if k.lower() not in SENSITIVE_KEYWORDS else "***REDACTED***" for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_dict(item) for item in obj]
    return obj


async def log_activity(
    session_factory: async_sessionmaker[AsyncSession],
    actor_type: str,
    action: str,
    status_code: int,
    actor_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    message: str | None = None,
    details: dict[str, object] | None = None,
    error_code: str | None = None,
    translation_key: str | None = None,
    error_message: str | None = None,
    request_body: str | None = None,
    response_body: str | None = None,
    ip_address: str | None = None,
    request_id: str | None = None,
    user_agent: str | None = None,
    duration_ms: int | None = None,
    path: str | None = None,
    method: str | None = None,
) -> None:
    log_level = "INFO" if status_code < 400 else ("WARNING" if status_code < 500 else "ERROR")
    logger.opt(depth=1).log(
        log_level,
        "activity_log",
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        message=message,
        details=details,
        status_code=status_code,
        error_code=error_code,
        translation_key=translation_key,
        error_message=error_message,
        ip_address=ip_address,
        request_id=request_id,
        user_agent=user_agent,
        duration_ms=duration_ms,
        path=path,
        method=method,
    )

    try:
        async with session_factory() as db:
            entry = ActivityLog(
                actor_type=actor_type,
                actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                message=message,
                details=details,
                status_code=status_code,
                error_code=error_code,
                translation_key=translation_key,
                error_message=error_message,
                request_body=request_body if status_code >= 400 else None,
                response_body=response_body if status_code >= 400 else None,
                ip_address=ip_address,
                request_id=request_id,
                user_agent=user_agent,
                duration_ms=duration_ms,
                path=path,
                method=method,
            )
            await ActivityLogRepository(db).add(entry)
            await db.commit()
    except Exception:
        logger.opt(exception=True).warning("activity_log_failed")


class ActivityLoggerMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        body_chunks: list[bytes] = []
        response_body_chunks: list[bytes] = []
        body_len = 0
        response_body_len = 0
        status_code: int | None = None
        response_headers: list[tuple[bytes, bytes]] = []
        app_exc: BaseException | None = None
        logged: bool = False

        async def receive_with_capture() -> MutableMapping[str, Any]:
            nonlocal body_len
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                if chunk:
                    body_len = _append_capped(body_chunks, body_len, chunk)
            return message

        async def send_with_capture(message: MutableMapping[str, Any]) -> None:
            nonlocal status_code, response_body_len
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers[:] = message.get("headers", [])
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if chunk:
                    response_body_len = _append_capped(response_body_chunks, response_body_len, chunk)
            await send(message)

        activity: dict[str, object] = {}
        scope["_activity"] = activity

        try:
            await self.app(scope, receive_with_capture, send_with_capture)
        except BaseException as exc:
            app_exc = exc
            if status_code is None:
                status_code = 500
            raise
        finally:
            if app_exc is not None or status_code is None:
                logged = True

        if logged:
            return

        assert status_code is not None

        duration = time.monotonic() - start
        duration_ms = round(duration * 1000)

        method: str = scope.get("method", "")
        path: str = scope.get("path", "")
        uid: str = user_id_var.get() or ""
        actor_type: str = "user" if uid else "system"

        raw_action = activity.get("action")
        action: str = str(raw_action) if raw_action else ACTIONS_BY_METHOD.get(method, "UNKNOWN")

        raw_resource_type = activity.get("resource_type")
        resource_type_str: str | None = str(raw_resource_type) if raw_resource_type else infer_resource_type(path)

        raw_resource_id = activity.get("resource_id")
        resource_id_str: str | None = str(raw_resource_id) if raw_resource_id else None

        raw_message = activity.get("message")
        message_str: str | None = str(raw_message) if raw_message else None

        raw_details = activity.get("details")
        details_dict: dict[str, object] | None = cast(dict[str, object], raw_details) if isinstance(raw_details, dict) else None

        raw_error_code = activity.get("error_code")
        error_code_str: str | None = str(raw_error_code) if raw_error_code else (None if status_code < 400 else "UNKNOWN")

        raw_translation_key = activity.get("translation_key")
        translation_key_str: str | None = str(raw_translation_key) if raw_translation_key else None

        raw_error_message = activity.get("error_message")
        error_message_str: str | None = str(raw_error_message) if raw_error_message else None

        headers_dict = dict(response_headers)
        raw_ip = headers_dict.get(b"x-forwarded-for", b"")
        if raw_ip:
            ip_str = raw_ip.decode().split(",")[0].strip()
        else:
            client = scope.get("client")
            ip_str = str(client[0]) if isinstance(client, (list, tuple)) and len(client) > 0 else ""
        ip_address: str | None = ip_str or None

        raw_ua = headers_dict.get(b"user-agent", b"")
        ua_str: str | None = raw_ua.decode() if raw_ua else None

        raw_rid = headers_dict.get(b"x-request-id", b"")
        rid_str: str | None = raw_rid.decode() if raw_rid else None

        req_body_raw = b"".join(body_chunks).decode(errors="replace")
        res_body_raw = b"".join(response_body_chunks).decode(errors="replace")
        req_body: str | None = _pii_filter(req_body_raw) or None
        res_body: str | None = _pii_filter(res_body_raw) or None

        app_obj = scope.get("app")
        if app_obj is not None:
            session_factory = getattr(app_obj.state, "session_factory", None) if hasattr(app_obj, "state") else None
            if session_factory is not None:
                _spawn_activity_task(
                    log_activity(
                        session_factory=cast(async_sessionmaker[AsyncSession], session_factory),
                        actor_type=actor_type,
                        actor_id=uid or None,
                        action=action,
                        resource_type=resource_type_str,
                        resource_id=resource_id_str,
                        message=message_str,
                        details=details_dict,
                        status_code=status_code,
                        error_code=error_code_str,
                        translation_key=translation_key_str,
                        error_message=error_message_str,
                        request_body=req_body,
                        response_body=res_body,
                        ip_address=ip_address,
                        request_id=rid_str,
                        user_agent=ua_str,
                        duration_ms=duration_ms,
                        path=path,
                        method=method,
                    )
                )
