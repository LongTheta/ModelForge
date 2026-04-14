# Engineering expectations

This repository is maintained for production use. Conventions below keep behavior predictable for operators and reviewers.

## Priorities

1. **Correctness** — Policy verdicts and CI exit codes must match documented rules. Tests should fail when contracts break.
2. **Maintainability** — Prefer small, explicit modules over layers of indirection. Name functions and variables after what they do.
3. **Security** — No secrets in git. Dependencies and images are scanned in CI; turning on strict failure modes (`PIP_AUDIT_STRICT`, `TRIVY_FAIL_ON_SEVERITY`) is a team decision once noise is acceptable.
4. **Operability** — Health and readiness endpoints must reflect real state. Logs and metrics should identify version and deployment context.
5. **Observability** — Prometheus metrics on `/metrics`; optional OTLP when configured. Scrapes must not distort primary HTTP metrics.
6. **Deployment readiness** — Manifests and CI should be valid (`kubectl apply --dry-run=client` in CI). Document known gaps in `production-readiness.md`.

## Determinism

- **Policy enforcement** for pass/fail is deterministic (scripted checks, explicit severities). Retrieval and optional agents are supplementary unless governance says otherwise—document any exception.
- **Builds** should be reproducible for a given commit: pinned base images in Dockerfiles, versioned dependencies in `pyproject.toml` / lockfiles where used.

## Documentation

- Write for **operators and engineers**: how to run, configure, deploy, and troubleshoot. Avoid aspirational claims; state what exists and what does not.
- **README files** in each major directory should describe layout and entrypoints, not marketing copy.
- **Large design decisions** belong in `docs/` with enough context for the next maintainer—no duplicate essays across files.

## Code style

- **Python:** Ruff (lint + format) as in CI. Type hints where they catch real errors.
- **YAML:** Valid Kubernetes and GitLab CI; run kustomize render in CI before merge.
- **Naming:** `snake_case` for Python; resource names follow Kubernetes conventions in manifests.

## What to avoid

- Abstractions that exist only to shorten line count or “future-proof” without a concrete second use case.
- Silent failure in policy or security paths—prefer explicit exit codes and artifacts (`policy-findings.json`, agent JSON).
- Changing verdict logic inside enrichment or retrieval code paths.

## Reviews

- Security-sensitive changes: manifests, CI, Dockerfile, dependency bumps, anything touching auth or policy scripts.
- Breaking API or probe behavior: coordinate with anyone consuming `/predict`, `/healthz`, `/readyz`, `/metrics`.
