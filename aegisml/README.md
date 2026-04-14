# AegisML

HTTP inference service (FastAPI + scikit-learn) with CI policy checks, container image, and Kubernetes manifests. Repository layout is oriented toward GitLab CI and GitOps.

## Layout

| Path | Role |
|------|------|
| `app/` | API, config, inference pipeline, observability hooks |
| `src/retrieval/` | Optional Chroma-backed RAG for policy enrichment |
| `scripts/` | `policy_check.py` (deterministic CI rules) |
| `policies/` | Policy configuration consumed by the script |
| `k8s/` | Kustomize base + dev/prod overlays |
| `docker/` | Production-oriented Dockerfile |
| `tests/` | Pytest |
| `docs/` | Architecture and service notes |

## Requirements

- Python **3.10+**
- Docker (optional; for image build/run targets)

## Local development

From this directory (`aegisml/`):

```bash
make install
make lint
make test
make run
```

- API: `http://127.0.0.1:8080` — OpenAPI at `/docs`.
- Health: `GET /healthz`, readiness: `GET /readyz`, metrics: `GET /metrics`.

## Container

```bash
make docker-build
make docker-run
```

Build context is **this directory** (same as GitLab Kaniko). Override image name: `make docker-build DOCKER_IMAGE=registry.example.com/aegisml:dev`.

## Configuration

Environment variables are documented in `app/config.py` and `app/deployment.py`. Optional OpenTelemetry: `pip install -e ".[otel]"` and set `OTEL_EXPORTER_OTLP_ENDPOINT`.

## CI/CD

Parent repository `.gitlab-ci.yml` includes `.gitlab/ci/*.yml` (lint → test → build → security). See `../.gitlab/README.md`.

## Policy

```bash
make install
python scripts/policy_check.py
```

Writes `policy-findings.json` in this tree (gitignored). Exit non-zero on high/critical findings per `policies/policy-config.yaml`.

## Further reading

- `docs/architecture.md` — components, request path, dependencies, integration points
- `docs/service.md` — HTTP surface and model lifecycle
