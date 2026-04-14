# AegisML observability (minimal)

| File | Purpose |
|------|---------|
| **`prometheus.yaml`** | Scrape config: `job_name: aegisml` → `http://localhost:8080/metrics`. |
| **`grafana-dashboard.json`** | Import into Grafana; map datasource `DS_PROMETHEUS`. |

## Deployment tracking (SRE)

| Signal | Where | Use |
|--------|--------|-----|
| **version** | `aegisml_app_info{version="..."}`, log `version` | Release / image tag. |
| **git commit** | `aegisml_app_info{git_commit="..."}`, logs `git_commit` + `git_commit_full` | Short SHA in labels; full SHA in logs when `AEGISML_GIT_COMMIT_FULL` or CI vars set. |
| **environment** | `aegisml_app_info{environment="..."}`, log `environment` | dev/staging/prod / overlay. |
| **Pod / namespace** | `aegisml_app_info{pod="...",namespace="..."}` (Kubernetes), logs `pod_name`, `pod_namespace` | Tie metrics to a replica; `n/a` when not in-cluster. |
| **Process start** | `aegisml_process_start_timestamp_seconds` | Approximate rollout time for **this** replica (compare with HTTP panels). |

**Correlate deployment → performance**

1. After a deploy, confirm **`aegisml_app_info`** (or logs `event=service_start`) shows the expected **version** and **git_commit**.
2. Note **`aegisml_process_start_timestamp_seconds`** (or log timestamp) as the cut-over for that pod.
3. On Grafana, compare **request rate**, **p95 latency**, and **5xx share** **before vs after** that time (or add CI/CD **annotations** at deploy time).
4. Multi-replica: each pod has its own **process start** and **pod** label — split or filter in Prometheus/Grafana if needed.

HTTP metrics stay **unlabeled by version** (low cardinality). Identity lives on **`aegisml_app_info`** + **structured logs** + optional **OpenTelemetry** resource (`k8s.pod.name`, `k8s.namespace.name` when `OTEL_EXPORTER_OTLP_ENDPOINT` is set).

## Metric quick reference

| Metric | Role |
|--------|------|
| `aegisml_http_requests_total` | Request rate; `method`, `path`, `status`. |
| `aegisml_http_request_duration_seconds` | Latency histogram. |
| `aegisml_http_errors_total` | `4xx` / `5xx`. |
| `aegisml_app_info` | Deployment labels (version, environment, git, pod, namespace). |
| `aegisml_process_start_timestamp_seconds` | Unix time at startup (per process). |
