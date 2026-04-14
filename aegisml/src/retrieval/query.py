"""Similarity search with optional Chroma metadata filters."""

from __future__ import annotations

from typing import Any

from retrieval.index import get_collection
from retrieval.schemas import FILTER_KEYS


def _normalize_where(filters: dict[str, str] | None) -> dict[str, Any] | None:
    """Map {'severity': 'high'} -> Chroma where clause."""
    if not filters:
        return None
    allowed = {k: v for k, v in filters.items() if k in FILTER_KEYS and v}
    if not allowed:
        return None
    if len(allowed) == 1:
        k, v = next(iter(allowed.items()))
        return {k: {"$eq": v}}
    # AND multiple conditions
    return {"$and": [{k: {"$eq": v}} for k, v in allowed.items()]}


def query_context(
    query_text: str,
    *,
    k: int = 5,
    where: dict[str, str] | None = None,
    collection_name: str | None = None,
) -> dict:
    """
    Return top-k similar chunks with distances and metadata.

    `where` may include any subset of: finding_type, platform, severity, source_type.
    """
    coll = get_collection(collection_name)
    where_clause = _normalize_where(where)
    kwargs: dict = {
        "query_texts": [query_text],
        "n_results": k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where_clause is not None:
        kwargs["where"] = where_clause
    return coll.query(**kwargs)
