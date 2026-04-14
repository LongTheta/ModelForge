# Production readiness (MVP checklist)

| Area | Status | Notes |
|------|--------|--------|
| Health probes | Done | `/healthz` liveness, `/readyz` readiness |
| Metrics | Done | Prometheus text at `/metrics`; Service annotations for scraping |
| Container | Done | Non-root user, slim base, tini, healthcheck in Dockerfile |
| Supply chain | Partial | pip-audit + Trivy in CI; pin versions in overlays/registry |
| GitOps | Partial | Kustomize overlays; replace `registry.example.com` with your registry |
| Policy | Partial | Deterministic CI checks; optional external agent |
| OTEL | Optional | Install `.[otel]` and set OTLP endpoint |
| DR / SLO | Future | Define SLOs on latency and error ratio from Grafana panels |

Before production: enforce `PIP_AUDIT_STRICT` and `TRIVY_FAIL_ON_SEVERITY`, wire secrets via ExternalSecrets/Vault, and run the full policy agent against pipelines and manifests.
