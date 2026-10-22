"""Set the value the app shows, for the demo "change the value in the database and
watch the page change within 5 seconds".

Inserts a new row into lab_values; the backend always returns the newest row, so
the old values stay as history. Runs as a one-off Kubernetes Job with the
db-migrator service account (the only identity that may read the RDS master
secret), started by scripts/set-db-value.sh in the infra repo.

Run with: python -m app.set_value 42
"""

import logging
import sys

import psycopg

from app import config, db
from app.migrate import master_credentials

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("set_value")

INSERT_VALUE_SQL = "INSERT INTO lab_values (value) VALUES (%s) RETURNING id, value, updated_at"
PG_INTEGER = range(-(2**31), 2**31)  # the lab_values.value column type


def parse_value(args: list[str]) -> int:
    usage = "usage: python -m app.set_value <integer>"
    if len(args) != 1:
        raise SystemExit(usage)
    try:
        value = int(args[0])
    except ValueError:
        raise SystemExit(usage) from None
    if value not in PG_INTEGER:
        raise SystemExit(f"{value} does not fit in a PostgreSQL integer")
    return value


def main() -> None:
    value = parse_value(sys.argv[1:])
    settings = config.load()
    username, password = master_credentials(settings)
    with psycopg.connect(
        db.conninfo(settings, username), password=password, autocommit=True
    ) as conn:
        row_id, new_value, updated_at = conn.execute(INSERT_VALUE_SQL, (value,)).fetchone()
    log.info("lab_values row %d: value=%d at %s", row_id, new_value, updated_at.isoformat())


if __name__ == "__main__":
    main()
