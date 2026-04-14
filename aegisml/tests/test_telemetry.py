"""OTLP gate and env behavior for ``app.observability.telemetry``."""

from __future__ import annotations

import pytest
from app.observability.telemetry import _otlp_trace_export_configured


@pytest.mark.parametrize(
    ("traces_ep", "base_ep", "expected"),
    [
        ("http://collector:4318/v1/traces", "", True),
        ("", "http://collector:4318", True),
        ("  ", "  ", False),
        ("", "", False),
    ],
)
def test_otlp_trace_export_configured(
    monkeypatch: pytest.MonkeyPatch,
    traces_ep: str,
    base_ep: str,
    expected: bool,
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    if traces_ep:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", traces_ep)
    if base_ep:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", base_ep)
    assert _otlp_trace_export_configured() is expected
