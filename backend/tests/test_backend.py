"""Backend tests: no real database or AWS calls (the pool is replaced by a fake)."""

from datetime import UTC, datetime

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import config, db, main, migrate, set_value


class FakeConnection:
    def __init__(self, row):
        self.row = row

    def execute(self, _query):
        return self

    def fetchone(self):
        return self.row


class FakePool:
    def __init__(self, row=None, error=None):
        self.row, self.error = row, error

    def open(self, wait=True):
        pass

    def close(self):
        pass

    def connection(self, timeout=None):
        pool = self

        class _Ctx:
            def __enter__(self):
                if pool.error:
                    raise pool.error
                return FakeConnection(pool.row)

            def __exit__(self, *exc):
                return False

        return _Ctx()


@pytest.fixture
def client_with(monkeypatch):
    def _make(pool):
        monkeypatch.setattr(db, "make_pool", lambda _settings: pool)
        return TestClient(main.app)

    return _make


def test_value_returns_latest_row(client_with):
    row = (5, datetime(2026, 10, 22, 7, 0, tzinfo=UTC))
    with client_with(FakePool(row=row)) as client:
        body = client.get("/api/value").json()
    assert body["value"] == 5
    assert body["updated_at"].startswith("2026-10-22T07:00:00")


def test_value_404_when_table_empty(client_with):
    with client_with(FakePool(row=None)) as client:
        assert client.get("/api/value").status_code == 404


def test_value_503_when_database_down(client_with):
    with client_with(FakePool(error=psycopg.OperationalError("down"))) as client:
        assert client.get("/api/value").status_code == 503
        assert client.get("/readyz").status_code == 503
        assert client.get("/healthz").status_code == 200  # liveness doesn't depend on the DB


def test_metrics_count_requests_by_route(client_with):
    with client_with(FakePool(row=(1, datetime.now(UTC)))) as client:
        client.get("/api/value")
        text = client.get("/metrics").text
    assert 'http_requests_total{handler="/api/value",method="GET",status="200"}' in text


def test_migration_is_scoped_to_read_only_app_user():
    settings = config.load()
    rendered = [s.as_string(None) for s in migrate.statements(settings)]
    assert any("CREATE TABLE IF NOT EXISTS lab_values" in s for s in rendered)
    assert 'GRANT rds_iam TO "app_reader"' in rendered
    assert 'GRANT SELECT ON lab_values TO "app_reader"' in rendered
    assert not any("INSERT" in s and "UPDATE" in s for s in rendered)
    assert not any("GRANT ALL" in s or "SUPERUSER" in s for s in rendered)


def test_conninfo_requires_verified_tls():
    info = db.conninfo(config.load(), "app_reader")
    assert "sslmode=verify-full" in info
    assert "sslrootcert=" in info


def test_set_value_accepts_one_integer():
    assert set_value.parse_value(["42"]) == 42
    assert set_value.parse_value(["-7"]) == -7
    for bad in ([], ["1", "2"], ["4.2"], ["abc"], [str(2**31)]):
        with pytest.raises(SystemExit):
            set_value.parse_value(bad)


def test_set_value_inserts_a_row_with_a_bound_parameter():
    # A new row (history kept), the value passed as a parameter, never formatted in.
    assert set_value.INSERT_VALUE_SQL.startswith("INSERT INTO lab_values (value) VALUES (%s)")
    # The backend reads the newest row, so the inserted value is what the page shows.
    assert "ORDER BY id DESC LIMIT 1" in db.LATEST_VALUE_SQL
