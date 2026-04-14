from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.dependencies import ClassifierDep
from app.schemas import HealthResponse, ReadyResponse
from app.schemas.errors import ErrorDetail, ErrorResponse
from app.observability.telemetry import metrics_response

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


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
