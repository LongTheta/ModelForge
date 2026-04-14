"""Ingest structured knowledge-base JSON documents into the vector index."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from retrieval.index import get_collection
from retrieval.schemas import DEFAULT_KB_SOURCE_TYPE, FILTER_KEYS
from retrieval.ingest import _chunk_text


def kb_record_to_embedding_text(record: dict[str, Any]) -> str:
    """
    Flatten a KB JSON document into prose for embedding.

    Includes title, summary, body, remediation, and a short compliance summary line
    so NIST/FedRAMP IDs participate in semantic search even though filters use other metadata.
    """
    parts: list[str] = []
    if t := record.get("title"):
        parts.append(f"# {t}")
    if s := record.get("summary"):
        parts.append(s)
    parts.append(record.get("body", "").strip())

    rem = record.get("remediation")
    if isinstance(rem, dict):
        sec: list[str] = []
        if steps := rem.get("steps"):
            sec.append("## Remediation steps\n" + "\n".join(f"- {x}" for x in steps))
        if snip := rem.get("example_manifest_snippet"):
            sec.append("## Example\n```yaml\n" + snip.strip() + "\n```")
        if ver := rem.get("verification"):
            sec.append("## Verification\n" + ver.strip())
        if sec:
            parts.append("\n\n".join(sec))

    comp = record.get("compliance") or {}
    comp_bits: list[str] = []
    for n in comp.get("nist") or []:
        if isinstance(n, dict) and n.get("control_id"):
            nm = n.get("name") or ""
            comp_bits.append(f"NIST {n['control_id']}{(' — ' + nm) if nm else ''}")
    for f in comp.get("fedramp") or []:
        if isinstance(f, dict):
            bl = f.get("baseline", "")
            ctl = f.get("control", "")
            if bl or ctl:
                comp_bits.append(f"FedRAMP ({bl}): {ctl}".strip())
    if comp_bits:
        parts.append("## Compliance references\n" + "\n".join(f"- {x}" for x in comp_bits))

    if rel := record.get("related_rules"):
        parts.append("## Related AegisML rules\n" + ", ".join(str(x) for x in rel))

    return "\n\n".join(p for p in parts if p)


def _metadata_for_kb_chunk(record: dict[str, Any], chunk_index: int) -> dict[str, Any]:
    """Chroma metadata: filter keys + document fields (values are str / bool / int / float only)."""
    filters = record["filters"]
    st_raw = filters.get("source_type") if isinstance(filters.get("source_type"), str) else ""
    source_type = st_raw.strip() if st_raw.strip() else DEFAULT_KB_SOURCE_TYPE
    meta: dict[str, Any] = {
        "source_id": record["id"],
        "chunk": str(chunk_index),
        FILTER_KEYS[0]: filters["finding_type"],
        FILTER_KEYS[1]: filters["platform"],
        FILTER_KEYS[2]: filters["severity"],
        FILTER_KEYS[3]: source_type,
        "doc_type": record.get("doc_type", "policy_explanation"),
        "title": (record.get("title") or "")[:512],
    }
    comp = record.get("compliance") or {}
    meta["nist_refs"] = json.dumps(comp.get("nist") or [], separators=(",", ":"))[:4096]
    meta["fedramp_refs"] = json.dumps(comp.get("fedramp") or [], separators=(",", ":"))[:4096]
    rel = record.get("related_rules") or []
    meta["related_rules"] = ",".join(str(x) for x in rel)[:1024]
    return meta


def ingest_kb_record(
    record: dict[str, Any],
    *,
    collection_name: str | None = None,
    max_chars: int = 1200,
) -> list[str]:
    """
    Index one KB document: chunk text, attach metadata per chunk.

    `record` must match knowledge_base/schema/kb-document.schema.json (id, doc_type, filters, body).
    """
    coll = get_collection(collection_name)
    text = kb_record_to_embedding_text(record)
    chunks = _chunk_text(text, max_chars=max_chars)
    ids: list[str] = []
    docs: list[str] = []
    metas: list[dict] = []
    sid = record["id"]
    for i, ch in enumerate(chunks):
        uid = hashlib.sha256(f"{sid}:{i}:{ch[:64]}".encode()).hexdigest()[:32]
        ids.append(uid)
        docs.append(ch)
        metas.append(_metadata_for_kb_chunk(record, i))
    if docs:
        coll.add(ids=ids, documents=docs, metadatas=metas)
    return ids


def ingest_kb_json_path(path: Path, **kwargs: Any) -> list[str]:
    """Load a single JSON file and ingest."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return ingest_kb_record(data, **kwargs)


def ingest_kb_directory(
    root: Path,
    *,
    glob: str = "**/*.json",
    collection_name: str | None = None,
) -> int:
    """Ingest all matching JSON documents under root; returns count of files ingested."""
    n = 0
    for p in sorted(root.glob(glob)):
        if p.is_file() and p.name != "kb-document.schema.json":
            ingest_kb_json_path(p, collection_name=collection_name)
            n += 1
    return n
