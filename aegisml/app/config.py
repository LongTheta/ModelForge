"""Environment-backed settings. No secrets belong here; inject via env or mounted files."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    log_level: str
    service_name: str
    environment: str
    model_path: str | None
    sklearn_random_state: int

    @classmethod
    def from_env(cls) -> Settings:
        path = os.getenv("AEGISML_MODEL_PATH", "").strip()
        rs_raw = os.getenv("AEGISML_SKLEARN_RANDOM_STATE", "42").strip()
        try:
            rs = int(rs_raw)
        except ValueError:
            rs = 42
        return cls(
            host=os.getenv("AEGISML_HOST", "0.0.0.0"),
            port=int(os.getenv("AEGISML_PORT", "8080")),
            log_level=os.getenv("AEGISML_LOG_LEVEL", "info"),
            service_name=os.getenv("OTEL_SERVICE_NAME", "aegisml-inference"),
            environment=os.getenv("AEGISML_ENVIRONMENT")
            or os.getenv("AEGISML_DEPLOYMENT", "local"),
            model_path=path or None,
            sklearn_random_state=rs,
        )


def get_settings() -> Settings:
    return Settings.from_env()
