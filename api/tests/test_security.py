import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import get_db
from app.main import app


def _expected_csp() -> str:
    if settings.debug:
        return (
            "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none';"
            " script-src 'self' 'unsafe-inline' cdn.jsdelivr.net;"
            " style-src 'self' 'unsafe-inline' cdn.jsdelivr.net;"
            " img-src 'self' data:; font-src 'self' data:; connect-src 'self'"
        )
    return "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"


@pytest.mark.asyncio
async def test_security_headers(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/health")
    headers = {k.lower(): v for k, v in resp.headers.items()}
    assert headers.get("strict-transport-security") == "max-age=31536000; includeSubDomains"
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert headers.get("content-security-policy") == _expected_csp()
    assert headers.get("permissions-policy") == "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
    assert headers.get("cross-origin-resource-policy") == "cross-origin"
    assert headers.get("cross-origin-opener-policy") == "same-origin"
    app.dependency_overrides.clear()
