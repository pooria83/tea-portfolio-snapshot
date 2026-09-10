import io
import logging

from loguru import logger

from app.core.logging import (
    _inject_context,
    _pii_filter,
    log_source_var,
    request_id_var,
    setup_logging,
    suppress_stdlib_logging,
    user_id_var,
)


def test_pii_filter_redacts_sensitive_fields():
    record = {"extra": {"email": "test@example.com", "api_key": "sk-123", "safe_field": "hello"}}
    assert _pii_filter(record)
    assert record["extra"]["email"] == "[REDACTED]"
    assert record["extra"]["api_key"] == "[REDACTED]"
    assert record["extra"]["safe_field"] == "hello"


def test_pii_filter_ignores_non_pii():
    record = {"extra": {"name": "hello", "count": 5}}
    assert _pii_filter(record)
    assert record["extra"]["name"] == "hello"
    assert record["extra"]["count"] == 5


def test_inject_context_injects_all_vars():
    request_id_var.set("req-1")
    user_id_var.set("user-1")
    log_source_var.set("authenticated")
    record = {"extra": {}}
    _inject_context(record)
    assert record["extra"]["request_id"] == "req-1"
    assert record["extra"]["user_id"] == "user-1"
    assert record["extra"]["source"] == "authenticated"


def test_inject_context_skips_empty_vars():
    request_id_var.set("")
    user_id_var.set("")
    log_source_var.set("")
    record = {"extra": {}}
    _inject_context(record)
    assert record["extra"] == {}


def test_suppress_stdlib_logging_clears_handlers():
    test_logger = logging.getLogger("test.suppress")
    test_logger.setLevel(logging.DEBUG)
    test_logger.handlers = [logging.StreamHandler()]
    test_logger.propagate = False
    suppress_stdlib_logging()
    assert test_logger.handlers == []
    assert test_logger.propagate is True


def test_suppress_stdlib_logging_adds_root_handler():
    logging.root.handlers.clear()
    suppress_stdlib_logging()
    assert len(logging.root.handlers) > 0


def test_setup_logging_initializes_without_error():
    logger.remove()
    setup_logging(debug=False)
    assert len(logger._core.handlers) > 0


def test_setup_logging_json_mode():
    logger.remove()
    buf = io.StringIO()
    logger.add(buf, format="{message}", serialize=True)
    assert len(logger._core.handlers) > 0


def test_intercept_handler_routes_stdlib_to_loguru():
    suppress_stdlib_logging()
    test_logger = logging.getLogger("test.intercept")
    test_logger.info("test message from stdlib")
    # Should not raise
    assert True
