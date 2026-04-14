from app.inference.classifier import (
    EMBEDDED_MODEL_VERSION,
    TicketClassifier,
    get_classifier,
    get_model_version,
    reset_classifier_for_tests,
)

MODEL_VERSION = EMBEDDED_MODEL_VERSION

__all__ = [
    "EMBEDDED_MODEL_VERSION",
    "MODEL_VERSION",
    "TicketClassifier",
    "get_classifier",
    "get_model_version",
    "reset_classifier_for_tests",
]
