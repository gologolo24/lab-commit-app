"""Polls the backend every POLL_INTERVAL_SECONDS and keeps the last answer.

PDF: "the frontend service will pull each X amount of time (5 seconds) the values
from the backend service and present the value in the HTTPS response".
Pages are served from this in-memory snapshot, so page views never wait on the
backend or the database. If the backend is down, the last known value is kept
and marked as stale.
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime

import httpx

log = logging.getLogger("frontend.poller")


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Snapshot:
    value: int | None = None
    updated_at: str | None = None  # when the row last changed in the database
    fetched_at: str | None = None  # when the frontend last got an answer
    backend_ok: bool = False
    backend_version: str | None = None  # lets the backend pipeline check its release end to end


class Poller:
    def __init__(self, backend_url: str, interval: float, timeout: float, client=None):
        self.url = backend_url.rstrip("/") + "/api/value"
        self.interval = interval
        self.client = client or httpx.AsyncClient(timeout=timeout)
        self.snapshot = Snapshot()
        self._task: asyncio.Task | None = None

    async def poll_once(self) -> None:
        try:
            response = await self.client.get(self.url)
            response.raise_for_status()
            body = response.json()
            self.snapshot = Snapshot(
                value=int(body["value"]),
                updated_at=body.get("updated_at"),
                fetched_at=now_iso(),
                backend_ok=True,
                backend_version=body.get("version"),
            )
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            log.warning("backend poll failed: %r", exc)
            self.snapshot = replace(self.snapshot, backend_ok=False)  # keep the last value

    async def run(self) -> None:
        while True:
            await self.poll_once()
            await asyncio.sleep(self.interval)

    def start(self) -> None:
        self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        await self.client.aclose()
