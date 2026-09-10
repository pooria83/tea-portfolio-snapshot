from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.models.user import User


class TestLinkGoogleMobile:
    async def test_link_google_mobile_not_configured(self, client: AsyncClient):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "mobile@example.com",
                "username": "mobileuser",
                "password": "StrongPass1!",
            },
        )
        access_token = reg.json()["access_token"]

        response = await client.post(
            "/api/v1/users/me/link/google/mobile",
            json={"id_token": "some-token"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 503
        body = response.json()
        assert body["success"] is False
        assert body["error"]["translation_key"] == "google_not_configured"

    async def test_link_google_mobile_success(self, client: AsyncClient):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "mobile2@example.com",
                "username": "mobileuser2",
                "password": "StrongPass1!",
            },
        )
        access_token = reg.json()["access_token"]

        linked = User(
            id="user-1",
            email="mobile2@example.com",
            username="mobileuser2",
            full_name=None,
            role="seller",
            is_active=True,
            preferred_language="ar",
            google_id="google-id-1",
            created_at=__import__("datetime").datetime.now(),
        )

        with patch(
            "app.api.v1.users.user_service.link_google",
            new=AsyncMock(return_value=linked),
        ):
            response = await client.post(
                "/api/v1/users/me/link/google/mobile",
                json={"id_token": "valid-token"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["has_google"] is True
