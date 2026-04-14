"""Knowledge-base JSON flattening (no chromadb required)."""

from __future__ import annotations

from pathlib import Path

import pytest

from retrieval.ingest_kb import kb_record_to_embedding_text


def test_kb_record_to_embedding_text_includes_nist_and_body() -> None:
    sample = Path(__file__).resolve().parents[1] / "knowledge_base" / "samples"
    path = sample / "policy-explanation-image-digest.json"
    if not path.is_file():
        pytest.skip("knowledge base sample missing")
    import json

    record = json.loads(path.read_text(encoding="utf-8"))
    text = kb_record_to_embedding_text(record)
    assert "digest" in text.lower()
    assert "SC-13" in text or "NIST" in text
    assert "FedRAMP" in text
