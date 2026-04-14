"""Load policy text / remediation snippets into the vector index."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from retrieval.index import FILTER_KEYS, get_collection


def _chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    """Simple paragraph-aware chunks for MVP."""
    parts = re.split(r"\n\s*\n+", text.strip())
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for p in parts:
        if size + len(p) > max_chars and buf:
            chunks.append("\n\n".join(buf))
            buf = [p]
            size = len(p)
        else:
            buf.append(p)
            size += len(p) + 2
    if buf:
        chunks.append("\n\n".join(buf))
    return chunks if chunks else [text[:max_chars]]


def ingest_text(
    text: str,
    *,
    finding_type: str,
    platform: str,
    severity: str,
    source_id: str,
    collection_name: str | None = None,
) -> list[str]:
    """
    Index one logical document split into chunks.
    Metadata on every chunk enables query-time filters (finding_type, platform, severity).
    """
    coll = get_collection(collection_name)
    chunks = _chunk_text(text)
    ids: list[str] = []
    docs: list[str] = []
    metas: list[dict] = []
    for i, ch in enumerate(chunks):
        uid = hashlib.sha256(f"{source_id}:{i}:{ch[:64]}".encode()).hexdigest()[:32]
        ids.append(uid)
        docs.append(ch)
        metas.append(
            {
                "source_id": source_id,
                "chunk": str(i),
                FILTER_KEYS[0]: finding_type,
                FILTER_KEYS[1]: platform,
                FILTER_KEYS[2]: severity,
            }
        )
    if docs:
        coll.add(ids=ids, documents=docs, metadatas=metas)
    return ids


def ingest_path(
    path: Path,
    *,
    finding_type: str = "general",
    platform: str = "any",
    severity: str = "info",
) -> list[str]:
    """Ingest a UTF-8 file (e.g. policy markdown, runbook)."""
    text = path.read_text(encoding="utf-8")
    return ingest_text(
        text,
        finding_type=finding_type,
        platform=platform,
        severity=severity,
        source_id=str(path.resolve()),
    )


def ingest_directory(
    root: Path,
    *,
    glob: str = "**/*.md",
    default_meta: dict | None = None,
) -> int:
    """Batch-ingest files under root; returns count of files processed."""
    meta = default_meta or {}
    n = 0
    for p in sorted(root.glob(glob)):
        if p.is_file():
            ingest_path(
                p,
                finding_type=meta.get("finding_type", "general"),
                platform=meta.get("platform", "any"),
                severity=meta.get("severity", "info"),
            )
            n += 1
    return n
