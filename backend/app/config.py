"""Settings from environment variables. No secrets here: the backend logs in to
PostgreSQL with short-lived IAM tokens, and the migration job reads the master
password from Secrets Manager at run time."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_version: str
    aws_region: str
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_ssl_root_cert: str
    db_master_secret_id: str  # only used by app.migrate
    seed_value: int  # only used by app.migrate


def load() -> Settings:
    env = os.environ.get
    return Settings(
        app_version=env("APP_VERSION", "0.0.0"),
        aws_region=env("AWS_REGION", "us-east-1"),
        db_host=env("DB_HOST", "localhost"),
        db_port=int(env("DB_PORT", "5432")),
        db_name=env("DB_NAME", "labcommit"),
        db_user=env("DB_USER", "app_reader"),
        db_ssl_root_cert=env("DB_SSL_ROOT_CERT", "/app/certs/rds-global-bundle.pem"),
        db_master_secret_id=env("DB_MASTER_SECRET_ID", ""),
        seed_value=int(env("SEED_VALUE", "5")),
    )
