from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.main import _shutdown_event


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "product-graph-api"
    assert data["environment"] in {"development", "staging", "production"}
    assert isinstance(data["git_sha"], str)
    assert len(data["git_sha"]) > 0
    assert isinstance(data["uptime_seconds"], int)
    assert data["uptime_seconds"] >= 0
    assert isinstance(data["python_version"], str)


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "app" in data
    assert "docs" in data


@pytest.mark.asyncio
async def test_openapi_schema(client: AsyncClient):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert "/webhook/product-sync" in schema["paths"]


@pytest.mark.asyncio
async def test_check_shutdown_middleware_returns_503_when_set(client: AsyncClient):
    _shutdown_event.set()
    response = await client.get("/api/v1/health")
    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert body["error"]["translation_key"] == "server_shutting_down"
    _shutdown_event.clear()


@pytest.mark.asyncio
async def test_docs_disabled_in_production(client: AsyncClient):
    with patch("app.main.settings.debug", False):
        docs_resp = await client.get("/docs")
        assert docs_resp.status_code == 404
        openapi_resp = await client.get("/openapi.json")
        assert openapi_resp.status_code == 404
