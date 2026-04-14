# ModelForge / AegisML

FastAPI + scikit-learn inference service, GitLab CI (build/scan/policy), Kustomize manifests. **Policy pass/fail** is from `policy_check.py` and optional agent gate rules only; optional Chroma + KB enriches finding text after the verdict and does not change it.

**Stack:** Python 3.10+, Prometheus `/metrics`, OTLP traces via `[otel]` + env, Kaniko, Kubernetes.

---

## Architecture

```
CI (lint, test, build, scan, policy [+ optional agent]) --> image registry
                                                          |
Kustomize manifests (GitOps sync out of band) -----------> Pods: /predict, /healthz, /readyz, /metrics
```

`policy_check.py` runs in CI (and similar batch paths), not inside the inference request path.

---

## What ships here

| Area | Detail |
|------|--------|
| **Runtime** | `GET /healthz` (liveness), `GET /readyz` (model loaded), `POST /predict`, `GET /metrics` |
| **CI** | Ruff, pytest + coverage, `kubectl kustomize` + client dry-run, Kaniko push, pip-audit / Trivy (strict = CI vars), `security:policy` runs `policy_check.py` |
| **Policy** | `aegisml/scripts/policy_check.py` — deterministic over repo YAML / `.gitlab-ci.yml` patterns; `POLICY_AGENT_PACKAGE` enables separate agent job + `policy_agent_gate.py` |
| **RAG** | `aegisml/src/retrieval/`, `aegisml/knowledge_base/` — optional; requires `[retrieval]` and index ingest |
| **Deploy** | No deploy stage in this repo; sample `aegisml/k8s/` + `k8s/argo/application-example.yaml` |

---

## CI to cluster (short)

1. Merge triggers pipeline: lint → test → image build → security (including deterministic policy JSON).
2. Image tag + digest artifact; policy artifacts e.g. `aegisml/policy-findings.json`, optional `artifacts/policy-check/`.
3. Cluster rollout uses your process; pods expose metrics; OTLP if configured.

---

## Quick start

```bash
cd aegisml && make install && make lint && make test && make run
```

- `http://127.0.0.1:8080/docs` — probes and `/metrics` as above  
- Image: `make docker-build` / `make docker-run` (context = `aegisml/`)  
- Policy: `python scripts/policy_check.py` → `policy-findings.json` (gitignored); fails on high/critical per `policies/policy-config.yaml`  

Pipelines: root `.gitlab-ci.yml` → [`.gitlab/ci/`](.gitlab/README.md).

---

## Layout

| Path | Contents |
|------|----------|
| [`aegisml/`](aegisml/README.md) | `app/`, `tests/`, `docker/`, `k8s/`, `scripts/`, `policies/`, `knowledge_base/` |
| [`.gitlab/ci/`](.gitlab/README.md) | Job YAML, variables (`PIP_AUDIT_STRICT`, `TRIVY_FAIL_ON_SEVERITY`, `POLICY_AGENT_PACKAGE`, …) |
| `aegisml/docs/` | `architecture.md`, `production-readiness.md`, `engineering.md`, `roadmap.md` |

---

## Invariants

- Verdict for bundled rules does not depend on embeddings or LLMs.
- Metrics always on; traces and retrieval are optional extras.
- Dependency/image scan failure is opt-in (`variables.yml` defaults).
