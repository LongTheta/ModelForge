from __future__ import annotations

import os
import threading
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.config import get_settings
from app.exceptions import InferenceError

EMBEDDED_MODEL_VERSION = "ticket-triage-tfidf-2.0"

_LABELS = ("incident", "access_request", "general")

_TRAINING_TEXTS = (
    "production outage sev1 customer impact",
    "pod crash loop errors in cluster",
    "database replication lag alert firing",
    "latency spike on payment api",
    "disk full on primary node",
    "need vpn access for contractor",
    "request role grant to staging project",
    "add user to gitlab group",
    "new hire needs aws console access",
    "approve break glass for on call",
    "question about roadmap timeline",
    "documentation link for onboarding",
    "meeting notes from architecture review",
    "can we schedule a design review",
    "feedback on internal wiki page",
)


def _validate_serving_pipeline(obj: object) -> Pipeline:
    if not isinstance(obj, Pipeline):
        raise InferenceError(
            f"Model artifact must be a sklearn Pipeline, got {type(obj).__name__}",
            code="model_invalid",
        )
    if not hasattr(obj, "predict_proba"):
        raise InferenceError("Model pipeline must support predict_proba", code="model_invalid")
    return obj


def _fit_embedded_pipeline(random_state: int) -> Pipeline:
    y = ([_LABELS[0]] * 5 + [_LABELS[1]] * 5 + [_LABELS[2]] * 5)
    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=256,
                    ngram_range=(1, 2),
                    stop_words="english",
                ),
            ),
            ("clf", LogisticRegression(max_iter=300, random_state=random_state)),
        ]
    )
    pipeline.fit(list(_TRAINING_TEXTS), y)
    return pipeline


def _load_pipeline_and_version() -> tuple[Pipeline, str]:
    settings = get_settings()
    path_str = settings.model_path
    rs = settings.sklearn_random_state

    if path_str:
        path = Path(path_str).expanduser()
        if not path.is_file():
            raise InferenceError(
                f"AEGISML_MODEL_PATH is set but file not found: {path}",
                code="model_load_failed",
            )
        try:
            raw = joblib.load(path)
        except Exception as e:
            raise InferenceError(
                f"Failed to load model from {path}: {e}",
                code="model_load_failed",
            ) from e
        pipeline = _validate_serving_pipeline(raw)
        ver = os.getenv("AEGISML_MODEL_VERSION", "").strip()
        if not ver:
            ver = f"artifact:{path.name}"
        return pipeline, ver

    np.random.seed(rs)
    pipeline = _fit_embedded_pipeline(rs)
    return pipeline, EMBEDDED_MODEL_VERSION


class TicketClassifier:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pipeline: Pipeline | None = None
        self._version: str | None = None

    @property
    def is_ready(self) -> bool:
        return self._pipeline is not None and self._version is not None

    def model_version(self) -> str:
        if self._version is None:
            raise RuntimeError("model_version called before load")
        return self._version

    def ensure_loaded(self) -> None:
        if self._pipeline is not None:
            return
        with self._lock:
            if self._pipeline is not None:
                return
            pipeline, version = _load_pipeline_and_version()
            self._pipeline = pipeline
            self._version = version

    def predict(self, text: str) -> tuple[str, float, dict[str, float]]:
        self.ensure_loaded()
        pipeline = self._pipeline
        if pipeline is None or self._version is None:
            raise InferenceError("Model pipeline is not initialized", code="model_unavailable")
        try:
            proba = pipeline.predict_proba([text])[0]
        except Exception as e:
            raise InferenceError("Inference failed", code="inference_failed") from e
        classes = pipeline.named_steps["clf"].classes_
        best = int(np.argmax(proba))
        label = str(classes[best])
        scores = {str(classes[i]): float(proba[i]) for i in range(len(classes))}
        return label, float(proba[best]), scores


_model: TicketClassifier | None = None
_model_lock = threading.Lock()


def get_classifier() -> TicketClassifier:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = TicketClassifier()
    return _model


def get_model_version() -> str:
    return get_classifier().model_version()


def reset_classifier_for_tests() -> None:
    global _model
    with _model_lock:
        _model = None
