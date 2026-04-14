# AegisML initial knowledge base

Structured JSON documents under `samples/` seed the vector index used by `retrieval.enrich` for explanations, compliance hints, and remediation text. They do **not** change deterministic CI pass/fail.

## Design overview

| Layer | Choice |
|-------|--------|
| **Unit of authorship** | One JSON file per logical document (`id`), validated by `schema/kb-document.schema.json`. |
| **Vector unit** | One or more **chunks** per document after flattening to prose (see chunking below). |
| **Retrieval filters** | Chroma `where` uses only `finding_type`, `platform`, `severity` (from each document’s `filters`). |
| **Compliance surfacing** | NIST / FedRAMP references are stored as JSON strings on chunks and appear in enriched `compliance_mapping`. |

### Sample documents (`samples/`)

| File | `doc_type` | Focus |
|------|------------|--------|
| `policy-explanation-image-digest.json` | `policy_explanation` | Why digest pinning; supply chain / reproducibility |
| `policy-explanation-non-root-workload.json` | `policy_explanation` | Non-root `securityContext`; least privilege |
| `remediation-forbid-image-latest.json` | `remediation_example` | Replace `:latest` with immutable tag or digest |
| `remediation-probes-and-resources.json` | `remediation_example` | Probes + CPU/memory requests/limits YAML |
| `compliance-nist-fedramp-secrets-ci.json` | `compliance_mapping` | Plaintext secrets in CI → AC/IA/SC families |
| `secure-pipeline-gitlab-example.json` | `secure_pipeline` | Stages, variables, policy gate in `.gitlab-ci.yml` |

## Contents by `doc_type`

| `doc_type` | Purpose |
|------------|---------|
| `policy_explanation` | Why a rule exists; links to supply chain, ops, or security posture |
| `remediation_example` | Step-by-step fixes and optional YAML snippets |
| `compliance_mapping` | NIST SP 800-53 and FedRAMP-oriented narratives for auditors/engineers |
| `secure_pipeline` | GitLab CI patterns (stages, variables, policy gates) |

## Chunking strategy

1. **Flatten:** `kb_record_to_embedding_text()` builds one string from: title, summary, `body`, remediation (steps + fenced YAML snippet + verification), a bullet list derived from `compliance.nist` / `compliance.fedramp`, and `related_rules`.
2. **Split:** `ingest._chunk_text()` splits on paragraph boundaries (`\n\s*\n+`), with a soft cap of **1200 characters** per chunk (override via `ingest_kb_record(..., max_chars=...)`).
3. **No overlap (v1):** Adjacent chunks do not repeat tail/head text; add overlap only if retrieval metrics show fragmentation.
4. **IDs:** Each chunk gets a deterministic id (`sha256` of `source_id`, chunk index, and chunk prefix) so re-ingesting the same file yields stable ids; for a **full reset**, use a fresh `AEGISML_CHROMA_PATH` or remove the old Chroma directory before re-running ingestion.

## Metadata schema

### Canonical JSON (per document)

| Field | Description |
|-------|-------------|
| `id` | Stable string (e.g. `kb-k8s-digest-001`) |
| `doc_type` | One of the four enum values |
| `title`, `summary` | Short labels; both feed embeddings |
| `body` | Main prose |
| `remediation` | Optional `steps[]`, `example_manifest_snippet`, `verification` |
| `compliance` | Optional `nist[]` (`control_id` required), `fedramp[]` |
| `related_rules` | `policy_check.py` rule names for traceability |
| `filters` | **Required:** `finding_type`, `platform`, `severity` (must align with enrichment inference) |

### Stored on each vector chunk (Chroma metadata)

| Field | Description |
|-------|-------------|
| `source_id` | KB document `id` |
| `chunk` | 0-based index as string |
| `finding_type`, `platform`, `severity` | From `filters` — used in `query_context(where=...)` |
| `doc_type` | Same as document |
| `title` | Truncated to 512 chars |
| `nist_refs` | JSON string of the `compliance.nist` array (max 4096 chars) |
| `fedramp_refs` | JSON string of the `compliance.fedramp` array (max 4096 chars) |
| `related_rules` | Comma-separated rule names (max 1024 chars) |

Chroma `where` filters in code use only `finding_type`, `platform`, `severity`; other fields surface in enriched `compliance_mapping` and debugging.

## Schema file

See `schema/kb-document.schema.json` for the canonical JSON Schema.

## Ingestion approach

1. **Install** the optional retrieval stack: `pip install -e ".[retrieval]"` (includes `chromadb`).
2. **From `aegisml/`**, ingest the default sample set:

   ```bash
   python scripts/ingest_knowledge_base.py
   ```

   This indexes every `*.json` under `knowledge_base/samples` (non-recursive default in the script; place files directly under `samples/` or pass another directory).

3. **Custom path or collection:**

   ```bash
   python scripts/ingest_knowledge_base.py path/to/kb/docs --collection aegisml_policy_kb
   ```

4. **Environment:** `AEGISML_CHROMA_PATH` sets the persistent store directory (default `.chroma/aegisml` under the process working directory). CI and laptops should agree on path if you expect portable embeddings; otherwise re-ingest after clone.

5. **Programmatic API:** `retrieval.ingest_kb.ingest_kb_record`, `ingest_kb_json_path`, `ingest_kb_directory` — same chunking and metadata as the CLI.

6. **After ingest:** run `scripts/policy_check.py` or agent flows as usual; `enrich_policy_payload` / `enrich_finding` will query the collection and attach `explanation`, `compliance_mapping`, and `recommended_fix_summary`.

## Authoring new entries

- Keep `body` focused; put long YAML in `remediation.example_manifest_snippet`.
- Set `filters` so inferred `policy_check` findings (via `_rule_metadata` in `retrieval.enrich`) overlap KB filters — the enricher falls back to severity-only and unfiltered tiers when needed.
- Prefer real NIST control IDs (e.g. `SC-13`) and FedRAMP control text that matches your SSP.
- Add the `related_rules` entry for every `policy_check.py` rule the document supports.
