# AegisML retrieval (`src/retrieval`)

RAG-style **context for explanations only** — deterministic policy pass/fail is unchanged.

## Folder structure

```text
src/retrieval/
├── __init__.py      # Public exports
├── README.md        # This file
├── index.py         # Chroma client, collection, FILTER_KEYS, persist path
├── ingest.py        # Chunk + add documents with metadata (finding_type, platform, severity)
├── ingest_kb.py     # Optional: structured KB JSON → chunks (knowledge_base/samples)
├── query.py         # Similarity search + `where` metadata filters
└── enrich.py        # Attach retrieval context to policy findings (policy_check / agents)
```

**Vector store:** [Chroma](https://www.trychroma.com/) persistent SQLite under `AEGISML_CHROMA_PATH` (default `.chroma/aegisml`). A FAISS backend would replace `index.py` / collection calls while keeping the same `ingest` / `query` contracts.

## Metadata filtering

Every indexed chunk stores:

| Key | Purpose |
|-----|---------|
| `finding_type` | e.g. `kubernetes_workload`, `ci_security`, `secrets` |
| `platform` | e.g. `kubernetes`, `gitlab_ci`, `general` |
| `severity` | e.g. `high`, `medium`, `info` (align with policy findings) |

`query.py` builds Chroma `where` clauses (`$eq`, `$and`) from a subset of these keys so retrieval stays scoped to relevant KB slices.

## Flow

```text
┌─────────────┐     ┌──────────┐     ┌─────────────┐
│ ingest*.py  │────▶│ index.py │────▶│ Chroma DB   │
│ (chunks+    │     │ collection      │ (.chroma/)  │
│  metadata)  │     └──────────┘     └──────┬──────┘
└─────────────┘                             │
                                            │ query + where
┌─────────────┐     ┌──────────┐            │
│ policy      │────▶│ query.py │◀───────────┘
│ finding     │     └────┬─────┘
└─────────────┘          │
                         ▼
                  ┌─────────────┐
                  │  enrich.py  │──▶ finding + retrieval + explanation fields
                  └─────────────┘
```

1. **Ingest** — Text is split into chunks; each chunk gets `finding_type`, `platform`, `severity` plus `source_id` / `chunk` index.
2. **Index** — Chroma stores embeddings (default embedding function unless configured).
3. **Query** — `query_context(query_text, where={...}, k=)` runs similarity search with optional metadata filters.
4. **Enrich** — `enrich_finding` / `enrich_findings` infer filters from the finding (`rule`, `severity`, explicit keys), query with fallbacks (strict → severity-only → unfiltered), then attach `retrieval`, `explanation`, `compliance_mapping`, `recommended_fix_summary`.

## Install

```bash
pip install -e ".[retrieval]"
```

Set `AEGISML_DISABLE_RETRIEVAL=true` to skip vector queries (CI without Chroma).
