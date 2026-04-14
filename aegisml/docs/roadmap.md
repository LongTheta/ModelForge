# Roadmap — AegisML

This document outlines plausible next steps after the current MVP: inference HTTP service, deterministic `policy_check.py`, optional Chroma-backed retrieval enrichment, GitLab CI for lint/test/build/security, and sample Kubernetes manifests. Items are grouped into phases that can be executed largely in order; later phases assume baseline CI and cluster ownership exist.

Nothing here is a commitment. Scope and priority depend on product and operational constraints.

---

## Phase 1 — Deployment automation

**Current state:** CI builds and pushes a container image (Kaniko) and records a digest artifact. There is no first-party deploy job; clusters are assumed external.

**Realistic work:**

- GitLab deploy jobs (or equivalent) parameterized by environment, image tag/digest, and target namespace—using protected branches or manual gates where appropriate.
- Injection of runtime config via ConfigMaps/Secrets already referenced in `k8s/base/deployment.yaml` (`aegisml-config`, `aegisml-secrets`); document and automate secret provisioning (External Secrets Operator, Vault Agent, or CI-generated sealed secrets—choose one pattern per environment).
- Smoke checks post-deploy (`scripts/smoke-test.sh` against service URL) as an automated step or child pipeline.
- Image promotion flow: immutable tags per SHA, optional `-latest` only for non-prod if policy allows.

**Out of scope for this phase:** Full environment parity matrices; start with one non-prod and one prod pattern.

---

## Phase 2 — GitOps controller integration

**Current state:** Kustomize overlays under `k8s/overlays/` and an example Argo CD `Application` manifest under `k8s/argo/application-example.yaml`.

**Realistic work:**

- Turn the example into a documented pattern: repo URL, path, target revision, sync policy (manual vs automated), retry/backoff, and health checks tied to Deployment readiness (already uses `/readyz`).
- Add ignore differences or replace directives only where required (e.g. image tags updated by CI).
- Optional: ApplicationSet or per-environment folders if multiple clusters are in play.
- Define who owns rollback: revert Git vs `kubectl rollout undo` vs Argo “History and rollback.”

**Dependency:** Phase 1 clarity on image coordinates and secrets; GitOps only applies manifests that are already safe to sync.

---

## Phase 3 — Tracing

**Current state:** OpenTelemetry is optional (`pip install -e ".[otel]"` and `OTEL_EXPORTER_OTLP_ENDPOINT`). HTTP metrics are always on via Prometheus.

**Realistic work:**

- Standardize resource attributes: service name, version, deployment environment, `k8s.pod.name` / namespace (partially wired via `app/deployment.py` and OTel setup).
- Sampling strategy for production (e.g. head-based 1–10% for success paths, higher for errors) to control collector and storage cost.
- Trace context propagation from ingress/load balancer if the platform supports W3C `traceparent` injection.
- Dashboards: latency breakdown by span vs existing `aegisml_http_request_duration_seconds`—avoid duplicating the same signal without purpose.

**Non-goals:** Tracing every sklearn internal call; keep spans at HTTP and major application boundaries unless profiling demands more.

---

## Phase 4 — Richer model evaluation

**Current state:** sklearn `Pipeline` (TF–IDF + logistic regression); tests cover API contracts and health, not model quality benchmarks.

**Realistic work:**

- Offline evaluation harness: fixed train/val/test split or time-based split for ticket-like data; report precision/recall/F1 per class, calibration if probabilities are consumed downstream.
- Versioned training artifacts: store hash or path of training snapshot in model metadata; surface via `/status` or metrics (`model_version` already has a hook in code paths).
- Regression gates in CI: block promotion when metrics drop below thresholds on a reference dataset (artifact-stored, not necessarily in git LFS for small corpora).
- Optional: shadow deployment or A/B at the routing layer—only if product requires it; adds operational complexity.

**Constraint:** Any model swap (e.g. larger classifier) should preserve the existing JSON API contract unless versioning the API explicitly.

---

## Phase 5 — Stronger policy coverage

**Current state:** `scripts/policy_check.py` encodes a finite set of rules over Kubernetes manifests and GitLab CI; optional `POLICY_AGENT_PACKAGE` adds an external agent review with `policy_agent_gate.py`.

**Realistic work:**

- Extend deterministic rules where gaps are known (additional manifest paths, stricter GitLab CI patterns, registry references).
- Align terminology with organizational policy: map findings to the same control IDs used in SSP or OSCAL exports where applicable.
- Optional integration with admission or CI policy engines (Kyverno, OPA Gatekeeper, Conftest bundles) **as additional** signals—keep deterministic repo checks for developer feedback without requiring a cluster for every MR.
- CI defaults: set `PIP_AUDIT_STRICT` / `TRIVY_FAIL_ON_SEVERITY` to `true` in protected pipelines once noise is manageable.

**Principle:** Deterministic checks remain the baseline for predictable pass/fail; agents and LLM-assisted reviews stay supplementary unless governance mandates otherwise.

---

## Phase 6 — Retrieval knowledge expansion

**Current state:** JSON knowledge base under `knowledge_base/samples/`, Chroma ingestion via `src/retrieval/ingest_kb.py`, enrichment after policy findings. No retrieval on the live inference path.

**Realistic work:**

- Grow curated documents per `doc_type` (policy explanation, remediation, compliance mapping, secure CI/CD and Kubernetes patterns); keep `filters` aligned with how `enrich.py` infers metadata from findings.
- Periodic re-ingest job or pipeline step when KB changes; document `AEGISML_CHROMA_PATH` and collection naming for shared vs per-environment indexes.
- Lightweight quality checks: manual review of top-k for representative findings; optional golden-query list (scripted) to assert non-empty retrieval for critical rules.
- If corpus grows large: evaluate whether `doc_type` or additional metadata should become query filters (today enrichment uses finding-derived `where` with fallbacks).

**Constraint:** Retrieval remains non-authoritative for enforcement; expansion must not blur that line.

---

## Phase 7 — Authentication and authorization integration

**Current state:** Inference API has no built-in API keys, JWT validation, or mTLS; suitable only for trusted network boundaries.

**Realistic work:**

- Edge authentication: terminate TLS and validate JWT/OIDC at ingress (preferred) or API gateway; pass identity as headers only if trust model is explicit.
- Service-to-service: mTLS or mesh identity (SPIFFE) if the inference service is called from other workloads in-cluster.
- Application-level option: FastAPI dependency for bearer token validation against an IdP JWKS—only if ingress cannot enforce policy.
- Authorization: map claims to allowed operations (e.g. predict vs admin); rate limiting per client at gateway.

**Ordering:** Usually after Phase 1–2 so TLS endpoints and stable service names exist; otherwise keys and issuers churn during bring-up.

---

## Explicit non-goals (near term)

- Multi-tenant model serving with per-tenant isolation guarantees.
- Real-time drift detection and automatic retraining pipelines.
- Feature stores and online serving unless product scope expands materially.

These add significant data and MLOps surface area relative to the current codebase.

---

## Related documentation

| Topic | Document |
|-------|----------|
| What exists today | `docs/architecture.md`, `docs/production-readiness.md` |
| Application layout | `docs/application-structure.md` |
| Knowledge base | `knowledge_base/README.md` |
