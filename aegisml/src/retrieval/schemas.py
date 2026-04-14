"""
Shared types and filter dimensions for retrieval (Chroma metadata / query ``where``).

Enrichment never affects deterministic policy verdicts — these types describe KB chunks and queries only.
"""

from __future__ import annotations

from typing import TypedDict

# Dimensions indexed on every chunk and allowed in ``query_context(..., where=...)``.
FILTER_KEYS: tuple[str, ...] = (
    "finding_type",
    "platform",
    "severity",
    "source_type",
)

# Default for knowledge-base documents and for queries when a finding omits ``source_type``.
DEFAULT_KB_SOURCE_TYPE = "knowledge_base"


class RetrievalChunkMetadata(TypedDict, total=False):
    """Subset of metadata stored on each vector row (string values for Chroma)."""

    source_id: str
    chunk: str
    finding_type: str
    platform: str
    severity: str
    source_type: str
    doc_type: str
    title: str
    nist_refs: str
    fedramp_refs: str
    related_rules: str
