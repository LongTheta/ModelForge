from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str


class StatusResponse(BaseModel):
    """Runtime metadata for operators (no secrets or config values)."""

    version: str = Field(description="Application / build version string.")
    environment: str = Field(description="Logical deployment environment (e.g. dev, prod).")
    git_commit: str = Field(description="Short Git SHA (7 chars) when available.")
    git_commit_full: str = Field(description="Full Git SHA or CI ref when available.")
    service: str = Field(description="Service identifier (typically OTEL_SERVICE_NAME).")
    model_version: str | None = Field(
        default=None,
        description="Loaded inference artifact version when the model is ready.",
    )
    pod: str | None = Field(default=None, description="Kubernetes pod name when running in-cluster.")
    namespace: str | None = Field(
        default=None,
        description="Kubernetes namespace when running in-cluster.",
    )
