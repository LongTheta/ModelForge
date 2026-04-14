"""
Prometheus text exposition on ``GET /metrics`` (``prometheus_client``).

HTTP RED-style signals (low-cardinality ``path`` labels for this API’s fixed routes):
  - ``aegisml_http_requests_total`` — Counter(method, path, status)
  - ``aegisml_http_request_duration_seconds`` — Histogram(method, path)
  - ``aegisml_http_errors_total`` — Counter(class) with class 4xx|5xx

Scrapes of ``/metrics`` are not recorded (avoids self-inflating request/latency series).

Optional OTLP tracing when standard OTel env vars are set and ``[otel]`` extras are installed.
Do **not** pass a raw ``OTEL_EXPORTER_OTLP_ENDPOINT`` into ``OTLPSpanExporter(endpoint=...)``:
the HTTP exporter appends ``/v1/traces`` only when it reads the env itself; an explicit
``endpoint`` argument is used as-is and breaks collectors that expect the default path.
"""

from __future__ import annotations

import atexit
import logging
import os
import time
from typing import Any

from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, Info, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from app.deployment import DeploymentMeta, get_deployment_meta

logger = logging.getLogger(__name__)

_otel_tracer_provider: Any = None  # TracerProvider when OTLP enabled; shutdown flushes spans
_otel_atexit_registered = False

HTTP_REQUESTS = Counter(
    "aegisml_http_requests_total",
    "Total HTTP requests",
    ("method", "path", "status"),
)

HTTP_REQUEST_DURATION = Histogram(
    "aegisml_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# Aggregated 4xx/5xx counts (low-cardinality) — complements per-status ``HTTP_REQUESTS``.
HTTP_ERRORS = Counter(
    "aegisml_http_errors_total",
    "HTTP responses with status 4xx or 5xx",
    ("class",),
)

PREDICTIONS_TOTAL = Counter(
    "aegisml_predictions_total",
    "Prediction requests",
    ("outcome",),
)

INFERENCE_SECONDS = Histogram(
    "aegisml_inference_seconds",
    "Model inference duration",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

APP_INFO = Info(
    "aegisml_app",
    "Build and deployment metadata (labels align with startup JSON logs)",
)

PROCESS_START = Gauge(
    "aegisml_process_start_timestamp_seconds",
    "Unix time when this process registered deployment metadata (rollout correlation per replica)",
)


def _label_or_na(value: str) -> str:
    return value if value.strip() else "n/a"


def _otlp_trace_export_configured() -> bool:
    """True if env indicates OTLP HTTP trace export (standard OTel variables)."""
    return bool(
        os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    )


def set_deployment_metadata(meta: DeploymentMeta) -> None:
    """Register once at startup: Info labels + process start time for SRE correlation."""
    APP_INFO.info(
        {
            "service": meta.service_name,
            "version": meta.version,
            "environment": meta.environment,
            "git_commit": meta.git_commit,
            "pod": _label_or_na(meta.pod_name),
            "namespace": _label_or_na(meta.pod_namespace),
        }
    )
    PROCESS_START.set(time.time())


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def setup_http_metrics(app: FastAPI) -> None:
    @app.middleware("http")
    async def observe_http(request: Request, call_next):
        path = request.url.path
        if path == "/metrics":
            return await call_next(request)
        method = request.method
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - start
            HTTP_REQUESTS.labels(method, path, str(status)).inc()
            HTTP_REQUEST_DURATION.labels(method, path).observe(elapsed)
            if status >= 500:
                HTTP_ERRORS.labels("5xx").inc()
            elif status >= 400:
                HTTP_ERRORS.labels("4xx").inc()


def setup_opentelemetry(app: FastAPI) -> None:
    global _otel_tracer_provider, _otel_atexit_registered
    if not _otlp_trace_export_configured():
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "OTLP trace export configured in env but OpenTelemetry is not installed; "
            'use pip install -e ".[otel]"'
        )
        return

    meta = get_deployment_meta()
    attrs: dict[str, str] = {
        "service.name": meta.service_name,
        "service.version": meta.version,
        "deployment.environment": meta.environment,
        "git.commit.sha": meta.git_commit_full,
    }
    if meta.pod_name:
        attrs["k8s.pod.name"] = meta.pod_name
    if meta.pod_namespace:
        attrs["k8s.namespace.name"] = meta.pod_namespace
    resource = Resource.create(attrs)
    provider = TracerProvider(resource=resource)
    # No ``endpoint=`` — exporter reads OTEL_EXPORTER_OTLP_* and appends /v1/traces to the base URL.
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    _otel_tracer_provider = provider
    if not _otel_atexit_registered:
        atexit.register(_shutdown_otel_tracer_provider)
        _otel_atexit_registered = True
    FastAPIInstrumentor.instrument_app(app)
    logger.info("OpenTelemetry FastAPI instrumentation enabled")


def _shutdown_otel_tracer_provider() -> None:
    global _otel_tracer_provider
    if _otel_tracer_provider is not None:
        _otel_tracer_provider.shutdown()
        _otel_tracer_provider = None
