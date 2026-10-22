"""Frontend (PDF: "Surfing the frontend service, should show 'Hello Lab-Commit'
with 'X' as a String (X - app version number)" and the value from the database).

Served only through the internal ALB (HTTPS) at lab-commit-task.<zone>.
"""

import html
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app import config, metrics
from app.poller import Poller

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("frontend")
settings = config.load()
STATIC_DIR = Path(__file__).parent / "static"

SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'; base-uri 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000",
    "Cache-Control": "no-store",
}


def make_poller(s: config.Settings) -> Poller:
    return Poller(s.backend_url, s.poll_interval_seconds, s.backend_timeout_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.poller = make_poller(settings)
    app.state.poller.start()
    log.info(
        "frontend %s polling %s every %ss",
        settings.app_version,
        settings.backend_url,
        settings.poll_interval_seconds,
    )
    yield
    await app.state.poller.stop()


app = FastAPI(
    title="lab-commit frontend",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
metrics.instrument(app)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    return response


def greeting() -> str:
    return f"Hello Lab-Commit v{settings.app_version}"


def message(snapshot) -> dict:
    return {
        "message": greeting(),
        "version": settings.app_version,
        "value": snapshot.value,
        "updated_at": snapshot.updated_at,
        "fetched_at": snapshot.fetched_at,
        "backend_ok": snapshot.backend_ok,
        "poll_interval_seconds": settings.poll_interval_seconds,
    }


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <main>
    <h1 id="greeting">{title}</h1>
    <p class="value">Value from the database: <strong id="value">{value}</strong></p>
    <p class="meta">
      The frontend asks the backend every {interval:g} seconds.
      Last answer: <span id="fetched">{fetched}</span>
      <span id="status" class="{status_class}">{status}</span>
    </p>
  </main>
  <script src="/static/refresh.js" defer></script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    s = app.state.poller.snapshot
    return PAGE.format(
        title=html.escape(greeting()),
        value=html.escape("-" if s.value is None else str(s.value)),
        interval=settings.poll_interval_seconds,
        fetched=html.escape(s.fetched_at or "not yet"),
        status="" if s.backend_ok else "(backend unavailable, showing the last known value)",
        status_class="ok" if s.backend_ok else "stale",
    )


@app.get("/api/message")
def api_message():
    return message(app.state.poller.snapshot)


@app.get("/version")
def version():
    return {"version": settings.app_version}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    # Ready even if the backend is down: the page then shows the last known value.
    return {"status": "ready"}
