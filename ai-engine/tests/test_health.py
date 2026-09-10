from __future__ import annotations

from httpx import AsyncClient


class TestHealth:
    async def test_health_ok(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"status": "ok"}
