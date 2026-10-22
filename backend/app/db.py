"""PostgreSQL access with IAM database authentication.

Every new connection uses a fresh IAM auth token as its password. The token is
valid for 15 minutes and is signed locally with the pod's IRSA credentials, so no
password is stored anywhere. TLS is verified against the RDS CA bundle
(sslmode=verify-full). The RDS instance refuses plain-text connections anyway.
"""

from typing import Any

import boto3
import psycopg
from psycopg_pool import ConnectionPool

from app.config import Settings

LATEST_VALUE_SQL = "SELECT value, updated_at FROM lab_values ORDER BY id DESC LIMIT 1"


def conninfo(settings: Settings, user: str) -> str:
    return psycopg.conninfo.make_conninfo(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=user,
        sslmode="verify-full",
        sslrootcert=settings.db_ssl_root_cert,
        connect_timeout=5,
        application_name="lab-commit-backend",
    )


def make_pool(settings: Settings) -> ConnectionPool:
    rds = boto3.client("rds", region_name=settings.aws_region)

    class IamTokenConnection(psycopg.Connection):
        """A connection that logs in with a new IAM token each time it's opened."""

        @classmethod
        def connect(cls, conninfo: str = "", **kwargs: Any) -> "IamTokenConnection":
            kwargs["password"] = rds.generate_db_auth_token(
                DBHostname=settings.db_host,
                Port=settings.db_port,
                DBUsername=settings.db_user,
                Region=settings.aws_region,
            )
            return super().connect(conninfo, **kwargs)

    return ConnectionPool(
        conninfo(settings, settings.db_user),
        connection_class=IamTokenConnection,
        min_size=1,
        max_size=4,
        max_lifetime=600,  # reconnect (with a new token) well before the 15 min token expiry
        open=False,
        name="lab-commit",
    )


def latest_value(pool: ConnectionPool) -> dict[str, Any] | None:
    with pool.connection(timeout=5) as conn:
        row = conn.execute(LATEST_VALUE_SQL).fetchone()
    if row is None:
        return None
    value, updated_at = row
    return {"value": value, "updated_at": updated_at.isoformat()}


def ping(pool: ConnectionPool) -> None:
    with pool.connection(timeout=3) as conn:
        conn.execute("SELECT 1")
