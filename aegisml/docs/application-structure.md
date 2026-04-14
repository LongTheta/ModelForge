# AegisML service layout

## Directory tree (`aegisml/`)

```text
app/
  __init__.py          # package version
  __main__.py          # uvicorn entry (reads Settings from env)
  main.py              # FastAPI app factory, lifespan, middleware wiring
  config.py            # Settings (frozen dataclass, from_env)
  deployment.py        # DeploymentMeta for logs / metrics / OTel resource
  dependencies.py      # FastAPI Depends() for TicketClassifier
  exceptions.py        # InferenceError → structured 500
  error_handlers.py    # Validation and unhandled exception mapping
  api/
    routes.py          # aggregates routers
    health.py          # GET /healthz, /readyz, /metrics
    predict.py         # POST /predict
  inference/
    classifier.py      # load-once sklearn pipeline; thread-safe singleton
  observability/
    telemetry.py       # Prometheus metrics; optional OTLP when endpoint set
  schemas/             # Pydantic request/response and error models
tests/                 # pytest + httpx TestClient
docs/                  # service and architecture notes
requirements.txt       # mirrors runtime + dev deps (see pyproject.toml for extras)
```

## Design

| Concern | Approach |
|---------|----------|
| **Config** | `Settings.from_env()` — no secrets in code; bind address and log level only at this layer. |
| **Inference** | Eager load in lifespan (`ensure_loaded`); `readyz` reflects load state for kube probes. |
| **Determinism** | Fixed `random_state` in training data fit; same binary → same predictions for same input. |
| **Observability** | `prometheus_client` on `/metrics` (request count, latency histogram, 4xx/5xx class); scrape path excluded from HTTP metrics. OTel traces only with `OTEL_EXPORTER_OTLP_ENDPOINT` + `pip install -e ".[otel]"`. |
| **Errors** | Validation → 422 with stable `error.code`; inference failures → 500 with `InferenceError` code. |

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/healthz` | Liveness: process up (no model check). |
| GET | `/status` | Version, environment, Git SHA, service name, model version, pod/namespace (ops metadata). |
| GET | `/readyz` | Readiness: model loaded; 503 until `ensure_loaded` completes. |
| GET | `/metrics` | Prometheus text exposition. |
| POST | `/predict` | JSON `{ "text": "..." }` → label + probabilities. |

## Run

```bash
cd aegisml && pip install -e .
python -m app
```

Override host/port: `AEGISML_HOST`, `AEGISML_PORT`, `AEGISML_LOG_LEVEL`.

**Inference:** Default embedded TF-IDF + logistic regression is fitted once at startup (`lifespan` → `TicketClassifier.ensure_loaded`). Optional production path: set `AEGISML_MODEL_PATH` to a `joblib`-serialized sklearn `Pipeline` with `predict_proba`; optional `AEGISML_MODEL_VERSION` labels responses. `AEGISML_SKLEARN_RANDOM_STATE` (default `42`) controls the embedded fit only.
