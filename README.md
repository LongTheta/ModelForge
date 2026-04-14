# AegisML – Secure ML Delivery & Governance Platform

**Implementation (MVP):** the runnable service, CI/CD ([`.gitlab/README.md`](.gitlab/README.md)), Kubernetes manifests, policy scripts, and Grafana dashboard live under [`aegisml/`](aegisml/README.md).

## Overview

AegisML is a production-ready ML delivery platform that unifies secure development, automated policy enforcement, GitOps-based deployment, and full-stack observability. It is built for teams that need governed ML releases: deterministic gates in CI/CD, traceable decisions, and runtime visibility without trading velocity for control.

The platform treats ML services as first-class production workloads. Pipelines validate code and artifacts, an agent-driven policy layer blocks or gates non-compliant changes, and Argo CD promotes approved state to Kubernetes. OpenTelemetry and Grafana provide operational signals; retrieval-augmented context is used strictly to clarify findings and remediation paths, not to override policy outcomes.

## Architecture

```
Developer (code-server)
        |
        v
   GitLab CI/CD
        |
        v
 Policy Enforcement Agent
        |
        v
  Build / Test / Scan
        |
        v
    GitOps (Argo CD)
        |
        v
    Kubernetes
        |
        +-- ML Service
        |
        +-- Observability (metrics, traces, dashboards)
```

## Core Capabilities

- **Secure development environment** — Isolated, consistent workspaces (e.g. code-server) aligned with organizational baselines and secrets handling.
- **CI/CD for ML services (GitLab)** — Pipelines for build, test, containerization, and artifact promotion with versioned, repeatable stages.
- **Policy enforcement (agent-driven)** — Automated validation against security, compliance, and engineering rules; failures are explicit and actionable.
- **GitOps deployment** — Declarative cluster state; changes flow through review, merge, and sync with auditable promotion.
- **Production readiness framework** — Checklists and gates covering availability, rollback, configuration, and operational handoff—not ad-hoc go-live.
- **Observability and reliability** — Metrics and traces wired through OpenTelemetry; Grafana for SLOs, incident response, and capacity signals.
- **RAG-enhanced policy context (explanations only)** — Retrieval augments explanations of violations and suggested fixes; it does not decide pass/fail.

## Tech Stack

| Area | Components |
|------|------------|
| Source & CI/CD | GitLab, container builds, automated tests and scans |
| Policy | Policy Enforcement Agent, rule catalogs, integration with pipeline stages |
| Delivery | Argo CD, Git-backed manifests, progressive or controlled sync |
| Runtime | Kubernetes, ML inference and supporting services |
| Observability | OpenTelemetry instrumentation, Grafana dashboards and alerting |

## Data Flow

1. Developer commits code to the repository from the secure development environment.
2. GitLab CI executes the pipeline: build, test, and security/quality scans as defined for the ML service.
3. The Policy Enforcement Agent evaluates the change against enforced rules (e.g. image policy, secrets, supply-chain, deployment constraints).
4. Findings are generated: pass, fail, or conditional outcomes with references to violated controls.
5. RAG enriches context for human review—plain-language explanation of the violation and alignment with policy intent (no change to enforcement outcome).
6. On success, deployment proceeds via Argo CD applying approved manifests to the target cluster(s).
7. Observability captures runtime metrics and traces from the ML service and platform components for health, latency, and error budgets.

## Example Use Case

A team ships an **inference service** behind an API in Kubernetes. On merge, the **pipeline runs** unit tests, model packaging, and image build; the **policy agent** rejects a deployment when the container runs as root and a required label is missing. **Findings** cite the specific rule; **RAG-backed text** explains why the rule exists and points to the **template or patch** that remediates (e.g. non-root user, required labels). After the developer fixes the manifest and the pipeline **passes**, **Argo CD syncs** the new revision. **Grafana and traces** show request rate, p95 latency, and error ratio; alerts fire if SLOs degrade.

## Design Principles

**Rules decide. RAG explains. Templates remediate.**

- **Deterministic enforcement** — Policy outcomes derive from explicit rules and pipeline inputs, not from probabilistic model output.
- **Auditability** — Who changed what, which commit and image were promoted, and which checks ran are recorded for review and compliance evidence.
- **Reproducibility** — Same commit and configuration produce the same build artifacts and the same gated path to production.
- **Secure defaults** — Least privilege, minimal images, secrets outside source control, and safe-by-default Kubernetes and network posture unless overridden with justification.

## Why This Matters

This work is a concrete exercise in **end-to-end platform and ML delivery skills**: shipping a service with real operational seams—**governed ML delivery** with automation for speed, **gates for risk**, and **observability for operations**—and owning the path from code and CI through GitOps and runtime behavior, not a single isolated tool or demo script.

## Roadmap / Next Steps

- Expand policy packs (e.g. admission-aligned checks, SBOM gates, license policy).
- Deeper integration between findings, ticketing, and merge request workflows.
- SLO-driven alerting and runbooks wired to Grafana and on-call rotation.
- Broader model lifecycle coverage (training job governance, artifact lineage) where applicable.
- Continuous hardening of the secure dev environment and secrets integration patterns.
