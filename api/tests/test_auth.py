from httpx import AsyncClient


class TestRegister:
    async def test_register_success(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "username": "newuser",
                "password": "StrongPass1!",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_register_duplicate_email(self, client: AsyncClient):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "dup@example.com",
                "username": "user1",
                "password": "StrongPass1!",
            },
        )
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "dup@example.com",
                "username": "user2",
                "password": "StrongPass1!",
            },
        )
        assert response.status_code == 409

    async def test_register_duplicate_username(self, client: AsyncClient):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "a@example.com",
                "username": "dupuser",
                "password": "StrongPass1!",
            },
        )
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "b@example.com",
                "username": "dupuser",
                "password": "StrongPass1!",
            },
        )
        assert response.status_code == 409


class TestLogin:
    async def test_login_success(self, client: AsyncClient):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@example.com",
                "username": "loginuser",
                "password": "StrongPass1!",
            },
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "login@example.com",
                "password": "StrongPass1!",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    async def test_login_invalid_email(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nobody@example.com",
                "password": "wrong",
            },
        )
        assert response.status_code == 401

    async def test_login_wrong_password(self, client: AsyncClient):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "wp@example.com",
                "username": "wpuser",
                "password": "StrongPass1!",
            },
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "wp@example.com",
                "password": "WrongPass!",
            },
        )
        assert response.status_code == 401


class TestRefresh:
    async def test_refresh_token(self, client: AsyncClient):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh@example.com",
                "username": "refreshuser",
                "password": "StrongPass1!",
            },
        )
        refresh_token = reg.json()["refresh_token"]
        response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_refresh_invalid_token(self, client: AsyncClient):
        response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid-token"})
        assert response.status_code == 401

    async def test_refresh_revoked(self, client: AsyncClient):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "revoke@example.com",
                "username": "revokeuser",
                "password": "StrongPass1!",
            },
        )
        refresh_token = reg.json()["refresh_token"]
        await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 401

    async def test_refresh_reuse_revokes_all_sessions(self, client: AsyncClient):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "reuse@example.com",
                "username": "reuseuser",
                "password": "StrongPass1!",
            },
        )
        first_token = reg.json()["refresh_token"]
        rotated = await client.post("/api/v1/auth/refresh", json={"refresh_token": first_token})
        assert rotated.status_code == 200
        second_token = rotated.json()["refresh_token"]

        reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": first_token})
        assert reused.status_code == 401

        stale = await client.post("/api/v1/auth/refresh", json={"refresh_token": second_token})
        assert stale.status_code == 401


class TestAuthEndpoints:
    async def test_health_no_auth_required(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200

    async def test_metrics_endpoint(self, client: AsyncClient):
        response = await client.get("/api/v1/metrics")
        assert response.status_code == 200

    async def test_ready_endpoint(self, client: AsyncClient):
        response = await client.get("/api/v1/ready")
        assert response.status_code == 200

    async def test_openapi_has_auth_flow(self, client: AsyncClient):
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        assert "/api/v1/auth/login" in str(response.json()["paths"])


class TestSendOTP:
    async def test_send_otp_success(self, client: AsyncClient):
        response = await client.post("/api/v1/auth/send-otp", json={"phone": "+989123456789"})
        assert response.status_code == 204

    async def test_send_otp_invalid_phone(self, client: AsyncClient):
        response = await client.post("/api/v1/auth/send-otp", json={"phone": "123"})
        assert response.status_code == 422


class TestVerifyOTP:
    async def test_verify_otp_invalid_code(self, client: AsyncClient):
        await client.post("/api/v1/auth/send-otp", json={"phone": "+989123456780"})
        response = await client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": "+989123456780", "code": "000000"},
        )
        assert response.status_code == 401

    async def test_verify_otp_success(self, client: AsyncClient):
        await client.post("/api/v1/auth/send-otp", json={"phone": "+989123456781"})
        otp_key = "otp:+989123456781"
        import redis.asyncio as aioredis

        mock_redis: aioredis.Redis = client._transport.app.state.redis  # type: ignore[union-attr]
        stored = await mock_redis.get(otp_key)
        assert stored is not None
        code = stored.decode() if isinstance(stored, bytes) else stored
        response = await client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": "+989123456781", "code": code},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data


class TestGoogleAuth:
    async def test_google_auth_not_configured(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/google",
            json={"id_token": "invalid-token"},
        )
        assert response.status_code == 503
