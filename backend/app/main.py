"""Backend API (PDF: "configure the backend service to select a query from DB").

Reachable only inside the cluster (ClusterIP Service, no Ingress). The frontend
calls GET /api/value every 5 seconds.
"""

import logging
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout

from app import config, db, metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("backend")
settings = config.load()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = db.make_pool(settings)
    app.state.pool.open(wait=False)  # don't block startup; /readyz reports DB health
    log.info(
        "backend %s started (db %s/%s as %s)",
        settings.app_version,
        settings.db_host,
        settings.db_name,
        settings.db_user,
    )
    yield
    app.state.pool.close()


app = FastAPI(
    title="lab-commit backend",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
metrics.instrument(app)


@app.get("/api/value")
def get_value(request: Request):
    try:
        row = db.latest_value(request.app.state.pool)
    except (psycopg.Error, PoolTimeout) as exc:
        log.warning("database query failed: %s", exc)
        return JSONResponse({"error": "database unavailable"}, status_code=503)
    if row is None:
        return JSONResponse({"error": "no value in lab_values"}, status_code=404)
    return {**row, "version": settings.app_version}


@app.get("/healthz")
def healthz():
    """Liveness: the process is up. Deliberately doesn't touch the database."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz(request: Request):
    """Readiness: only receive traffic when the database answers."""
    try:
        db.ping(request.app.state.pool)
    except (psycopg.Error, PoolTimeout):
        return JSONResponse({"status": "database unavailable"}, status_code=503)
    return {"status": "ready"}
