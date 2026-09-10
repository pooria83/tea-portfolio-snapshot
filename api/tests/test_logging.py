from unittest.mock import patch

from app.core.logging import _pii_filter


def _make_record(extra: dict | None = None) -> dict:
    return {"extra": extra or {}}


def test_pii_filter_redacts_email():
    record = _make_record({"email": "user@test.com", "message": "hello"})
    _pii_filter(record)
    assert record["extra"]["email"] == "[REDACTED]"


def test_pii_filter_redacts_password():
    record = _make_record({"password": "secret123"})
    _pii_filter(record)
    assert record["extra"]["password"] == "[REDACTED]"


def test_pii_filter_redacts_token():
    record = _make_record({"access_token": "eyJ..."})
    _pii_filter(record)
    assert record["extra"]["access_token"] == "[REDACTED]"


def test_pii_filter_redacts_api_key():
    record = _make_record({"X-API-Key": "my-key"})
    _pii_filter(record)
    assert record["extra"]["X-API-Key"] == "[REDACTED]"


def test_pii_filter_redacts_authorization():
    record = _make_record({"authorization": "Bearer eyJ..."})
    _pii_filter(record)
    assert record["extra"]["authorization"] == "[REDACTED]"


def test_pii_filter_redacts_secret():
    record = _make_record({"secret_key": "super-secret"})
    _pii_filter(record)
    assert record["extra"]["secret_key"] == "[REDACTED]"


def test_pii_filter_no_pii():
    record = _make_record({"message": "hello", "level": "info"})
    assert _pii_filter(record) is True
    assert record["extra"] == {"message": "hello", "level": "info"}


def test_pii_filter_case_insensitive():
    record = _make_record({"Email": "user@test.com", "TOKEN": "abc123"})
    _pii_filter(record)
    assert record["extra"]["Email"] == "[REDACTED]"
    assert record["extra"]["TOKEN"] == "[REDACTED]"


@patch("app.core.logging.logger.add")
def test_setup_logging_debug(mock_add):
    from app.core.logging import setup_logging

    setup_logging(debug=True)
    mock_add.assert_called_once()


@patch("app.core.logging.logger.add")
def test_setup_logging_production(mock_add):
    from app.core.logging import setup_logging

    setup_logging(debug=False)
    mock_add.assert_called_once()
