from httpx import AsyncClient


class TestUserMe:
    async def test_get_me_unauthenticated(self, client: AsyncClient):
        response = await client.get("/api/v1/users/me")
        assert response.status_code == 401

    async def test_get_me_authenticated(self, client: AsyncClient, auth_headers, test_user):
        response = await client.get("/api/v1/users/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["data"]["email"] == test_user.email

    async def test_update_me(self, client: AsyncClient, auth_headers):
        response = await client.patch(
            "/api/v1/users/me",
            json={"full_name": "Updated Name"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["data"]["full_name"] == "Updated Name"


class TestUserAdmin:
    async def test_get_user_as_admin(self, client: AsyncClient, admin_headers, test_user):
        response = await client.get(f"/api/v1/users/{test_user.id}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["email"] == test_user.email

    async def test_get_user_as_non_admin(self, client: AsyncClient, auth_headers, test_user):
        response = await client.get(f"/api/v1/users/{test_user.id}", headers=auth_headers)
        assert response.status_code == 403

    async def test_get_user_not_found(self, client: AsyncClient, admin_headers):
        response = await client.get("/api/v1/users/non-existent", headers=admin_headers)
        assert response.status_code == 404
