"""Retrieval module tests; Chroma-dependent tests skip if chromadb is not installed."""

from __future__ import annotations

import os
import tempfile

import pytest

from retrieval.enrich import enrich_finding, enrich_policy_payload
from retrieval.index import get_client, persist_directory


def test_enrich_finding_adds_fields_without_chroma() -> None:
    """KB query may fail without chromadb; enrichment must still populate top-level fields."""
    f = {
        "severity": "high",
        "rule": "require_image_digest",
        "file": "k8s/base/deploy.yaml",
        "detail": "Use an image digest.",
    }
    out = enrich_finding(f, k=2)
    assert "explanation" in out
    assert "compliance_mapping" in out
    assert "recommended_fix_summary" in out
    assert isinstance(out["compliance_mapping"], list)


def test_enrich_policy_payload_preserves_verdict() -> None:
    """Top-level verdict and summary must not change; only findings are replaced."""
    payload = {
        "verdict": "fail",
        "summary": "unchanged",
        "findings": [
            {
                "severity": "high",
                "rule": "require_image_digest",
                "file": "k8s/base/deploy.yaml",
                "detail": "Use an image digest.",
            }
        ],
    }
    out = enrich_policy_payload(payload)
    assert out["verdict"] == "fail"
    assert out["summary"] == "unchanged"
    assert len(out["findings"]) == 1
    assert "explanation" in out["findings"][0]


def test_persist_directory_default() -> None:
    path = persist_directory()
    assert ".chroma" in path.replace("\\", "/")


def test_ingest_query_enrich_flow() -> None:
    pytest.importorskip("chromadb")

    from retrieval.ingest import ingest_text
    from retrieval.query import query_context

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AEGISML_CHROMA_PATH"] = tmp
        get_client.cache_clear()

        ingest_text(
            "Use TLS 1.2+ for all API endpoints. Rotate keys every 90 days.",
            finding_type="network",
            platform="kubernetes",
            severity="high",
            source_id="test-doc",
            collection_name="test_policy_kb",
        )

        out = query_context(
            "TLS requirements",
            k=2,
            where={"severity": "high", "platform": "kubernetes"},
            collection_name="test_policy_kb",
        )
        assert out["documents"] and out["documents"][0]

        finding = {
            "title": "Weak TLS",
            "description": "Service allows TLS 1.0",
            "finding_type": "network",
            "platform": "kubernetes",
            "severity": "high",
        }
        enriched = enrich_finding(
            finding,
            k=2,
            collection_name="test_policy_kb",
        )
        assert "retrieval" in enriched
        assert enriched["retrieval"]["contexts"]
        assert enriched["explanation"]
        assert enriched["compliance_mapping"]
        assert enriched["recommended_fix_summary"]
