from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient

REDIRECT_URI = "https://portfolio.example.invalid/auth/google/callback"


async def _register(client: AsyncClient, email: str, username: str) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "StrongPass1!"},
    )
    assert resp.status_code == 201


class TestAuthCookies:
    async def test_login_sets_http_only_cookies(self, client: AsyncClient):
        await _register(client, "cookielogin@example.com", "cookielogin")
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "cookielogin@example.com", "password": "StrongPass1!"},
        )
        assert resp.status_code == 200
        set_cookie = resp.headers.get("set-cookie", "")
        assert "access_token=" in set_cookie
        assert "refresh_token=" in set_cookie
        assert "HttpOnly" in set_cookie
        assert "access_token" in client.cookies
        assert "refresh_token" in client.cookies

    async def test_register_sets_cookies(self, client: AsyncClient):
        await _register(client, "cookiereg@example.com", "cookiereg")
        assert "access_token" in client.cookies
        assert "refresh_token" in client.cookies

    async def test_refresh_uses_cookie_fallback(self, client: AsyncClient):
        await _register(client, "cookieref@example.com", "cookieref")
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_logout_revokes_token_and_clears_cookies(self, client: AsyncClient):
        await _register(client, "cookielogout@example.com", "cookielogout")
        assert "refresh_token" in client.cookies
        resp = await client.post("/api/v1/auth/logout")
        assert resp.status_code == 204
        assert "access_token" not in client.cookies
        assert "refresh_token" not in client.cookies
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401


class TestOAuthState:
    async def test_google_nonce_returns_state(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/google/nonce")
        assert resp.status_code == 200
        state = resp.json()["state"]
        assert isinstance(state, str)
        assert len(state) >= 8

    async def test_google_code_invalid_state(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/google/code",
            json={"code": "fake-code", "redirect_uri": REDIRECT_URI, "state": "invalid-state-value"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["translation_key"] == "invalid_oauth_state"

    async def test_google_code_consumes_state_on_use(self, client: AsyncClient):
        nonce = await client.post("/api/v1/auth/google/nonce")
        state = nonce.json()["state"]

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {"id_token": "fake-id-token"}
        mock_client.post = AsyncMock(return_value=mock_resp)

        def _payload() -> dict:
            return {"code": "fake-code", "redirect_uri": REDIRECT_URI, "state": state}

        with patch("app.api.v1.auth.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            first = await client.post("/api/v1/auth/google/code", json=_payload())
        assert first.status_code == 503

        with patch("app.api.v1.auth.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            second = await client.post("/api/v1/auth/google/code", json=_payload())
        assert second.status_code == 401
        assert second.json()["error"]["translation_key"] == "invalid_oauth_state"


class TestLinkGoogle:
    async def test_link_google_invalid_state(self, client: AsyncClient, auth_headers: dict[str, str]):
        resp = await client.post(
            "/api/v1/users/me/link/google",
            headers=auth_headers,
            json={"code": "fake-code", "redirect_uri": REDIRECT_URI, "state": "invalid-state-value"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["translation_key"] == "invalid_oauth_state"
