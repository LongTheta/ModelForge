from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.deployment import get_deployment_meta
from app.dependencies import ClassifierDep
from app.inference import get_classifier
from app.schemas import HealthResponse, ReadyResponse, StatusResponse
from app.schemas.errors import ErrorDetail, ErrorResponse
from app.observability.telemetry import metrics_response

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/status", response_model=StatusResponse)
def status() -> StatusResponse:
    meta = get_deployment_meta()
    model_version: str | None = None
    clf = get_classifier()
    if clf.is_ready:
        model_version = clf.model_version()
    return StatusResponse(
        version=meta.version,
        environment=meta.environment,
        git_commit=meta.git_commit,
        git_commit_full=meta.git_commit_full,
        service=meta.service_name,
        model_version=model_version,
        pod=meta.pod_name or None,
        namespace=meta.pod_namespace or None,
    )


@router.get(
    "/readyz",
    response_model=ReadyResponse,
    responses={503: {"description": "Classifier not loaded"}},
)
def readyz(model: ClassifierDep) -> ReadyResponse | JSONResponse:
    if not model.is_ready:
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="model_not_ready",
                    message="Classifier has not finished loading",
                )
            ).model_dump(),
        )
    return ReadyResponse(status="ready")


@router.get("/metrics", include_in_schema=False)
def metrics():
    return metrics_response()
