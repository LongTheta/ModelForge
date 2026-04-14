from __future__ import annotations

import logging
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.dependencies import ClassifierDep
from app.exceptions import InferenceError
from app.inference import MODEL_VERSION
from app.observability.telemetry import INFERENCE_SECONDS, PREDICTIONS_TOTAL, metrics_response
from app.schemas import HealthResponse, PredictRequest, PredictResponse, ReadyResponse
from app.schemas.errors import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["inference"])


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
    """Prometheus text exposition (``prometheus_client``)."""
    return metrics_response()


@router.post("/predict", response_model=PredictResponse)
def predict(body: PredictRequest, model: ClassifierDep) -> PredictResponse:
    start = time.perf_counter()
    try:
        label, confidence, scores = model.predict(body.text)
        ordered_scores = dict(sorted(scores.items()))
        PREDICTIONS_TOTAL.labels("success").inc()
        return PredictResponse(
            label=label,
            confidence=confidence,
            scores=ordered_scores,
            model_version=MODEL_VERSION,
        )
    except InferenceError:
        PREDICTIONS_TOTAL.labels("error").inc()
        raise
    except Exception as e:
        PREDICTIONS_TOTAL.labels("error").inc()
        logger.exception("predict failed")
        raise InferenceError("Prediction failed", code="prediction_failed") from e
    finally:
        INFERENCE_SECONDS.observe(time.perf_counter() - start)
