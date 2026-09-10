import json
from unittest.mock import MagicMock

import pytest
from fastapi import Request
from sqlalchemy.exc import MissingGreenlet

from app.core.exception_handlers import global_exception_handler


@pytest.mark.asyncio
async def test_missing_greenlet_returns_lazy_load_violation():
    request = MagicMock(spec=Request)
    request.url.path = "/test"
    request.state = MagicMock()
    request.state.request_id = None

    exc = MissingGreenlet("Lazy load outside async greenlet context")

    response = await global_exception_handler(request, exc)
    body = json.loads(response.body)

    assert response.status_code == 500
    assert body["success"] is False
    assert body["error"]["code"] == "LAZY_LOAD_VIOLATION"
    assert body["error"]["message"] == "Internal server error"


@pytest.mark.asyncio
async def test_generic_exception_returns_internal_error():
    request = MagicMock(spec=Request)
    request.url.path = "/test"
    request.state = MagicMock()
    request.state.request_id = None

    exc = ValueError("Something went wrong")

    response = await global_exception_handler(request, exc)
    body = json.loads(response.body)

    assert response.status_code == 500
    assert body["success"] is False
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert body["error"]["message"] == "Internal server error"


@pytest.mark.asyncio
async def test_app_error_returns_proper_code():
    from app.core.exceptions import AppError

    request = MagicMock(spec=Request)
    request.url.path = "/test"
    request.state = MagicMock()
    request.state.request_id = None

    exc = AppError(status_code=404, code="NOT_FOUND", detail="Item not found")

    response = await global_exception_handler(request, exc)
    body = json.loads(response.body)

    assert response.status_code == 500
    assert body["error"]["code"] == "INTERNAL_ERROR"
