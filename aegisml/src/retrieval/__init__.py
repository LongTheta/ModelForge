"""
RAG-style retrieval for policy finding enrichment (explanations only; rules stay authoritative).

Install: pip install -e ".[retrieval]"
"""

from retrieval.enrich import enrich_finding, enrich_findings, enrich_policy_payload
from retrieval.index import FILTER_KEYS, get_collection, persist_directory
from retrieval.schemas import DEFAULT_KB_SOURCE_TYPE
from retrieval.ingest import ingest_directory, ingest_path, ingest_text
from retrieval.ingest_kb import ingest_kb_directory, ingest_kb_record, kb_record_to_embedding_text
from retrieval.query import query_context

__all__ = [
    "DEFAULT_KB_SOURCE_TYPE",
    "FILTER_KEYS",
    "enrich_finding",
    "enrich_findings",
    "enrich_policy_payload",
    "get_collection",
    "ingest_directory",
    "ingest_kb_directory",
    "ingest_kb_record",
    "ingest_path",
    "ingest_text",
    "kb_record_to_embedding_text",
    "persist_directory",
    "query_context",
]
