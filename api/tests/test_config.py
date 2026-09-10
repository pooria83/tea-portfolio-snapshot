import warnings

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_database_url_validation():
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(database_url="sqlite:///test.db")


def test_database_url_valid():
    s = Settings(database_url="postgresql+asyncpg://user:pass@localhost:5432/test")
    assert s.database_url == "postgresql+asyncpg://user:pass@localhost:5432/test"


def test_allowed_origins_empty():
    with pytest.raises(ValidationError, match="must not be empty"):
        Settings(allowed_origins="")


def test_production_warning_on_localhost_origins():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Settings(debug=False, allowed_origins="http://localhost:3000")
        assert len(w) >= 1
        assert any("ALLOWED_ORIGINS only contains localhost" in str(msg.message) for msg in w)


def test_no_warning_with_production_origins():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Settings(debug=False, allowed_origins="https://myapp.com")
        prod_warnings = [msg for msg in w if "ALLOWED_ORIGINS only contains localhost" in str(msg.message)]
        assert len(prod_warnings) == 0


def test_no_warning_in_debug_mode():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Settings(debug=True, allowed_origins="http://localhost:3000")
        prod_warnings = [msg for msg in w if "ALLOWED_ORIGINS only contains localhost" in str(msg.message)]
        assert len(prod_warnings) == 0


def test_cors_wildcard_warning():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Settings(debug=False, allowed_origins="*", secret_key="not-default-secret", jwt_secret_key="not-default-jwt")
        wildcard_warnings = [msg for msg in w if "Wildcard origin" in str(msg.message)]
        assert len(wildcard_warnings) == 1


def test_cors_wildcard_credentials_warning():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Settings(debug=True, allowed_origins="*")
        cred_warnings = [msg for msg in w if "CORS allow_origins contains '*'" in str(msg.message)]
        assert len(cred_warnings) == 1


def test_default_secret_warning():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Settings(debug=False, allowed_origins="https://myapp.com", secret_key="change-me")
        secret_warnings = [msg for msg in w if "SECRET_KEY is still set to the default" in str(msg.message)]
        assert len(secret_warnings) >= 1
