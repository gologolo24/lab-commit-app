"""Prometheus metrics: request count and latency per route.

The route *template* is used as the label (not the raw path) so the number of
time series stays small.
"""

import time

from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "handler", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "handler"])


def instrument(app: FastAPI) -> None:
    @app.middleware("http")
    async def record(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        handler = getattr(request.scope.get("route"), "path", "unmatched")
        if handler != "/metrics":
            REQUESTS.labels(request.method, handler, str(response.status_code)).inc()
            LATENCY.labels(request.method, handler).observe(time.perf_counter() - start)
        return response

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
