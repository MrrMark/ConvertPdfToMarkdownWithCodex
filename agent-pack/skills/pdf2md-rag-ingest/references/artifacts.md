# PDF2MD Output Artifacts

Use artifact metadata before reading raw Markdown content. Prefer `report.json`, `manifest.json`, and sidecar counts for status summaries.

## Core Outputs

| File | Purpose |
| --- | --- |
| `document.md` | Human-reviewable Markdown source output |
| `manifest.json` | Stable options, source identity, asset/table/image metadata |
| `report.json` | Status, page diagnostics, warnings, summary metrics |
| `assets/images/*` | Referenced images when `image-mode=referenced` |

## RAG Sidecars

| File | Use |
| --- | --- |
| `retrieval_chunks_rag.jsonl` | Primary vector DB ingest candidate |
| `text_blocks_rag.jsonl` | Text block provenance and heading paths |
| `semantic_units_rag.jsonl` | Conservative semantic units such as requirements and definitions |
| `requirements_rag.jsonl` | Filtered normative requirement view |
| `requirement_traceability_rag.jsonl` | Requirement ID, condition, dependency, exception, testability hints |
| `technical_tables_rag.jsonl` | Register/bitfield/opcode/log page/CDW/pointer/status taxonomy typed rows |
| `tables_rag.jsonl` | Row-oriented table JSONL when requested |
| `rag_tables.md` | Row-oriented Markdown when requested |
| `figures_rag.jsonl` | Figure/image provenance, captions, bbox, nearby refs |
| `domain_units_rag.jsonl` | Domain adapter output when `--domain-adapter` is used |
| `cross_refs_rag.jsonl` | Resolved/unresolved section/table/figure/technical references |

## Batch Outputs

| File | Use |
| --- | --- |
| `batch_report.json` | Per-document batch status and status counts |
| `corpus_manifest.json` | Corpus-level document/file map and source hashes |
| `corpus_diff_report.json` | Added/changed/unchanged/removed document diff |
| `requirement_change_impact_report.json` | Requirement-level added/changed/removed diff |

## Reporting Guidance

When reporting to users:

- Include conversion status, exit code, processed pages, warning count, and output directory.
- Mention warning codes and affected pages when available.
- Mention whether outputs are full, minimal, or fast sidecar scope.
- For NVMe Base and NVM Command Set, summarize `domain_units_rag.jsonl`, `technical_tables_rag.jsonl`, command relationship metadata coverage, and validation status; do not paste raw spec rows.
- Do not paste raw PDF text, full Markdown, customer filenames, or image bytes unless explicitly requested and safe.
