from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_ready_db_failure(client: AsyncClient):
    from sqlalchemy.ext.asyncio import AsyncSession

    bad_session = AsyncMock(spec=AsyncSession)
    bad_session.execute = AsyncMock(side_effect=Exception("DB down"))

    async def override_db():
        yield bad_session

    from app.core.database import get_db

    app.dependency_overrides[get_db] = override_db

    resp = await client.get("/api/v1/ready")
    data = resp.json()
    assert data["database"] == "error"
    assert data["status"] == "degraded"
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_ready_redis_failure(client: AsyncClient):
    app.state.redis.ping = AsyncMock(side_effect=Exception("Redis down"))

    resp = await client.get("/api/v1/ready")
    data = resp.json()
    assert data["redis"] == "error"
    assert data["status"] == "degraded"

    app.state.redis.ping = AsyncMock(return_value=True)


@pytest.mark.asyncio
async def test_ready_broker_failure(client: AsyncClient):
    app.state.broker.is_connected = lambda: False

    resp = await client.get("/api/v1/ready")
    data = resp.json()
    assert data["rabbitmq"] == "error"
    assert data["status"] == "degraded"

    app.state.broker.is_connected = lambda: True


@pytest.mark.asyncio
async def test_ready_broker_exception(client: AsyncClient):
    app.state.broker = None

    resp = await client.get("/api/v1/ready")
    data = resp.json()
    assert data["rabbitmq"] == "error"
    assert data["status"] == "degraded"

    from app.core.broker import Broker

    app.state.broker = AsyncMock(spec=Broker)
    app.state.broker.is_connected = lambda: True


@pytest.mark.asyncio
async def test_ready_ai_exception(client: AsyncClient):
    app.state.ai_client.health = AsyncMock(side_effect=Exception("AI down"))

    resp = await client.get("/api/v1/ready")
    data = resp.json()
    assert data["ai_engine"] == "error"
    assert data["status"] == "degraded"

    app.state.ai_client.health = AsyncMock(return_value=True)


@pytest.mark.asyncio
async def test_metrics_endpoint(client: AsyncClient):
    with patch("app.api.v1.health.settings.debug", True):
        resp = await client.get("/api/v1/metrics")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_metrics_disabled_in_production(client: AsyncClient):
    with patch("app.api.v1.health.settings.debug", False):
        resp = await client.get("/api/v1/metrics")
        assert resp.status_code == 404
