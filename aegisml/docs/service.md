# AegisML inference service

## Layout

| Path | Responsibility |
|------|----------------|
| `app/main.py` | FastAPI app factory wiring, lifespan (model load), observability hooks |
| `app/config.py` | `Settings.from_env()` — host, port, log level, service name |
| `app/deployment.py` | Version / environment / git SHA for logs and `aegisml_app_info` |
| `app/api/routes.py` | HTTP routes only |
| `app/schemas/` | Pydantic request/response models |
| `app/inference/` | sklearn pipeline; no HTTP or env reads |
| `app/dependencies.py` | `Depends` bindings for the classifier singleton |
| `app/observability/` | Prometheus metrics middleware; optional OTLP when `[otel]` installed |
| `app/error_handlers.py` | Structured JSON errors (`ErrorResponse`) for validation, inference, HTTP, and uncaught exceptions |

## Model lifecycle

The `TicketClassifier` singleton is created via `get_classifier()`. `lifespan` runs `ensure_loaded()` once at startup so the TF–IDF + logistic pipeline is fit before traffic. `/readyz` returns 503 with `{"error":{"code":"model_not_ready",...}}` if the injected classifier reports `is_ready` false (abnormal if startup completed).

## Endpoints

- `GET /healthz` — process up (kube liveness)
- `GET /readyz` — model loaded (kube readiness)
- `GET /metrics` — Prometheus text exposition
- `POST /predict` — JSON `{ "text": "..." }` → label + probabilities

## Determinism

Training data and `LogisticRegression(random_state=42)` are fixed so inference is reproducible for a given build. `/predict` returns `scores` with keys sorted alphabetically for stable JSON.

## Errors

Responses use `app/schemas/errors.py`: `{"error": {"code", "message", "detail?"}}`. Validation failures return 422; inference failures return 500 with `InferenceError` codes; unexpected server faults return 500 with `internal_error` (no stack trace in the body).

## Configuration

See `app/config.py` and `app/deployment.py` for environment variables. Secrets do not belong in env for this service’s current surface; use Kubernetes Secrets and mount or inject via your platform if you add API keys later.
