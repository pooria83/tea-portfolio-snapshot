from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest

from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.core.jwt import TokenPayload, create_access_token, create_refresh_token, decode_token


class TestCreateAccessToken:
    def test_creates_token_for_user(self):
        token = create_access_token("user-123")
        payload = decode_token(token)
        assert payload.sub == "user-123"
        assert payload.role == "user"

    def test_creates_token_with_custom_role(self):
        token = create_access_token("admin-1", role="admin")
        payload = decode_token(token)
        assert payload.sub == "admin-1"
        assert payload.role == "admin"

    def test_token_has_expiry_in_future(self):
        token = create_access_token("user-123")
        payload = decode_token(token)
        assert payload.exp > datetime.now(UTC)


class TestCreateRefreshToken:
    def test_creates_token(self):
        token = create_refresh_token("user-123")
        payload = decode_token(token)
        assert payload.sub == "user-123"

    def test_token_has_expiry_in_future(self):
        token = create_refresh_token("user-123")
        payload = decode_token(token)
        assert payload.exp > datetime.now(UTC)


class TestDecodeToken:
    def test_decode_valid_token(self):
        token = create_access_token("user-123")
        payload = decode_token(token)
        assert isinstance(payload, TokenPayload)
        assert payload.sub == "user-123"

    def test_decode_expired_token_raises(self):
        token = pyjwt.encode(
            {
                "sub": "user-123",
                "exp": datetime.now(UTC) - timedelta(hours=1),
                "type": "access",
                "aud": settings.jwt_audience,
                "iss": settings.jwt_issuer,
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(AuthenticationError, match="Invalid token"):
            decode_token(token)

    def test_decode_invalid_signature_raises(self):
        token = pyjwt.encode(
            {"sub": "user-123", "exp": datetime.now(UTC) + timedelta(hours=1)},
            "a-different-secret-key-thats-long-enough-for-sha256",
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(AuthenticationError, match="Invalid token"):
            decode_token(token)

    def test_decode_malformed_token_raises(self):
        with pytest.raises(AuthenticationError, match="Invalid token"):
            decode_token("not-a-token")

    def test_decode_wrong_audience_raises(self):
        token = pyjwt.encode(
            {
                "sub": "user-123",
                "exp": datetime.now(UTC) + timedelta(hours=1),
                "aud": "wrong-audience",
                "iss": settings.jwt_issuer,
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(AuthenticationError, match="Invalid token"):
            decode_token(token)
