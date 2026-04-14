"""
Prometheus text exposition on ``GET /metrics`` (``prometheus_client``).

HTTP RED-style signals (low-cardinality ``path`` labels for this API’s fixed routes):
  - ``aegisml_http_requests_total`` — Counter(method, path, status)
  - ``aegisml_http_request_duration_seconds`` — Histogram(method, path)
  - ``aegisml_http_errors_total`` — Counter(class) with class 4xx|5xx

Scrapes of ``/metrics`` are not recorded (avoids self-inflating request/latency series).

Optional OTLP tracing when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set and ``[otel]`` extras installed.
"""

from __future__ import annotations

import logging
import os
import time

from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, Info, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from app.deployment import DeploymentMeta

logger = logging.getLogger(__name__)

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
    "Unix time when this process registered deployment metadata (useful for rollout correlation per replica)",
)


def _label_or_na(value: str) -> str:
    return value if value.strip() else "n/a"


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
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
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
            "OTEL_EXPORTER_OTLP_ENDPOINT set but OpenTelemetry is not installed; "
            'use pip install -e ".[otel]"'
        )
        return

    meta_ver = os.getenv("AEGISML_VERSION", "0.2.0")
    meta_env = os.getenv("AEGISML_ENVIRONMENT") or os.getenv("AEGISML_DEPLOYMENT", "local")
    meta_sha = os.getenv("AEGISML_GIT_COMMIT") or os.getenv("CI_COMMIT_SHORT_SHA", "unknown")
    pod = os.getenv("POD_NAME", "")
    ns = os.getenv("POD_NAMESPACE", "")
    attrs: dict[str, str] = {
        "service.name": os.getenv("OTEL_SERVICE_NAME", "aegisml-inference"),
        "service.version": meta_ver,
        "deployment.environment": meta_env,
        "git.commit.sha": meta_sha,
    }
    if pod:
        attrs["k8s.pod.name"] = pod
    if ns:
        attrs["k8s.namespace.name"] = ns
    resource = Resource.create(attrs)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    logger.info("OpenTelemetry FastAPI instrumentation enabled")
