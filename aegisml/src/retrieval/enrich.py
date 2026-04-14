"""Attach retrieval context to a policy finding (for explanations, not pass/fail)."""

from __future__ import annotations

import json
import os
from typing import Any

from retrieval.index import FILTER_KEYS
from retrieval.query import query_context


def enrich_policy_payload(
    payload: dict[str, Any],
    *,
    k: int = 5,
    collection_name: str | None = None,
) -> dict[str, Any]:
    """
    Enrich a policy result document (e.g. ``policy-findings.json`` or agent ``review-result.json``).

    Replaces only ``findings`` with enriched rows. Does **not** modify ``verdict`` or any other
    top-level keys — pass/fail must be computed from the raw findings before calling this.
    """
    out = dict(payload)
    raw = out.get("findings")
    if not isinstance(raw, list):
        return out
    out["findings"] = enrich_findings(raw, k=k, collection_name=collection_name)
    return out


def enrich_finding(
    finding: dict[str, Any],
    *,
    query_text: str | None = None,
    k: int = 5,
    collection_name: str | None = None,
) -> dict[str, Any]:
    """
    Query the knowledge base and attach explanation fields.

    Does not alter severity or verdict inputs. Adds explanation,
    compliance_mapping, and recommended_fix_summary.

    When chromadb is missing, the KB is empty, or query fails, fields use safe defaults.
    """
    text = query_text or _default_query_text(finding)
    base_where = _effective_where(finding)
    out = dict(finding)

    contexts: list[dict[str, Any]] = []
    retrieval_meta: dict[str, Any] = {
        "available": False,
        "query": text[:2000],
        "filters_inferred": base_where,
        "contexts": [],
        "disclaimer": "Retrieval augments explanations; policy verdicts remain deterministic.",
    }

    if os.getenv("AEGISML_DISABLE_RETRIEVAL", "").strip().lower() in ("1", "true", "yes"):
        out["retrieval"] = retrieval_meta
        _apply_enrichment_fields(out, contexts, finding, retrieval_meta)
        return out

    try:
        _, contexts, tier = _query_with_fallbacks(
            text,
            k=k,
            where=base_where,
            collection_name=collection_name,
        )
        retrieval_meta["available"] = True
        retrieval_meta["fallback_tier"] = tier
        retrieval_meta["contexts"] = contexts
    except Exception as exc:  # noqa: BLE001 — best-effort enrichment for CI
        retrieval_meta["error"] = type(exc).__name__
        retrieval_meta["contexts"] = []

    out["retrieval"] = retrieval_meta
    _apply_enrichment_fields(out, retrieval_meta["contexts"], finding, retrieval_meta)
    return out


def enrich_findings(
    findings: list[dict[str, Any]],
    *,
    k: int = 5,
    collection_name: str | None = None,
) -> list[dict[str, Any]]:
    """Enrich each finding; pass/fail must be computed from the pre-enrichment list."""
    return [enrich_finding(f, k=k, collection_name=collection_name) for f in findings]


def _effective_where(finding: dict[str, Any]) -> dict[str, str]:
    """Merge explicit finding metadata with rule-based defaults for KB filtering."""
    where: dict[str, str] = {}
    for key in FILTER_KEYS:
        val = finding.get(key)
        if isinstance(val, str) and val.strip():
            where[key] = val.strip()
    ft, plat = _rule_metadata(_rule_hint(finding))
    if "finding_type" not in where:
        where["finding_type"] = ft
    if "platform" not in where:
        where["platform"] = plat
    sev = finding.get("severity")
    if "severity" not in where and isinstance(sev, str) and sev.strip():
        where["severity"] = sev.strip()
    return where


def _rule_hint(finding: dict[str, Any]) -> str:
    """Prefer ``rule``; fall back to agent fields (``category``, ``id``, ``title``)."""
    for key in ("rule", "category", "id", "title"):
        v = finding.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _rule_metadata(hint: str) -> tuple[str, str]:
    r = hint.lower()
    if "gitlab" in r or "gitlab_ci" in r:
        return ("ci_security", "gitlab_ci")
    if "plaintext" in r or "secret" in r:
        return ("secrets", "repository")
    if any(
        x in r
        for x in (
            "supply_chain",
            "image",
            "digest",
            "artifact",
            "probe",
            "root",
            "resource",
            "readiness",
            "liveness",
        )
    ):
        return ("kubernetes_workload", "kubernetes")
    return ("policy", "general")


