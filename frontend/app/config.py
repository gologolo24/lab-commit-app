"""Settings from environment variables."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_version: str
    backend_url: str
    poll_interval_seconds: float
    backend_timeout_seconds: float


def load() -> Settings:
    env = os.environ.get
    return Settings(
        app_version=env("APP_VERSION", "0.0.0"),
        backend_url=env("BACKEND_URL", "http://backend:8080"),
        poll_interval_seconds=float(env("POLL_INTERVAL_SECONDS", "5")),
        backend_timeout_seconds=float(env("BACKEND_TIMEOUT_SECONDS", "2")),
    )
