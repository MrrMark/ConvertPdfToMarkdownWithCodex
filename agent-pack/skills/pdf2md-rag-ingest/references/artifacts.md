# PDF2MD Output Artifacts

Use artifact metadata before reading raw Markdown content. Prefer `report.json`, `manifest.json`, and sidecar counts for status summaries.

## Core Outputs

| File | Purpose |
| --- | --- |
| `document.md` | Human-reviewable Markdown source output |
| `manifest.json` | Stable options, source identity, asset/table/image metadata |
| `report.json` | Status, page diagnostics, warnings, summary metrics |
| `conversion_state.json` | Latest stage/page/artifact state for running or recently completed conversion |
| `interrupted_report.json` | Best-effort interrupted/fatal conversion report when partial artifacts exist |
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
| `page_layout_rag.jsonl` | Page layout diagnostics, reading-order evidence, region refs, and caption links |
| `figures_rag.jsonl` | Figure/image provenance, captions, bbox, nearby refs |
| `figure_ocr_evidence_rag.jsonl` | Region OCR evidence for figures, including confidence/status provenance |
| `figure_descriptions_rag.jsonl` | Generated figure description records when explicitly enabled by profile/options |
| `figure_structures_rag.jsonl` | Extracted figure/diagram structure records when explicitly enabled by profile/options |
| `domain_units_rag.jsonl` | Domain adapter output with `adapter_metadata`, `cross_spec_compatibility`, and stable source metadata when `--domain-adapter` is used |
| `cross_refs_rag.jsonl` | Resolved/unresolved section/table/figure/technical references |

## Batch Outputs

| File | Use |
| --- | --- |
| `batch_report.json` | Per-document batch status and status counts |
| `corpus_manifest.json` | Corpus-level document/file map and source hashes |
| `corpus_diff_report.json` | Added/changed/unchanged/removed document diff |
| `requirement_change_impact_report.json` | Requirement-level added/changed/removed diff |

## Page-window Outputs

| File or directory | Use |
| --- | --- |
| `windows/pages-0001-0100/` | Stable per-window output subdirectory |
| `page_window_merge_report.json` | Deterministic merge metadata, validation summary, and rewritten ID counts |

## Reporting Guidance

When reporting to users:

- Include conversion status, exit code, processed pages, warning count, and output directory.
- Mention warning codes and affected pages when available.
- Mention whether outputs are full, minimal, or fast sidecar scope.
- For interrupted/fatal conversions, mention `interrupted_stage`, `interrupted_page`, `last_completed_page`, and whether partial artifacts remain.
- For page-window conversions, mention `window_count`, failed windows, merge status, and `page_window_merge_report.json`.
- For visual technical RAG, summarize whether `page_layout_rag.jsonl`, `figure_ocr_evidence_rag.jsonl`, `figure_descriptions_rag.jsonl`, and `figure_structures_rag.jsonl` were generated, intentionally skipped, or omitted.
- For NVMe Base and NVM Command Set, summarize `domain_units_rag.jsonl`, `technical_tables_rag.jsonl`, command relationship metadata coverage, `adapter_metadata`/`cross_spec_compatibility` coverage, and validation status; do not paste raw spec rows.
- Preserve `source_sha256`, `source_dedupe_key`, `stable_source_id`, and `stable_requirement_seed` when handing sidecar records to downstream tools.
- Do not paste raw PDF text, full Markdown, customer filenames, or image bytes unless explicitly requested and safe.
