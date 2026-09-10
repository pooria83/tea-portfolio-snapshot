import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_request_validation_error_returns_unified_envelope(client: AsyncClient):
    response = await client.post("/api/v1/auth/send-otp", json={"phone": "123"})
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["translation_key"] == "validation_error"
    assert body["error"]["details"]["errors"]
    first = body["error"]["details"]["errors"][0]
    assert "loc" in first and "msg" in first and "type" in first
