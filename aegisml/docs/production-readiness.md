# Production readiness — AegisML

This document describes what the repository implements today: health semantics, probes, resources, CI gates, policy enforcement, observability, rollback-related Kubernetes behavior, and gaps. It is scoped to the inference HTTP service (`app/`), container image (`docker/`), manifests (`k8s/`), and the GitLab CI under `.gitlab/ci/`.

---

## Service health expectations

- **Process availability:** The HTTP server is considered up for **liveness** if it responds successfully on `GET /healthz`. That endpoint does **not** load the classifier or block on model state; it only confirms the FastAPI process is serving.
- **Traffic readiness:** Endpoints that perform inference depend on the classifier being loaded during application lifespan (`get_classifier().ensure_loaded()` in `app/main.py`). **Readiness** for Kubernetes is `GET /readyz`, which returns **503** with `model_not_ready` until `ClassifierDep` reports `is_ready`.
- **Operational detail:** `GET /status` returns version, environment, git commit (when env vars are set), and model version when loaded. Use it for debugging and correlation; it is not a substitute for probe semantics.

**Implication:** A pod can pass liveness while still failing readiness during startup or if the model enters a bad state after load (the current code does not flip `is_ready` back to false after successful load).

---

## Readiness and liveness behavior

| Probe | Path | HTTP success | Meaning in code |
|-------|------|----------------|-----------------|
| **Startup** | `/readyz` | 200 | Classifier finished loading (within startup window). |
| **Readiness** | `/readyz` | 200 | Same check; pod receives traffic when ready. |
| **Liveness** | `/healthz` | 200 | Process responding; no model check. |

**Base Deployment** (`k8s/base/deployment.yaml`):

- **Startup:** `periodSeconds: 3`, `failureThreshold: 20`, `timeoutSeconds: 3` (~60s max before Kubernetes marks startup failed).
- **Readiness:** `periodSeconds: 10`, `failureThreshold: 3`, `timeoutSeconds: 3`.
- **Liveness:** `initialDelaySeconds: 15`, `periodSeconds: 20`, `failureThreshold: 3`, `timeoutSeconds: 3`.

**Docker Compose / Dockerfile:** Healthcheck uses `/healthz` only (liveness-style), not `/readyz`.

**Metrics:** Requests to `GET /metrics` are excluded from HTTP request/latency counters so Prometheus scrapes do not inflate traffic metrics (`app/observability/telemetry.py`).

---

## Resource assumptions

**Default container resources** (base Deployment):

| | CPU | Memory |
|---|-----|--------|
| **Requests** | 100m | 256Mi |
| **Limits** | 1 | 512Mi |

These values are a starting point for a small TF–IDF + logistic inference workload. They are not validated against peak load or large batch requests in this repo. Adjust per environment after measuring CPU during cold start, steady-state QPS, and memory with your model artifact size.

**Storage:** `readOnlyRootFilesystem: true` with an `emptyDir` mount at `/tmp` for writable temporary data.

**Replicas:** Base manifest sets `replicas: 1`. No HorizontalPodAutoscaler is defined in-tree.

---

## CI/CD quality gates

Pipeline stages (see root `.gitlab-ci.yml` and `.gitlab/ci/*.yml`):

