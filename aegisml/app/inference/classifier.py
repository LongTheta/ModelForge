from __future__ import annotations

import threading

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.exceptions import InferenceError

MODEL_VERSION = "ticket-triage-tfidf-1.0"

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


class TicketClassifier:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pipeline: Pipeline | None = None

    @property
    def is_ready(self) -> bool:
        return self._pipeline is not None

    def ensure_loaded(self) -> None:
        if self._pipeline is not None:
            return
        with self._lock:
            if self._pipeline is not None:
                return
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
                    ("clf", LogisticRegression(max_iter=300, random_state=42)),
                ]
            )
            pipeline.fit(list(_TRAINING_TEXTS), y)
            self._pipeline = pipeline

    def predict(self, text: str) -> tuple[str, float, dict[str, float]]:
        self.ensure_loaded()
        pipeline = self._pipeline
        if pipeline is None:
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


def reset_classifier_for_tests() -> None:
    global _model
    with _model_lock:
        _model = None
