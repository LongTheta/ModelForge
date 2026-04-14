from __future__ import annotations

import logging
import time

from fastapi import APIRouter

from app.dependencies import ClassifierDep
from app.exceptions import InferenceError
from app.observability.telemetry import INFERENCE_SECONDS, PREDICTIONS_TOTAL
from app.schemas import PredictRequest, PredictResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["inference"])


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
            model_version=model.model_version(),
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
