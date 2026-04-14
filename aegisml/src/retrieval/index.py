"""Chroma persistent client and collection lifecycle."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

from retrieval.schemas import FILTER_KEYS

if TYPE_CHECKING:
    import chromadb

DEFAULT_COLLECTION = "aegisml_policy_kb"

__all__ = ["DEFAULT_COLLECTION", "FILTER_KEYS", "get_client", "get_collection", "persist_directory"]


def persist_directory() -> str:
    """Local directory for Chroma SQLite + embeddings (override with AEGISML_CHROMA_PATH)."""
    return os.getenv("AEGISML_CHROMA_PATH", os.path.join(".chroma", "aegisml"))


@lru_cache(maxsize=1)
def get_client():
    """Singleton Chroma persistent client."""
    import chromadb
    from chromadb.config import Settings

    path = persist_directory()
    os.makedirs(path, exist_ok=True)
    return chromadb.PersistentClient(
        path=path,
        settings=Settings(anonymized_telemetry=False),
    )


def get_collection(name: str | None = None) -> chromadb.Collection:
    """Get or create the policy knowledge collection (cosine similarity)."""
    nm = name or DEFAULT_COLLECTION
    client = get_client()
    return client.get_or_create_collection(
        name=nm,
        metadata={"hnsw:space": "cosine"},
    )
