import contextvars
import logging
import sys
from typing import Any

from loguru import logger

_PII_FIELDS = {"email", "password", "token", "secret", "authorization", "cookie", "api_key", "api-key", "apikey", "jwt"}

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="")
log_source_var: contextvars.ContextVar[str] = contextvars.ContextVar("log_source", default="")


def _pii_filter(record: dict[str, Any]) -> bool:
    for key in list(record["extra"].keys()):
        if any(pii in key.lower() for pii in _PII_FIELDS):
            record["extra"][key] = "[REDACTED]"
    return True


def _inject_context(record: dict[str, Any]) -> None:
    rid = request_id_var.get()
    if rid:
        record["extra"]["request_id"] = rid
    uid = user_id_var.get()
    if uid:
        record["extra"]["user_id"] = uid
    src = log_source_var.get()
    if src:
        record["extra"]["source"] = src


_LEVEL_MAP = {
    logging.CRITICAL: "CRITICAL",
    logging.ERROR: "ERROR",
    logging.WARNING: "WARNING",
    logging.INFO: "INFO",
    logging.DEBUG: "DEBUG",
}


class _ContextCaptureFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        rid = request_id_var.get()
        uid = user_id_var.get()
        src = log_source_var.get()
        if rid:
            record.request_id = rid
        if uid:
            record.user_id = uid
        if src:
            record.source = src
        return True


class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        level = _LEVEL_MAP.get(record.levelno, "INFO")
        bound = logger
        rid = request_id_var.get() or getattr(record, "request_id", "")
        uid = user_id_var.get() or getattr(record, "user_id", "")
        src = log_source_var.get() or getattr(record, "source", "")
        if rid:
            bound = bound.bind(request_id=rid)
        if uid:
            bound = bound.bind(user_id=uid)
        if src:
            bound = bound.bind(source=src)
        bound.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def suppress_stdlib_logging() -> None:
    for name in list(logging.root.manager.loggerDict):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    logging.root.handlers.clear()
    intercept = _InterceptHandler()
    intercept.addFilter(_ContextCaptureFilter())
    logging.root.addHandler(intercept)
    logging.root.setLevel(logging.DEBUG)


def setup_logging(*, debug: bool = False, json: bool = False) -> None:
    logger.remove()
    logger.configure(patcher=_inject_context)  # type: ignore[arg-type]

    suppress_stdlib_logging()

    if json:
        logger.add(
            sys.stderr,
            format="{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | {level:<8} | {name}:{function}:{line} | {message} | {extra}",
            serialize=True,
            filter=_pii_filter,  # type: ignore[arg-type]
            level="DEBUG" if debug else "INFO",
        )
    else:
        from rich.logging import RichHandler

        logger.add(
            RichHandler(
                rich_tracebacks=True,
                show_time=True,
                show_path=True,
                markup=True,
            ),
            format="{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | {level:<8} | {name}:{function}:{line} | {message} | {extra}",
            filter=_pii_filter,  # type: ignore[arg-type]
            level="DEBUG" if debug else "INFO",
        )

    for lib in ("httpx", "qdrant_client", "sqlalchemy.engine"):
        logging.getLogger(lib).setLevel(logging.WARNING)
