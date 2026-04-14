# GitLab CI — AegisML

Entrypoint: `/.gitlab-ci.yml` → includes under `.gitlab/ci/`.

## Stages

| Stage | Purpose |
|-------|---------|
| **lint** | Ruff check + format check on `app/`, `src/`, `tests/` |
| **test** | pytest (coverage, JUnit), kubectl kustomize render + client dry-run |
| **build** | Kaniko push to `$CI_REGISTRY_IMAGE`; `aegisml/image.digest` artifact |
| **security** | pip-audit, Trivy FS, Trivy image scan, deterministic `policy_check.py` |
| **policy_check** | AI DevSecOps Policy Enforcement Agent (`review-all` on pipeline + `aegisml/k8s`) |

## Jobs (by file)

| File | Job | Notes |
|------|-----|--------|
| `lint.yml` | `lint:ruff` | Gates style before tests |
| `test.yml` | `test:pytest` | Cobertura + JUnit artifacts |
| `test.yml` | `test:kustomize` | Rendered YAML under `aegisml/.rendered/` |
| `build.yml` | `build:kaniko` | Tags: `$AEGISML_IMAGE_NAME-$CI_COMMIT_SHORT_SHA`, `$AEGISML_IMAGE_NAME-latest`; digest file for promotion traceability |
| `security.yml` | `security:pip-audit` | JSON artifact; strict mode via `PIP_AUDIT_STRICT` |
| `security.yml` | `security:trivy-fs` | Repo tree scan |
| `security.yml` | `security:trivy-image` | Registry image scan |
| `security.yml` | `security:policy` | `aegisml/policy-findings.json` (deterministic script) |
| `policy_check.yml` | `policy_check:ai-devsecops` | Runs when `POLICY_AGENT_PACKAGE` is set; gate: `aegisml/scripts/policy_agent_gate.py` |

## Variables

| Variable | Default | Effect |
|----------|---------|--------|
| `AEGISML_IMAGE_NAME` | `aegisml` | Kaniko destination tag prefix |
| `AEGISML_CI_ENVIRONMENT` | `ci` | OCI label `ci.environment` (placeholder for env promotion) |
| `PIP_AUDIT_STRICT` | `false` | `true` → fail pip-audit on findings |
| `TRIVY_FAIL_ON_SEVERITY` | `false` | `true` → fail Trivy on `TRIVY_SEVERITY` |
| `POLICY_AGENT_PACKAGE` | unset | pip install spec for AI policy agent; **if set**, `policy_check:ai-devsecops` runs |
| `POLICY_CHECK_FAIL_SEVERITIES` | `high,critical` | Finding severities that fail the job (also fails if `verdict` is `fail`) |

Built-in: `CI_REGISTRY_*`, `CI_COMMIT_SHORT_SHA`, `CI_COMMIT_TAG`.

## policy_check artifacts

On each run (when enabled), see **`artifacts/policy-check/`** (layout: `aegisml/examples/policy-check-artifact-layout.txt`):

- `review-result.json` — machine-readable verdict + findings (examples: `aegisml/examples/policy-check-review-result.example.json`, `policy-check-review-result-fail.example.json`)
- `policy-check-summary.md` — human-readable Markdown (also printed to job log, first ~120 lines)
- Other agent outputs (`report.md`, etc.) when the agent version emits them

The job **fails** if `verdict == "fail"` **or** any finding has **`severity`** `high` or `critical`.

## Future deployment

Use `AEGISML_IMAGE_NAME` and `CI_COMMIT_TAG` / environment-scoped variables to map images to `dev` / `staging` / `prod`. Add `deploy:*` jobs in a new stage after `security`, reuse the same image reference and `needs` the image scan + policy jobs.
