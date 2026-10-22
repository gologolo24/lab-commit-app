"""One-time database setup, run as a Kubernetes Job before each deploy
(Argo CD PreSync hook, service account db-migrator). Idempotent: safe to run
any number of times.

- reads the RDS-managed master password from Secrets Manager (the job's IAM role
  may read only that one secret)
- creates the lab_values table and the seed value (PDF example: "Hello Lab-commit 5")
- creates the read-only application user, which logs in with IAM tokens only (rds_iam)
  and may only SELECT from lab_values

Run with: python -m app.migrate
"""

import json
import logging

import boto3
import psycopg
from psycopg import sql

from app import config, db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("migrate")


def master_credentials(settings: config.Settings) -> tuple[str, str]:
    if not settings.db_master_secret_id:
        raise SystemExit("DB_MASTER_SECRET_ID is not set")
    secrets = boto3.client("secretsmanager", region_name=settings.aws_region)
    secret = json.loads(
        secrets.get_secret_value(SecretId=settings.db_master_secret_id)["SecretString"]
    )
    return secret["username"], secret["password"]


def statements(settings: config.Settings) -> list[sql.Composable]:
    app_user = sql.Identifier(settings.db_user)
    return [
        sql.SQL(
            "CREATE TABLE IF NOT EXISTS lab_values ("
            " id SERIAL PRIMARY KEY,"
            " value INTEGER NOT NULL,"
            " updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        ),
        sql.SQL(
            "INSERT INTO lab_values (value) SELECT {seed}"
            " WHERE NOT EXISTS (SELECT 1 FROM lab_values)"
        ).format(seed=sql.Literal(settings.seed_value)),
        sql.SQL(
            "DO $$ BEGIN"
            " IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = {name}) THEN"
            " CREATE ROLE {user} LOGIN;"
            " END IF; END $$"
        ).format(name=sql.Literal(settings.db_user), user=app_user),
        sql.SQL("GRANT rds_iam TO {user}").format(user=app_user),
        sql.SQL("GRANT CONNECT ON DATABASE {database} TO {user}").format(
            database=sql.Identifier(settings.db_name), user=app_user
        ),
        sql.SQL("GRANT USAGE ON SCHEMA public TO {user}").format(user=app_user),
        sql.SQL("GRANT SELECT ON lab_values TO {user}").format(user=app_user),
    ]


def main() -> None:
    settings = config.load()
    username, password = master_credentials(settings)
    log.info("migrating %s/%s (app user: %s)", settings.db_host, settings.db_name, settings.db_user)
    with psycopg.connect(
        db.conninfo(settings, username), password=password, autocommit=True
    ) as conn:
        for statement in statements(settings):
            conn.execute(statement)
        count = conn.execute("SELECT count(*) FROM lab_values").fetchone()[0]
    log.info("done: lab_values has %d row(s); %s may only SELECT", count, settings.db_user)


if __name__ == "__main__":
    main()
