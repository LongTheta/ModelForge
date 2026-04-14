# AegisML knowledge base (policy enrichment)

Structured JSON documents under `samples/` seed the vector index used by `retrieval.enrich` for explanations, compliance hints, and remediation text. They do **not** change deterministic CI pass/fail.

## Design overview

| Layer | Choice |
|-------|--------|
| **Unit of authorship** | One JSON file per logical document (`id`), validated by `schema/kb-document.schema.json`. |
| **Vector unit** | One or more **chunks** per document after flattening to prose (see [Chunking](#chunk-structure)). |
| **Retrieval filters** | Chroma `where` uses `finding_type`, `platform`, `severity`, and `source_type` (see [Metadata](#metadata-schema)). |
| **Document typing** | `doc_type` distinguishes rationale vs fixes vs compliance tables vs CI/CD vs Kubernetes **patterns** — predictable slices for authors and for debugging retrieval. |

### Document types (`doc_type`)

| `doc_type` | Use for | Typical `body` |
|------------|---------|----------------|
| `policy_explanation` | Why a rule exists; risk and intent | Narrative only; optional remediation for “what good looks like” |
| `remediation_example` | Concrete steps and YAML/CI snippets to fix a finding | Steps + `example_manifest_snippet` |
| `compliance_mapping` | Auditor-oriented mapping: controls, SSP language | Narrative + structured `compliance` |
| `secure_cicd_pattern` | Reusable secure pipeline layout (GitLab CI, gates, stages) | Narrative + optional `.gitlab-ci.yml`-style snippet |
| `secure_kubernetes_pattern` | Reusable manifest shapes (Deployment baseline, probes, securityContext) | Narrative + YAML in `remediation.example_manifest_snippet` |

**Legacy:** `secure_pipeline` is still accepted in the schema and behaves like `secure_cicd_pattern` at ingest; **prefer `secure_cicd_pattern`** for new files.

### Sample documents (`samples/`)

| File | `doc_type` | Focus |
|------|------------|-------|
| `policy-explanation-image-digest.json` | `policy_explanation` | Digest pinning; supply chain / reproducibility |
| `policy-explanation-non-root-workload.json` | `policy_explanation` | Non-root `securityContext`; least privilege |
| `remediation-forbid-image-latest.json` | `remediation_example` | Replace `:latest` with immutable tag or digest |
| `remediation-probes-and-resources.json` | `remediation_example` | Probes + CPU/memory requests/limits YAML |
| `compliance-nist-fedramp-secrets-ci.json` | `compliance_mapping` | Plaintext secrets in CI → AC/IA/SC families |
| `secure-pipeline-gitlab-example.json` | `secure_cicd_pattern` | Stages, variables, policy gate in `.gitlab-ci.yml` |
| `secure-kubernetes-pattern-workload-baseline.json` | `secure_kubernetes_pattern` | Baseline Deployment: securityContext, probes, resources |

## Chunk structure

1. **Flatten:** `retrieval.ingest_kb.kb_record_to_embedding_text()` builds one string from, in order: `# title`, `summary`, `body`, optional remediation blocks (steps, fenced YAML, verification), a bullet list from `compliance.nist` / `compliance.fedramp`, and `related_rules`.
2. **Split:** `retrieval.ingest._chunk_text()` splits on paragraph boundaries (`\n\s*\n+`), with a soft cap of **1200 characters** per chunk (override via `ingest_kb_record(..., max_chars=...)`).
3. **No overlap (v1):** Adjacent chunks do not repeat text; add overlap only if metrics show fragmentation.
4. **Stable IDs:** Each chunk id is `sha256(source_id, chunk_index, chunk_prefix)` so re-ingesting the same document yields the same chunk ids (use a fresh Chroma path for a full corpus reset).

**Why this stays predictable:** One authoring JSON → one deterministic flatten → deterministic chunk boundaries for unchanged inputs. Embeddings may vary slightly by environment; filters (`filters.*`) narrow hits before ranking.

## Metadata schema

### Canonical JSON (per document)

| Field | Description |
|-------|-------------|
| `id` | Stable string (e.g. `kb-k8s-digest-001`) |
| `doc_type` | One of the enum values in `schema/kb-document.schema.json` |
| `title`, `summary` | Short labels; both feed embeddings |
| `body` | Main prose (required; may be short if detail lives in `remediation`) |
| `remediation` | Optional `steps[]`, `example_manifest_snippet`, `verification` |
| `compliance` | Optional `nist[]` (`control_id` required per row), `fedramp[]` |
| `related_rules` | `policy_check.py` **finding** `rule` strings (e.g. `require_image_digest`) for traceability |
| `filters` | **Required:** `finding_type`, `platform`, `severity`; optional `source_type` (defaults to `knowledge_base` at ingest) |

### Stored on each vector chunk (Chroma metadata)

| Field | Description |
|-------|-------------|
| `source_id` | KB document `id` |
| `chunk` | 0-based index as string |
| `finding_type`, `platform`, `severity`, `source_type` | From `filters` — used in `query_context(where=...)` |
| `doc_type` | Same as document (surfaces in enriched `compliance_mapping`) |
| `title` | Truncated to 512 chars |
| `nist_refs` | JSON string of `compliance.nist` (max 4096 chars) |
| `fedramp_refs` | JSON string of `compliance.fedramp` (max 4096 chars) |
| `related_rules` | Comma-separated rule names (max 1024 chars) |

Filters drive **predictable** retrieval: authors align `filters` with how policy findings are labeled (`kubernetes_workload` / `gitlab_ci`, severities, etc.). `doc_type` is metadata for explanation quality, not a separate Chroma filter in v1 (keeps the filter surface small).

## Schema file

See `schema/kb-document.schema.json` for the canonical JSON Schema.

## Ingestion approach

1. **Install** the optional retrieval stack: `pip install -e ".[retrieval]"` (includes `chromadb`).
2. **From `aegisml/`**, ingest the default sample set:

   ```bash
   python scripts/ingest_knowledge_base.py
   ```

   This indexes every `*.json` under `knowledge_base/samples` (excluding the schema file).

3. **Custom path or collection:**

   ```bash
   python scripts/ingest_knowledge_base.py path/to/kb/docs --collection aegisml_policy_kb
   ```

4. **Environment:** `AEGISML_CHROMA_PATH` sets the persistent store directory (default `.chroma/aegisml` under the process working directory). CI and laptops should agree on path if you expect portable embeddings; otherwise re-ingest after clone.

5. **Programmatic API:** `retrieval.ingest_kb.ingest_kb_record`, `ingest_kb_json_path`, `ingest_kb_directory` — same chunking and metadata as the CLI.

6. **After ingest:** run `scripts/policy_check.py` or agent flows as usual; `enrich_policy_payload` / `enrich_finding` will query the collection and attach `explanation`, `compliance_mapping`, and `recommended_fix_summary`.

## Authoring new entries

- Keep `body` focused; put long YAML in `remediation.example_manifest_snippet`.
- Pick the smallest accurate `doc_type` (explanation vs remediation vs compliance vs CI/CD vs Kubernetes pattern).
- Set `filters` so inferred `policy_check` findings (via `_rule_metadata` in `retrieval.enrich`) overlap KB filters — the enricher falls back to severity-only and unfiltered tiers when needed.
- Prefer real NIST control IDs (e.g. `SC-13`) and FedRAMP control text that matches your SSP.
- List every relevant `policy_check.py` rule string in `related_rules`.