| Stage | Jobs | Failure effect |
|-------|------|----------------|
| **lint** | `ruff check`, `ruff format --check` on `app`, `src`, `tests` | Pipeline fails; no later stages unless rules allow. |
| **test** | Pytest with coverage (`app`, `src/retrieval`); JUnit + Cobertura artifacts | Fails on test failure. |
| **test** | `kubectl kustomize` for `k8s/overlays/dev` and `prod` + `kubectl apply --dry-run=client` | Fails on invalid manifests. |
| **build** | Kaniko build and push image (+ digest artifact) | Fails on build error. |
| **security** | pip-audit (JSON artifact), Trivy filesystem, Trivy image (after build) | See [Policy enforcement](#policy-enforcement-gates) for when these block. |

**Strict security toggles** (`.gitlab/ci/variables.yml` defaults both to non-blocking):

- `PIP_AUDIT_STRICT=true` — pip-audit non-zero exit fails the job.
- `TRIVY_FAIL_ON_SEVERITY=true` — Trivy uses exit code 1 on configured severities (`TRIVY_SEVERITY`, default `HIGH,CRITICAL`).

There is **no** deploy stage in the included CI: promotion to clusters is assumed to be external (e.g. Argo CD using `k8s/`; see `k8s/argo/application-example.yaml` as a template).

---

## Policy enforcement gates

Two layers:

### 1. Deterministic AegisML policy script (`security:policy`)

- Runs `aegisml/scripts/policy_check.py` against `policies/policy-config.yaml`, Kubernetes manifests under `aegisml/k8s`, and GitLab CI content as implemented in the script.
- Exit code **non-zero** when computed `verdict` is `fail` (high/critical severities in raw findings). Produces `aegisml/policy-findings.json`.
- Retrieval-based enrichment runs **after** verdict computation when imports succeed; it does not change pass/fail.

### 2. Optional AI DevSecOps agent (`policy_check:ai-devsecops`)

- Runs only when `POLICY_AGENT_PACKAGE` is set (see `.gitlab/ci/policy_check.yml`).
- Invokes `ai_devsecops_agent.cli review-all` on `.gitlab-ci.yml` and `aegisml/k8s`, writes artifacts under `artifacts/policy-check/`.
- Optional enrichment of `review-result.json` via `aegisml/scripts/enrich_review_result.py`.
- **`aegisml/scripts/policy_agent_gate.py`** exits **1** if `review-result.json` has `verdict == "fail"` **or** any finding whose severity is in `POLICY_CHECK_FAIL_SEVERITIES` (default `high,critical`).

**Operational note:** If `POLICY_AGENT_PACKAGE` is unset, the `policy_check` stage is skipped entirely; only the deterministic script enforces repo policy in CI.

---

## Observability baseline

**Metrics (in-process):**

- Prometheus text on **`GET /metrics`** (`prometheus_client`).
- Counters/histograms for HTTP requests, latency, error classes; `aegisml_app_info` for version, environment, git commit, pod/namespace when set; process start timestamp.
- Service `Service` manifest includes `prometheus.io/scrape`, `port`, `path` annotations (`k8s/base/service.yaml`).

**Reference configs:** `aegisml/observability/prometheus.yaml` and `aegisml/observability/grafana-dashboard.json` — import paths assume scraping the app (e.g. port 8080). No Prometheus or Grafana is deployed by this repository.

**Logs:** Structured JSON line on startup (`event=service_start`) with version, environment, git fields, optional pod/namespace (`app/deployment.py`).

**Tracing:** OpenTelemetry is wired only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set and the optional extra `pip install -e ".[otel]"` is used (`app/observability/`). Not part of the default image behavior unless you add it.

---

## Deployment rollback expectations

**What the repo defines:**

- **RollingUpdate** with `maxUnavailable: 0`, `maxSurge: 1`, `progressDeadlineSeconds: 600`, `revisionHistoryLimit: 5` (`k8s/base/deployment.yaml`).
- Failed rollouts surface as Deployment conditions and ReplicaSet state; Kubernetes will leave the previous ReplicaSet in place when the new revision does not become ready within the deadline.

**What the repo does not define:**

- Automated rollback jobs, canary analysis, or GitOps sync policies. Those are platform-specific (e.g. Argo Rollouts, manual `kubectl rollout undo`, or Git revert + sync).

**Practical rollback:** Use cluster tooling to roll back to the previous ReplicaSet or re-point the Deployment image to a known-good digest. The image build writes `aegisml/image.digest` in CI artifacts for traceability.

---

## Known limitations of the current implementation

- **Single-replica default:** No HA or pod-disruption guarantees in base manifests; scale and PDBs are operator-owned.
- **Classifier readiness:** `/readyz` does not re-check model health on every request; long-running degradation is not automatically reflected in readiness after initial load.
- **Resource limits:** Default CPU/memory are not benchmarked in CI; production sizing requires measurement.
- **Policy coverage:** Deterministic checks are a fixed set in `policy_check.py`; they do not cover every GitOps or runtime risk. The optional agent adds breadth but depends on `POLICY_AGENT_PACKAGE` and third-party behavior.
- **Retrieval / Chroma:** Enrichment depends on optional `chromadb`, index contents, and env vars (`AEGISML_CHROMA_PATH`, `AEGISML_DISABLE_RETRIEVAL`). Empty or missing KB yields stub or empty explanations without failing policy verdict.
- **No in-repo production deploy:** CI builds and scans the image; cluster deployment, secrets (e.g. `aegisml-secrets`), and ingress are not fully specified here.
- **Security scans default to non-fatal:** `PIP_AUDIT_STRICT` and `TRIVY_FAIL_ON_SEVERITY` default to `false`; pipelines can pass with known-vulnerable dependencies or image findings until you enable strict mode.
- **Windows vs Linux:** CI and container paths assume Linux; local development on Windows may differ (paths, optional tools).

---

## Related paths

| Topic | Location |
|-------|----------|
| Probe handlers | `aegisml/app/api/health.py` |
| Metrics | `aegisml/app/observability/telemetry.py` |
| Base Deployment | `aegisml/k8s/base/deployment.yaml` |
| CI includes | `.gitlab/ci/*.yml`, root `.gitlab-ci.yml` |
| Observability samples | `aegisml/observability/README.md` |
