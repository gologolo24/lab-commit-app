"""Frontend tests: the backend is replaced by httpx's MockTransport."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app import main
from app.poller import Poller


def backend(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def run(coro):
    return asyncio.run(coro)


def test_poller_stores_the_backend_value():
    poller = Poller(
        "http://backend:8080",
        5,
        2,
        client=backend(
            lambda request: httpx.Response(
                200, json={"value": 5, "updated_at": "2026-10-22T07:00:00", "version": "1.2.3"}
            )
        ),
    )
    run(poller.poll_once())
    assert poller.snapshot.value == 5
    assert poller.snapshot.backend_ok
    assert poller.snapshot.backend_version == "1.2.3"
    assert poller.url == "http://backend:8080/api/value"


def test_poller_keeps_last_value_when_backend_fails():
    answers = iter([httpx.Response(200, json={"value": 7}), httpx.Response(503)])
    poller = Poller("http://backend:8080", 5, 2, client=backend(lambda request: next(answers)))
    run(poller.poll_once())
    run(poller.poll_once())
    assert poller.snapshot.value == 7
    assert not poller.snapshot.backend_ok


class FakePoller:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def start(self):
        pass

    async def stop(self):
        pass


@pytest.fixture
def client(monkeypatch):
    from app.poller import Snapshot

    snapshot = Snapshot(
        value=5, fetched_at="2026-10-22T07:00:05+00:00", backend_ok=True, backend_version="1.2.3"
    )
    monkeypatch.setattr(main, "make_poller", lambda _settings: FakePoller(snapshot))
    with TestClient(main.app) as test_client:
        yield test_client


def test_page_shows_greeting_with_version_and_db_value(client):
    page = client.get("/")
    assert page.status_code == 200
    assert f"Hello Lab-Commit v{main.settings.app_version}" in page.text
    assert '<strong id="value">5</strong>' in page.text


def test_security_headers(client):
    headers = client.get("/").headers
    assert headers["content-security-policy"].startswith("default-src 'self'")
    assert headers["x-frame-options"] == "DENY"


def test_api_message_and_version(client):
    body = client.get("/api/message").json()
    assert body["message"].startswith("Hello Lab-Commit v")
    assert body["value"] == 5
    assert body["backend_version"] == "1.2.3"  # the backend pipeline's smoke test reads this
    assert client.get("/version").json() == {"version": main.settings.app_version}


def test_page_views_are_counted_for_autoscaling(client):
    # Counters are process-wide, so compare before/after instead of absolute values.
    def page_views():
        labels = {"handler": "/", "method": "GET", "status": "200"}
        return REGISTRY.get_sample_value("http_requests_total", labels) or 0.0

    before = page_views()
    for _ in range(3):
        client.get("/")
    client.get("/api/message")  # the browser's refresh calls must NOT count as page loads
    assert page_views() - before == 3
    assert 'http_requests_total{handler="/"' in client.get("/metrics").text
