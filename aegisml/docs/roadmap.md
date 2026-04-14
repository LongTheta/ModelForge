# Roadmap

1. **Phase A — Hardening** — Lock base images by digest in Kustomize; SBOM export in CI; optional Cosign sign/verify.
2. **Phase B — Policy agent** — Install AI DevSecOps Policy Enforcement Agent; fail builds on high/critical with MR comments.
3. **Phase C — RAG enrichment** — Deterministic rules stay authoritative; RAG explains findings and suggests remediations (per platform design).
4. **Phase D — Model** — Swap sklearn baseline for a distilled HF classifier behind the same API contract if needed.

The MVP intentionally avoids drift detection, feature stores, and multi-model routing until the delivery path is stable.
