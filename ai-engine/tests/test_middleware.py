import pytest
from starlette.types import Receive, Scope, Send

from app.core.logging import log_source_var, request_id_var, user_id_var
from app.core.middleware import LogContextMiddleware


@pytest.mark.asyncio
async def test_log_context_middleware_sets_headers():
    request_id_var.set("")
    user_id_var.set("")
    log_source_var.set("")

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        pass

    middleware = LogContextMiddleware(app)  # type: ignore[arg-type]

    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/health",
        "headers": [
            (b"x-request-id", b"fwd-req-1"),
            (b"x-user-id", b"fwd-user-1"),
        ],
    }

    async def receive() -> dict:
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        pass

    await middleware(scope, receive, send)  # type: ignore[arg-type]

    assert request_id_var.get() == "fwd-req-1"
    assert user_id_var.get() == "fwd-user-1"
    assert log_source_var.get() == "authenticated"
    assert scope["state"]["request_id"] == "fwd-req-1"
    assert scope["state"]["user_id"] == "fwd-user-1"


@pytest.mark.asyncio
async def test_log_context_middleware_no_headers():
    request_id_var.set("")
    user_id_var.set("")
    log_source_var.set("")

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        pass

    middleware = LogContextMiddleware(app)  # type: ignore[arg-type]

    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/health",
        "headers": [],
    }

    async def receive() -> dict:
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        pass

    await middleware(scope, receive, send)  # type: ignore[arg-type]

    assert request_id_var.get().startswith("req-")
    assert user_id_var.get().startswith("anon-")
    assert log_source_var.get() == ""
    assert scope["state"]["request_id"].startswith("req-")
    assert scope["state"]["user_id"].startswith("anon-")


@pytest.mark.asyncio
async def test_log_context_middleware_skips_non_http():
    request_id_var.set("existing")
    user_id_var.set("existing")
    log_source_var.set("existing")

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        pass

    middleware = LogContextMiddleware(app)  # type: ignore[arg-type]

    scope: Scope = {
        "type": "websocket",
        "path": "/ws",
    }

    async def receive() -> dict:
        return {"type": "websocket.receive"}

    async def send(message: dict) -> None:
        pass

    await middleware(scope, receive, send)  # type: ignore[arg-type]

    assert request_id_var.get() == "existing"
    assert user_id_var.get() == "existing"
    assert log_source_var.get() == "existing"


@pytest.mark.asyncio
async def test_engine_auth_middleware_rejects_missing_key():
    from app.core.auth import EngineAuthMiddleware

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        pass

    middleware = EngineAuthMiddleware(app, secret="secret-key")  # type: ignore[arg-type]

    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    scope: Scope = {
        "type": "http",
        "method": "POST",
        "path": "/chat",
        "headers": [],
    }

    async def receive() -> dict:
        return {"type": "http.disconnect"}

    await middleware(scope, receive, send)  # type: ignore[arg-type]

    assert sent and sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 401


@pytest.mark.asyncio
async def test_engine_auth_middleware_rejects_wrong_key():
    from app.core.auth import EngineAuthMiddleware

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        pass

    middleware = EngineAuthMiddleware(app, secret="secret-key")  # type: ignore[arg-type]

    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    scope: Scope = {
        "type": "http",
        "method": "POST",
        "path": "/chat",
        "headers": [(b"x-api-key", b"wrong")],
    }

    async def receive() -> dict:
        return {"type": "http.disconnect"}

    await middleware(scope, receive, send)  # type: ignore[arg-type]

    assert sent and sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 401


@pytest.mark.asyncio
async def test_engine_auth_middleware_passes_with_valid_key():
    from app.core.auth import EngineAuthMiddleware

    calls: list[Scope] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        calls.append(scope)

    middleware = EngineAuthMiddleware(app, secret="secret-key")  # type: ignore[arg-type]

    async def send(message: dict) -> None:
        pass

    scope: Scope = {
        "type": "http",
        "method": "POST",
        "path": "/chat",
        "headers": [(b"x-api-key", b"secret-key")],
    }

    async def receive() -> dict:
        return {"type": "http.disconnect"}

    await middleware(scope, receive, send)  # type: ignore[arg-type]

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_engine_auth_middleware_exempts_health():
    from app.core.auth import EngineAuthMiddleware

    calls: list[Scope] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        calls.append(scope)

    middleware = EngineAuthMiddleware(app, secret="secret-key")  # type: ignore[arg-type]

    async def send(message: dict) -> None:
        pass

    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/health",
        "headers": [],
    }

    async def receive() -> dict:
        return {"type": "http.disconnect"}

    await middleware(scope, receive, send)  # type: ignore[arg-type]

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_engine_auth_middleware_disabled_when_secret_empty():
    from app.core.auth import EngineAuthMiddleware

    calls: list[Scope] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        calls.append(scope)

    middleware = EngineAuthMiddleware(app, secret="")  # type: ignore[arg-type]

    async def send(message: dict) -> None:
        pass

    scope: Scope = {
        "type": "http",
        "method": "POST",
        "path": "/chat",
        "headers": [],
    }

    async def receive() -> dict:
        return {"type": "http.disconnect"}

    await middleware(scope, receive, send)  # type: ignore[arg-type]

    assert len(calls) == 1