def _query_with_fallbacks(
    text: str,
    *,
    k: int,
    where: dict[str, str],
    collection_name: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    """
    Tight filters first; relax if the KB has no hits.

    Returns (raw_chroma_response, formatted_contexts, tier_label).
    """
    attempts: list[tuple[str, dict[str, str] | None]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()

    def _add(label: str, w: dict[str, str] | None) -> None:
        key = tuple(sorted(w.items())) if w else tuple()
        if key in seen:
            return
        seen.add(key)
        attempts.append((label, w))

    _add("strict", where)
    sev = where.get("severity")
    if sev:
        _add("severity_only", {"severity": sev})
    _add("unfiltered", None)

    last: dict[str, Any] = {}
    tier = attempts[-1][0]
    for label, w in attempts:
        tier = label
        last = query_context(text, k=k, where=w, collection_name=collection_name)
        ctx = _format_hits(last)
        if ctx:
            return last, ctx, label
    return last, [], tier


def _apply_enrichment_fields(
    out: dict[str, Any],
    contexts: list[dict[str, Any]],
    finding: dict[str, Any],
    retrieval_meta: dict[str, Any],
) -> None:
    out["explanation"] = _build_explanation(finding, contexts, retrieval_meta)
    out["compliance_mapping"] = _build_compliance_mapping(finding, contexts)
    out["recommended_fix_summary"] = _build_recommended_fix(finding, contexts)


def _build_explanation(
    finding: dict[str, Any],
    contexts: list[dict[str, Any]],
    retrieval_meta: dict[str, Any],
) -> str:
    if not contexts:
        return (
            "No knowledge-base passages were retrieved for this finding. "
            "Use the rule and detail fields as the authoritative description of the violation."
        )
    parts: list[str] = []
    top = contexts[0].get("text") or ""
    if top:
        parts.append(top.strip()[:1200])
    if len(contexts) > 1:
        second = (contexts[1].get("text") or "").strip()
        if second:
            parts.append(f"Additional context: {second[:500]}")
    note = retrieval_meta.get("fallback_tier")
    if note and note != "strict" and parts:
        parts.append(f"(Broader KB match tier: {note}.)")
    return "\n\n".join(parts).strip()


def _parse_kb_json_list(raw: Any) -> list[Any]:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _build_compliance_mapping(
    finding: dict[str, Any],
    contexts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rule = finding.get("rule", "unknown")
    rows: list[dict[str, Any]] = []
    for i, c in enumerate(contexts[:8]):
        meta = c.get("metadata") if isinstance(c.get("metadata"), dict) else {}
        row: dict[str, Any] = {
            "framework": meta.get("framework", "organizational_kb"),
            "control": meta.get("control", rule),
            "knowledge_source": meta.get("source_id"),
            "rank": i + 1,
            "distance": c.get("distance"),
            "doc_type": meta.get("doc_type"),
        }
        nist = _parse_kb_json_list(meta.get("nist_refs"))
        fed = _parse_kb_json_list(meta.get("fedramp_refs"))
        if nist:
            row["nist_controls"] = nist
        if fed:
            row["fedramp_controls"] = fed
        rows.append(row)
    if not rows:
        rows.append(
            {
                "framework": "none",
                "control": str(rule),
                "knowledge_source": None,
                "note": "no_kb_hits",
            }
        )
    return rows


def _build_recommended_fix(
    finding: dict[str, Any],
    contexts: list[dict[str, Any]],
) -> str:
    if contexts:
        t = (contexts[0].get("text") or "").strip()
        if len(t) > 600:
            return t[:597].rstrip() + "..."
        return t
    detail = finding.get("detail")
    if isinstance(detail, str) and detail.strip():
        return detail.strip()[:600]
    return "See policy-config.yaml and team runbooks for the remediation pattern."


def _default_query_text(f: dict[str, Any]) -> str:
    parts = []
    for key in ("title", "rule", "detail", "message", "description", "file"):
        v = f.get(key)
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())
    imp = f.get("impacted_files")
    if isinstance(imp, list):
        for p in imp[:12]:
            if isinstance(p, str) and p.strip():
                parts.append(p.strip())
    rem = f.get("remediation_summary")
    if isinstance(rem, str) and rem.strip():
        parts.append(rem.strip())
    return "\n".join(parts) if parts else str(f)


def _format_hits(raw: dict) -> list[dict[str, Any]]:
    """Normalize Chroma query() response to a list of {text, metadata, distance}."""
    out: list[dict[str, Any]] = []
    ids = raw.get("ids") or [[]]
    docs = raw.get("documents") or [[]]
    metas = raw.get("metadatas") or [[]]
    dists = raw.get("distances") or [[]]
    if not ids or not ids[0]:
        return out
    for i in range(len(ids[0])):
        out.append(
            {
                "text": (docs[0][i] if docs and docs[0] else "") or "",
                "metadata": (metas[0][i] if metas and metas[0] else {}) or {},
                "distance": (dists[0][i] if dists and dists[0] else None),
            }
        )
    return out
