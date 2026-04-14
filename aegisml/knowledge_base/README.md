# AegisML initial knowledge base

Structured JSON documents under `samples/` seed the vector index used by `retrieval.enrich` for explanations, compliance hints, and remediation text. They do **not** change deterministic CI pass/fail.

## Contents

| `doc_type` | Purpose |
|------------|---------|
| `policy_explanation` | Why a rule exists; links to supply chain, ops, or security posture |
| `remediation_example` | Step-by-step fixes and optional YAML snippets |
| `compliance_mapping` | NIST SP 800-53 and FedRAMP-oriented narratives for auditors/engineers |
| `secure_pipeline` | GitLab CI patterns (stages, variables, policy gates) |

## Chunking strategy

1. **Unit of work:** one JSON file = one logical document (`id`).
2. **Embedding text:** `kb_record_to_embedding_text()` concatenates title, summary, body, remediation blocks, a flattened compliance bullet list (so control IDs are searchable), and `related_rules`.
3. **Splitting:** reuse `ingest._chunk_text` — paragraph boundaries (`\n\s*\n+`), soft cap **1200 characters** per chunk (tunable via `ingest_kb_record(..., max_chars=...)`).
4. **No overlap (v1):** adjacent chunks do not share tail/head text; add overlap only if retrieval quality metrics show fragmentation issues.
5. **Per-chunk metadata:** same filter triple (`finding_type`, `platform`, `severity`) on every chunk from `filters`, plus `doc_type`, `title`, JSON strings `nist_refs` / `fedramp_refs`, and `related_rules` for downstream display.

## Metadata schema (per vector chunk)

| Field | Description |
|-------|-------------|
| `source_id` | KB document `id` |
| `chunk` | 0-based chunk index within the document |
| `finding_type` | Filter dimension (e.g. `kubernetes_workload`, `ci_security`) |
| `platform` | Filter dimension (e.g. `kubernetes`, `gitlab_ci`) |
| `severity` | Filter dimension (`info`–`critical`; align with policy finding severity when possible) |
| `doc_type` | One of the four `doc_type` enum values |
| `title` | Short title (truncated for store limits) |
| `nist_refs` | JSON array string of `{control_id, name?, discussion?}` |
| `fedramp_refs` | JSON array string of `{baseline?, control?, notes?}` |
| `related_rules` | Comma-separated `policy_check.py` rule names |

Chroma `where` filters in code use only `finding_type`, `platform`, `severity`; other fields surface in enriched `compliance_mapping` and UI/debug.

## Schema file

See `schema/kb-document.schema.json` for the canonical JSON Schema.

## Ingestion

1. Install optional retrieval stack: `pip install -e ".[retrieval]"` (requires a working `chromadb` install).
2. From `aegisml/`, run:

   ```bash
   python scripts/ingest_knowledge_base.py
   ```

   Or point at a folder of `*.json` documents:

   ```bash
   python scripts/ingest_knowledge_base.py path/to/kb/docs
   ```

3. Optional: `AEGISML_CHROMA_PATH` sets the persistent store directory (default `.chroma/aegisml` under the working directory).

4. Re-run policy checks as usual; enrichment attaches KB context when queries hit indexed chunks.

## Authoring new entries

- Keep `body` focused; put long YAML in `remediation.example_manifest_snippet`.
- Set `filters` so inferred `policy_check` findings (via `_rule_metadata`) overlap KB filters—use `severity_only` / unfiltered tiers if metadata is sparse.
- Prefer real NIST control IDs (e.g. `SC-13`) and FedRAMP control text that matches your SSP.
