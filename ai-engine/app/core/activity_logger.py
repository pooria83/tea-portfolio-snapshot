import asyncio
import json
import os
import time
from collections.abc import MutableMapping
from datetime import UTC, date, datetime
from typing import Any, cast

from loguru import logger
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.logging import request_id_var, user_id_var

SENSITIVE_KEYWORDS: frozenset[str] = frozenset(
    {
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
        "webhook_url",
        "webhook-url",
    }
)

RESOURCE_TYPE_PREFIXES: list[tuple[str, str]] = [
    ("/generate-description", "description"),
    ("/chat", "chat"),
    ("/embed-product", "embed"),
    ("/config", "config"),
    ("/health", "health"),
]

ACTIONS_BY_METHOD: dict[str, str] = {
    "GET": "READ",
    "POST": "CREATE",
    "PUT": "UPDATE",
    "PATCH": "UPDATE",
    "DELETE": "DELETE",
}


def infer_resource_type(path: str) -> str | None:
    for prefix, rtype in RESOURCE_TYPE_PREFIXES:
        if path.startswith(prefix):
            return rtype
    return None


def _redact_dict(obj: object) -> object:
    if isinstance(obj, dict):
        return {k: _redact_dict(v) if k.lower() not in SENSITIVE_KEYWORDS else "***REDACTED***" for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_dict(item) for item in obj]
    return obj


def _pii_filter(body: str) -> str:
    if not body:
        return body
    body_lower = body.lower()
    if any(word in body_lower for word in SENSITIVE_KEYWORDS):
        try:
            parsed = json.loads(body)
            return json.dumps(_redact_dict(parsed), ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            return '"***REDACTED***"'
    return body


def _jsonl_path(log_dir: str) -> str:
    today = date.today().isoformat()
    return os.path.join(log_dir, f"ai_engine_activity_{today}.jsonl")


def _sync_write(path: str, line: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True, mode=0o700)
    with open(path, "a", encoding="utf-8", opener=_restricted_opener) as f:
        f.write(line)


def _restricted_opener(path: str, flags: int) -> int:
    return os.open(path, flags, 0o600)


async def _write_jsonl(log_dir: str, entry: dict[str, object]) -> None:
    try:
        path = _jsonl_path(log_dir)
        line = json.dumps(entry, ensure_ascii=False, default=str) + "\n"
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _sync_write, path, line)
    except Exception:
        logger.opt(exception=True).warning("jsonl_write_failed")


class ActivityLoggerMiddleware:
    def __init__(self, app: ASGIApp, log_dir: str) -> None:
        self.app = app
        self.log_dir = log_dir

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        body_chunks: list[bytes] = []
        response_body_chunks: list[bytes] = []
        status_code: int | None = None
        logged: bool = False

        async def receive_with_capture() -> MutableMapping[str, Any]:
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                if chunk:
                    body_chunks.append(chunk)
            return message

        async def send_with_capture(message: MutableMapping[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if chunk:
                    response_body_chunks.append(chunk)
            await send(message)

        try:
            await self.app(scope, receive_with_capture, send_with_capture)
        except BaseException:
            if status_code is None:
                status_code = 500
            logged = True
            raise
        finally:
            if status_code is None:
                logged = True

        if logged:
            return

        assert status_code is not None

        duration = time.monotonic() - start
        duration_ms = round(duration * 1000)

        method: str = scope.get("method", "")
        path: str = scope.get("path", "")
        uid: str = user_id_var.get() or ""
        rid: str = request_id_var.get() or ""
        raw_action = scope.get("_activity", {}).get("action")
        action: str = str(raw_action) if raw_action else ACTIONS_BY_METHOD.get(method, "UNKNOWN")
        raw_resource_type = scope.get("_activity", {}).get("resource_type")
        resource_type: str | None = str(raw_resource_type) if raw_resource_type else infer_resource_type(path)

        req_body_raw = b"".join(body_chunks).decode(errors="replace")
        res_body_raw = b"".join(response_body_chunks).decode(errors="replace")
        req_body: str | None = _pii_filter(req_body_raw) or None
        res_body: str | None = _pii_filter(res_body_raw) or None

        error_code: str | None = None
        error_message: str | None = None
        if status_code >= 400:
            raw_activity = scope.get("_activity", {})
            error_code = str(raw_activity.get("error_code", "")) or "UNKNOWN" if status_code >= 400 else None
            error_message = str(raw_activity.get("error_message", "")) or res_body if status_code >= 400 else None

        headers_dict = dict(scope.get("headers", []))
        raw_ip = headers_dict.get(b"x-forwarded-for", b"")
        if raw_ip:
            ip_str = raw_ip.decode().split(",")[0].strip()
        else:
            client = scope.get("client")
            ip_str = str(client[0]) if isinstance(client, (list, tuple)) and len(client) > 0 else ""
        ip_address: str | None = ip_str or None
        raw_ua = headers_dict.get(b"user-agent", b"")
        user_agent: str | None = raw_ua.decode() if raw_ua else None

        entry: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": rid or None,
            "user_id": uid or None,
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "resource_type": resource_type,
            "action": action,
            "error_code": error_code if status_code >= 400 else None,
            "error_message": error_message if status_code >= 400 else None,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        if status_code >= 400:
            entry["request_body"] = cast(str, req_body)
            entry["response_body"] = cast(str, res_body)

        asyncio.ensure_future(_write_jsonl(self.log_dir, entry))
