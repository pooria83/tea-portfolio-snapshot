import time
from collections.abc import MutableMapping
from typing import Any

from fastapi import Request, Response
from loguru import logger
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.asgi import wrap_send

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

IN_FLIGHT = Gauge(
    "http_requests_in_flight",
    "Currently in-flight requests",
)

ERROR_COUNT = Counter(
    "http_errors_total",
    "Total HTTP errors",
    ["method", "endpoint", "status"],
)


class PrometheusMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        route = scope.get("route", None)
        endpoint = getattr(route, "path", scope.get("path", ""))
        start = time.monotonic()

        IN_FLIGHT.inc()

        def on_start(message: MutableMapping[str, Any]) -> None:
            status = message["status"]
            duration = time.monotonic() - start
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)
            if status >= 500:
                ERROR_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
            common = dict(method=method, path=scope.get("path", ""), status=status, duration_ms=round(duration * 1000, 2))
            if status >= 500:
                logger.error("http_request", **common)
            elif status >= 400:
                logger.warning("http_request", **common)
            else:
                logger.info("http_request", **common)

        try:
            await self.app(scope, receive, wrap_send(send, on_start))
        except Exception:
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=500).inc()
            ERROR_COUNT.labels(method=method, endpoint=endpoint, status=500).inc()
            raise
        finally:
            IN_FLIGHT.dec()


async def metrics_endpoint(request: Request | None = None) -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
