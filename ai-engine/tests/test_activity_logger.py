import asyncio
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from starlette.types import Receive, Scope, Send

from app.core.activity_logger import (
    RESOURCE_TYPE_PREFIXES,
    ActivityLoggerMiddleware,
    _jsonl_path,
    _pii_filter,
    _redact_dict,
    infer_resource_type,
)
from app.core.logging import request_id_var, user_id_var


class TestPiiFilter:
    def test_no_sensitive_data(self) -> None:
        body = '{"name": "red dress", "price": 99.99}'
        assert _pii_filter(body) == body

    def test_redacts_api_key(self) -> None:
        body = '{"api_key": "sk-123456"}'
        result = _pii_filter(body)
        parsed = json.loads(result)
        assert parsed["api_key"] == "***REDACTED***"

    def test_redacts_token(self) -> None:
        body = '{"token": "abc123"}'
        result = _pii_filter(body)
        parsed = json.loads(result)
        assert parsed["token"] == "***REDACTED***"

    def test_redacts_nested(self) -> None:
        body = '{"user": {"password": "s3cret", "name": "test"}}'
        result = _pii_filter(body)
        parsed = json.loads(result)
        assert parsed["user"]["password"] == "***REDACTED***"
        assert parsed["user"]["name"] == "test"

    def test_redacts_webhook_url(self) -> None:
        body = '{"webhook_url": "https://hooks.example.com/secret-path"}'
        result = _pii_filter(body)
        parsed = json.loads(result)
        assert parsed["webhook_url"] == "***REDACTED***"

    def test_non_json_body_with_keyword(self) -> None:
        body = "password=abc123"
        result = _pii_filter(body)
        assert result == '"***REDACTED***"'

    def test_empty_body(self) -> None:
        assert _pii_filter("") == ""

    def test_redact_dict_noop(self) -> None:
        assert _redact_dict("hello") == "hello"
        assert _redact_dict(42) == 42
        assert _redact_dict([1, 2]) == [1, 2]

    def test_redact_dict_list_of_dicts(self) -> None:
        data = [{"api_key": "sk-xxx", "name": "test"}]
        result = _redact_dict(data)
        assert result == [{"api_key": "***REDACTED***", "name": "test"}]


class TestInferResourceType:
    def test_known_prefixes(self) -> None:
        cases: list[tuple[str, str]] = [
            ("/generate-description", "description"),
            ("/chat", "chat"),
            ("/embed-product", "embed"),
            ("/config", "config"),
            ("/health", "health"),
        ]
        for path, expected in cases:
            assert infer_resource_type(path) == expected

    def test_unknown_prefix(self) -> None:
        assert infer_resource_type("/unknown") is None

    def test_each_prefix_mapped(self) -> None:
        for prefix, rtype in RESOURCE_TYPE_PREFIXES:
            assert infer_resource_type(prefix) == rtype


class TestJsonlPath:
    def test_builds_dated_path(self, tmp_path: Path) -> None:
        today = date.today().isoformat()
        path = _jsonl_path(str(tmp_path))
        assert path == os.path.join(str(tmp_path), f"ai_engine_activity_{today}.jsonl")

    def test_respects_log_dir(self, tmp_path: Path) -> None:
        log_dir = str(tmp_path / "logs" / "ai-engine")
        path = _jsonl_path(log_dir)
        assert path.startswith(log_dir)


class TestActivityLoggerMiddleware:
    @pytest.mark.asyncio
    async def test_writes_jsonl_on_success(self, tmp_path: Path) -> None:
        log_dir = str(tmp_path)
        request_id_var.set("test-req-1")
        user_id_var.set("test-user-1")

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            await receive()
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b'{"status": "ok"}'})

        middleware = ActivityLoggerMiddleware(app, log_dir)  # type: ignore[arg-type]

        scope: Scope = {
            "type": "http",
            "method": "POST",
            "path": "/chat",
            "headers": [(b"x-forwarded-for", b"10.0.0.1"), (b"user-agent", b"test-agent")],
        }

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": b'{"query": "red dress"}'}

        async def send(message: dict[str, Any]) -> None:
            pass

        await middleware(scope, receive, send)  # type: ignore[arg-type]
        await asyncio.sleep(0.1)

        today = date.today().isoformat()
        log_file = tmp_path / f"ai_engine_activity_{today}.jsonl"
        assert log_file.exists()

        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["method"] == "POST"
        assert entry["path"] == "/chat"
        assert entry["status_code"] == 200
        assert entry["user_id"] == "test-user-1"
        assert entry["request_id"] == "test-req-1"
        assert entry["resource_type"] == "chat"
        assert entry["action"] == "CREATE"
        assert entry["duration_ms"] >= 0
        assert entry["ip_address"] == "10.0.0.1"
        assert entry["user_agent"] == "test-agent"
        assert entry.get("request_body") is None
        assert entry.get("response_body") is None

    @pytest.mark.asyncio
    async def test_includes_bodies_on_error(self, tmp_path: Path) -> None:
        log_dir = str(tmp_path)
        request_id_var.set("")
        user_id_var.set("")

        body_received: dict[str, Any] = {}

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            nonlocal body_received
            msg = await receive()
            body_received = msg
            await send({"type": "http.response.start", "status": 502})
            await send({"type": "http.response.body", "body": b"Model unavailable"})

        middleware = ActivityLoggerMiddleware(app, log_dir)  # type: ignore[arg-type]

        scope: Scope = {
            "type": "http",
            "method": "POST",
            "path": "/generate-description",
            "headers": [],
        }

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": b'{"model": "unknown"}'}

        async def send(message: dict[str, Any]) -> None:
            pass

        await middleware(scope, receive, send)  # type: ignore[arg-type]
        await asyncio.sleep(0.1)

        assert body_received.get("body") == b'{"model": "unknown"}'

        today = date.today().isoformat()
        log_file = tmp_path / f"ai_engine_activity_{today}.jsonl"
        assert log_file.exists()

        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["status_code"] == 502
        assert entry["error_code"] == "UNKNOWN"
        assert entry["request_body"] is not None
        assert entry["response_body"] is not None

    @pytest.mark.asyncio
    async def test_skips_non_http(self, tmp_path: Path) -> None:
        log_dir = str(tmp_path)

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            await send({"type": "websocket.send", "text": "hello"})

        middleware = ActivityLoggerMiddleware(app, log_dir)  # type: ignore[arg-type]

        scope: Scope = {"type": "websocket", "path": "/ws"}

        async def receive() -> dict[str, Any]:
            return {"type": "websocket.receive"}

        async def send(message: dict[str, Any]) -> None:
            pass

        await middleware(scope, receive, send)  # type: ignore[arg-type]
        await asyncio.sleep(0.1)

        today = date.today().isoformat()
        log_file = tmp_path / f"ai_engine_activity_{today}.jsonl"
        assert not log_file.exists()
