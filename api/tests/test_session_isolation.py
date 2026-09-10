from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.main import app


def _make_bad_override(bad_session):
    async def override_bad_db():
        yield bad_session

    return override_bad_db


@pytest.mark.asyncio
async def test_session_isolation_after_db_error(client: AsyncClient):
    """A DB error in one request must not prevent the next request from succeeding."""

    bad_session = AsyncMock(spec=AsyncSession)
    bad_session.execute = AsyncMock(side_effect=Exception("DB failure"))

    app.dependency_overrides[get_db] = _make_bad_override(bad_session)

    resp1 = await client.get("/api/v1/ready")
    app.dependency_overrides.pop(get_db, None)

    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["database"] == "error"

    resp2 = await client.get("/api/v1/health")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "ok"


@pytest.mark.asyncio
async def test_multiple_consecutive_db_failures_recover(client: AsyncClient):
    """Multiple consecutive DB failures must not accumulate state."""

    for _ in range(3):
        bad_session = AsyncMock(spec=AsyncSession)
        bad_session.execute = AsyncMock(side_effect=Exception("DB failure"))

        app.dependency_overrides[get_db] = _make_bad_override(bad_session)

        resp = await client.get("/api/v1/ready")
        app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        assert resp.json()["database"] == "error"

    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
