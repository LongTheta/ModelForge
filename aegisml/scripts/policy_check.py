#!/usr/bin/env python3
"""
Deterministic policy checks for CI (shift-left). Complements the optional
AI DevSecOps Policy Enforcement Agent (see policies/policy-config.yaml and README).

Pass/fail is computed only from raw findings (see ``main``). After that,
``retrieval.enrich.enrich_policy_payload`` replaces ``findings`` with enriched
rows; it does not change ``verdict``. If retrieval cannot be imported, stub
enrichment fills the same explanation fields without a KB.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

AEGISML_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AEGISML_ROOT.parent
_SRC = AEGISML_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def load_config() -> dict:
    path = AEGISML_ROOT / "policies" / "policy-config.yaml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def k8s_manifests() -> list[Path]:
    base = AEGISML_ROOT / "k8s"
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*") if p.suffix in (".yaml", ".yml") and p.is_file())


def _k_rules(cfg: dict) -> dict:
    return cfg.get("rules", {}).get("kubernetes", {})


def check_forbid_image_latest(cfg: dict) -> list[dict]:
    findings: list[dict] = []
    if not _k_rules(cfg).get("forbid_image_latest"):
        return findings
    tag_latest = re.compile(r":latest\b")
    for path in k8s_manifests():
        text = path.read_text(encoding="utf-8")
        if tag_latest.search(text):
            findings.append(
                {
                    "severity": "high",
                    "rule": "forbid_image_latest",
                    "file": str(path.relative_to(REPO_ROOT)),
                    "detail": (
                        "Avoid the :latest tag in Kubernetes images; "
                        "pin by digest or immutable tag."
                    ),
                }
            )
    return findings


def check_require_image_digest(cfg: dict) -> list[dict]:
    findings: list[dict] = []
    if not _k_rules(cfg).get("require_image_digest"):
        return findings
    digest_mark = "@sha256:"
    for path in k8s_manifests():
        text = path.read_text(encoding="utf-8")
        for doc in yaml.safe_load_all(text):
            if not isinstance(doc, dict) or doc.get("kind") != "Deployment":
                continue
            if not doc.get("spec", {}).get("selector"):
                continue
            containers = (
                doc.get("spec", {}).get("template", {}).get("spec", {}).get("containers") or []
            )
            for c in containers:
                img = c.get("image") or ""
                if img and digest_mark not in img:
                    findings.append(
                        {
                            "severity": "high",
                            "rule": "require_image_digest",
                            "file": str(path.relative_to(REPO_ROOT)),
                            "detail": (
                                f"Container {c.get('name', '?')}: image must include "
                                f"a digest ({digest_mark}...)."
                            ),
                        }
                    )
    return findings


def _iter_full_deployments() -> list[tuple[Path, dict]]:
    """Strategic-merge patches are skipped (no spec.selector)."""
    out: list[tuple[Path, dict]] = []
    for path in k8s_manifests():
        text = path.read_text(encoding="utf-8")
        for doc in yaml.safe_load_all(text):
            if not isinstance(doc, dict) or doc.get("kind") != "Deployment":
                continue
            if not doc.get("spec", {}).get("selector"):
                continue
            out.append((path, doc))
    return out


def check_non_root(cfg: dict) -> list[dict]:
    findings: list[dict] = []
    if not _k_rules(cfg).get("require_non_root"):
        return findings
    path = AEGISML_ROOT / "k8s" / "base" / "deployment.yaml"
    if not path.is_file():
        return findings
    text = path.read_text(encoding="utf-8")
    if "runAsNonRoot: true" not in text and "runAsUser:" not in text:
        findings.append(
            {
                "severity": "high",
                "rule": "require_non_root",
                "file": str(path.relative_to(REPO_ROOT)),
                "detail": "Pod securityContext should enforce non-root execution.",
            }
        )
    return findings


def check_resource_limits(cfg: dict) -> list[dict]:
    findings: list[dict] = []
    if not _k_rules(cfg).get("require_resource_limits"):
        return findings
    for path, doc in _iter_full_deployments():
        containers = doc["spec"]["template"]["spec"].get("containers") or []
        for c in containers:
            name = c.get("name", "?")
            res = c.get("resources") or {}
            lim = res.get("limits") or {}
            req = res.get("requests") or {}
            if not lim.get("cpu") or not lim.get("memory"):
                findings.append(
                    {
                        "severity": "high",
                        "rule": "require_resource_limits",
                        "file": str(path.relative_to(REPO_ROOT)),
                        "detail": f"Container {name}: missing CPU/memory limits.",
                    }
                )
            if not req.get("cpu") or not req.get("memory"):
                findings.append(
                    {
                        "severity": "high",
                        "rule": "require_resource_limits",
                        "file": str(path.relative_to(REPO_ROOT)),
                        "detail": f"Container {name}: missing CPU/memory requests.",
                    },
                )
    return findings


def check_probes(cfg: dict) -> list[dict]:
    findings: list[dict] = []
    want_ready = _k_rules(cfg).get("require_readiness_probe")
    want_live = _k_rules(cfg).get("require_liveness_probe")
    if not want_ready and not want_live:
        return findings
    for path, doc in _iter_full_deployments():
        containers = doc["spec"]["template"]["spec"].get("containers") or []
        for c in containers:
            name = c.get("name", "?")
            if want_ready and not c.get("readinessProbe"):
                findings.append(
                    {
                        "severity": "high",
                        "rule": "require_readiness_probe",
                        "file": str(path.relative_to(REPO_ROOT)),
                        "detail": f"Container {name}: missing readinessProbe.",
                    }
                )
            if want_live and not c.get("livenessProbe"):
                findings.append(
                    {
                        "severity": "high",
                        "rule": "require_liveness_probe",
                        "file": str(path.relative_to(REPO_ROOT)),
                        "detail": f"Container {name}: missing livenessProbe.",
                    }
                )
    return findings


def check_gitlab_ci(cfg: dict) -> list[dict]:
    findings: list[dict] = []
    if not cfg.get("rules", {}).get("ci", {}).get("forbid_plaintext_password_in_gitlab_ci"):
        return findings
    path = REPO_ROOT / ".gitlab-ci.yml"
    if not path.is_file():
        return findings
    text = path.read_text(encoding="utf-8")
    if re.search(r'password:\s*["\'][^$][^"\']+["\']', text, re.IGNORECASE):
        findings.append(
            {
                "severity": "critical",
                "rule": "forbid_plaintext_password_in_gitlab_ci",
                "file": str(path.relative_to(REPO_ROOT)),
                "detail": (
                    "Plaintext password-like values in CI YAML should use "
                    "CI/CD variables or vault."
                ),
            }
        )
    return findings


def _collect_plaintext_scan_files(cfg: dict) -> list[Path]:
    ps = cfg.get("rules", {}).get("secrets", {}).get("plaintext_secrets", {})
    if not ps.get("enabled"):
        return []
    paths: list[Path] = []
    for pattern in ps.get("scan_under_aegisml", []):
        paths.extend(sorted(AEGISML_ROOT.glob(pattern)))
    for pattern in ps.get("scan_under_repo_root", []):
        paths.extend(sorted(REPO_ROOT.glob(pattern)))
    # de-dupe, keep files only
    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:
        if p.is_file() and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def check_plaintext_patterns(cfg: dict) -> list[dict]:
    findings: list[dict] = []
    ps = cfg.get("rules", {}).get("secrets", {}).get("plaintext_secrets", {})
    if not ps.get("enabled"):
        return findings
    patterns = ps.get("patterns") or []
    for path in _collect_plaintext_scan_files(cfg):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for entry in patterns:
            if isinstance(entry, dict):
                name = entry.get("name", "pattern")
                pat = entry.get("regex")
                severity = entry.get("severity", "high")
            else:
                continue
            if not pat:
                continue
            try:
                if re.search(pat, text):
                    findings.append(
                        {
                            "severity": severity,
                            "rule": f"plaintext_secret_{name}",
                            "file": str(path.relative_to(REPO_ROOT)),
                            "detail": f"Matched regex /{pat}/",
                        }
                    )
            except re.error:
                continue
    return findings


def _stub_enrichment(finding: dict) -> dict:
    """Stable shape when retrieval package is not importable (path / optional install)."""
    out = dict(finding)
    detail = out.get("detail")
    d = detail.strip() if isinstance(detail, str) else ""
    out["explanation"] = (
        d
        if d
        else "Policy violation; retrieval was unavailable to add knowledge-base context."
    )
    out["compliance_mapping"] = [
        {
            "framework": "none",
            "control": str(out.get("rule", "unknown")),
            "knowledge_source": None,
            "note": "retrieval_import_unavailable",
        }
    ]
    out["recommended_fix_summary"] = (d[:600] if d else "See policy-config.yaml and team runbooks.")
    return out


def main() -> int:
    cfg = load_config()
    findings: list[dict] = []
    findings.extend(check_forbid_image_latest(cfg))
    findings.extend(check_require_image_digest(cfg))
    findings.extend(check_non_root(cfg))
    findings.extend(check_resource_limits(cfg))
    findings.extend(check_probes(cfg))
    findings.extend(check_gitlab_ci(cfg))
    findings.extend(check_plaintext_patterns(cfg))

    # Verdict is deterministic from severities only (before retrieval enrichment).
    verdict = (
        "fail"
        if any(f.get("severity") in ("high", "critical") for f in findings)
        else "pass"
    )

    payload: dict = {"verdict": verdict, "findings": findings}
    try:
        from retrieval.enrich import enrich_policy_payload

        payload = enrich_policy_payload(payload)
    except ImportError:
        payload = {
            "verdict": verdict,
            "findings": [_stub_enrichment(f) for f in findings],
        }

    out_path = AEGISML_ROOT / "policy-findings.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))  # verdict unchanged; findings include enrichment fields
    return 1 if payload["verdict"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
