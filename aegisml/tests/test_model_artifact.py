"""Optional AEGISML_MODEL_PATH: load a joblib-serialized sklearn Pipeline."""

from __future__ import annotations

from pathlib import Path

import joblib
import pytest

from app.inference import EMBEDDED_MODEL_VERSION, get_classifier, reset_classifier_for_tests
from app.inference.classifier import _fit_embedded_pipeline


def test_load_pipeline_from_joblib_artifact(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pipeline = _fit_embedded_pipeline(42)
    path = tmp_path / "model.joblib"
    joblib.dump(pipeline, path)
    monkeypatch.setenv("AEGISML_MODEL_PATH", str(path))
    monkeypatch.setenv("AEGISML_MODEL_VERSION", "unit-test-artifact")

    reset_classifier_for_tests()
    m = get_classifier()
    m.ensure_loaded()
    try:
        assert m.model_version() == "unit-test-artifact"
        label, _, scores = m.predict("need vpn access for contractor")
        assert label == "access_request"
        assert abs(sum(scores.values()) - 1.0) < 1e-5
    finally:
        monkeypatch.delenv("AEGISML_MODEL_PATH", raising=False)
        monkeypatch.delenv("AEGISML_MODEL_VERSION", raising=False)
        reset_classifier_for_tests()
        get_classifier().ensure_loaded()
        assert get_classifier().model_version() == EMBEDDED_MODEL_VERSION
