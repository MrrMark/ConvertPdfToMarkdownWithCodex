# Output Schema Contract

이 문서는 `pdf2md` 산출물을 외부 RAG/indexing 파이프라인에서 안정적으로 참조하기 위한 schema 계약이다.

## 호환성 정책

- `schema_version`은 현재 `1.0`이다.
- required field 제거, 타입 변경, 의미 변경은 breaking change로 본다.
- optional field 추가는 backward-compatible 변경이다.
- JSON consumer는 모르는 field를 무시해야 한다.
- 산출물 경로와 asset 파일명은 동일 입력 + 동일 옵션 + 동일 버전에서 결정적으로 유지한다.

## Machine-readable Schema

현재 public JSON 출력의 machine-readable schema는 `docs/schema/` 아래에 커밋한다.

- `docs/schema/manifest.schema.json`
- `docs/schema/report.schema.json`
- `docs/schema/batch_report.schema.json`
- `docs/schema/corpus_manifest.schema.json`
- `docs/schema/corpus_diff_report.schema.json`
- `docs/schema/requirement_change_impact_report.schema.json`
- `docs/schema/index_contract_report.schema.json`
- `docs/schema/provenance_integrity_report.schema.json`
- `docs/schema/artifact_integrity_report.schema.json`
- `docs/schema/local_corpus_evidence_pack.schema.json`
- `docs/schema/corpus_evidence_analysis_report.schema.json`
- `docs/schema/corpus_evidence_trend_report.schema.json`

Schema 파일은 다음 명령으로 재생성하거나 검증한다.

```bash
python scripts/export_output_schema.py
python scripts/export_output_schema.py --check
```

## document.md

Required:

- 원문 보존 중심 Markdown 본문
- opt-in page marker: `<!-- page: N -->`
- 표/이미지 위치 보존을 위한 comment 또는 link

Optional:

- `rag_tables.md`와 연결되는 표 주석
- partial success warning comment

## manifest.json

Required:

- `schema_version`
- `input_file`
- `total_pages`
- `selected_pages`
- `options`
- `images`
- `excluded_images`
- `tables`
- `ocr_pages`
- `warnings`

Stable nested fields:

- `options.image_mode`, `options.table_mode`, `options.rag_table_output`, `options.rag_text_blocks_output`, `options.semantic_layer_output`, `options.ocr_lang`
- `options.rag_text_blocks_jsonl_filename`, `options.semantic_units_jsonl_filename`, `options.requirements_jsonl_filename`, `options.cross_refs_jsonl_filename`
- `options.requirement_traceability_jsonl_filename`, `options.technical_tables_jsonl_filename`
- `options.retrieval_chunks_jsonl_filename`, `options.figures_rag_jsonl_filename`, `options.domain_adapter`, `options.domain_units_jsonl_filename`
- `options.retrieval_chunk_max_tokens`, `options.retrieval_tokenizer`, `options.rag_contextual_embedding_text`, `options.rag_merge_sibling_text_chunks`, `options.rag_chunk_relationship_metadata`
- `options.confidential_safe_mode`, `options.local_only_processing`, `options.external_llm_calls`, `options.external_embedding_calls`, `options.path_redaction`
- `options.page_workers`, `options.page_worker_effective_count`, `options.page_parallel_enabled`
- `images[].page`, `index`, `path`, `source`, `bbox`, `sha256`
- `images[].alt_text`, `caption_text`, `caption_source`, `dedupe_of`
- `images[].caption_confidence`, `crop_reason`, `crop_content_ratio`, `crop_rejected_reason`
- `excluded_images[].reason`, `classification`, `recovery_strategy`, `ocr_candidates`
- `tables[].page`, `index`, `mode`, `bbox`, `quality_score`, `fallback_reasons`
- `tables[].continuation_group`, `continued_from_page`, `continued_to_page`, `continuation_confidence`
- `tables[].continuation_reasons`, `continuation_rejected_reasons`, `continuation_features`

## report.json

Required:

- `schema_version`
- `started_at`
- `finished_at`
- `duration_ms`
- `status`
- `engine_usage`
- `failed_pages`
- `warnings`
- `page_results`
- `summary`

Stable summary fields:

- `processed_pages`, `warning_count`, `actionable_warning_count`, `advisory_warning_count`, `failed_page_count`, `partial_success`
- `page_status_counts`
- `table_total`, `table_html_count`, `table_gfm_count`, `table_fallback_count`
- `table_fallback_reason_counts`, `table_expected_fallback_count`, `table_expected_fallback_reason_counts`, `table_actionable_fallback_count`
- `table_low_quality_count`, `table_actionable_low_quality_count`, `table_advisory_low_quality_count`, `table_quality`
- `ocr_actionable_warning_count`, `ocr_advisory_warning_count`
- `stage_durations_ms`, `pdf_open_count`, `pages_per_second`
- `page_worker_count`, `page_worker_effective_count`, `page_parallel_enabled`
- `page_cache_hits`, `page_cache_misses`, `text_line_extract_count`
- `heading_count`, `list_item_count`, `code_block_count`, `hyphenation_repair_count`
- `rag_table_output`, `rag_table_record_count`, `rag_table_file_count`
- `rag_text_block_record_count`, `rag_text_block_file_count`
- `semantic_unit_record_count`, `semantic_unit_file_count`
- `requirement_record_count`, `requirement_file_count`
- `cross_ref_record_count`, `cross_ref_file_count`
- `semantic_low_confidence_count`, `unresolved_cross_ref_count`, `normative_requirement_count`
- `retrieval_chunk_record_count`, `retrieval_chunk_file_count`
- `retrieval_chunk_max_token_estimate`, `retrieval_chunk_average_token_estimate`
- `retrieval_chunk_over_target_count`, `retrieval_chunk_duplicate_source_ref_count`
- `figure_rag_record_count`, `figure_rag_file_count`
- `domain_unit_record_count`, `domain_unit_file_count`
- `requirement_traceability_record_count`, `requirement_traceability_file_count`
- `technical_table_record_count`, `technical_table_file_count`
- `confidential_safe_mode`
- `font_heading_candidate_count`, `footnote_candidate_count`, `structure_low_confidence_count`

## text_blocks_rag.jsonl

Default JSONL output for RAG ingestion of normal document text.

Required per JSONL record:

- `block_id`
- `page`
- `block_index`
- `block_type`
- `text`
- `bbox`
- `line_indices`
- `heading_path`
- `parent_heading_block_id`
- `classification_confidence`
- `classification_reasons`

Policy:

- `block_type` is one of `heading`, `paragraph`, `list`, `code`, `footnote`, `caption`.
- `text` is extracted source text, not a summary or paraphrase.
- Ambiguous structure is emitted as `paragraph` with conservative diagnostics in `report.json`.

## rag_tables.md

Optional output controlled by `--rag-table-output markdown|both`.

Required per table section:

- source page/table identity
- caption when available
- Markdown or HTML table body selected by table safety policy

## tables_rag.jsonl

Optional output controlled by `--rag-table-output jsonl|both`.

Required per JSONL record:

- `table_id`
- `table_row_id`
- `page`
- `table_index`
- `source_mode`
- `headers`
- `row_index`
- `cells`
- `row_text`
- `bbox`
- `quality_score`
- `fallback_reasons`
- `header_depth`
- `header_confidence`
- `rag_header_strategy`

Optional continuation fields:

- `continuation_group`
- `continued_from_page`
- `continued_to_page`
- `continuation_confidence`
- `continuation_reasons`
- `continuation_features`

## semantic_units_rag.jsonl

Default JSONL output for spec-level RAG semantics derived from `text_blocks_rag.jsonl` and table row sidecars.

Required per JSONL record:

- `semantic_id`
- `semantic_index`
- `semantic_type`
- `text`
- `source_refs`
- `page_range`
- `bbox`
- `heading_path`
- `parent_section_id`
- `canonical_key`
- `normative_strength`
- `classification_confidence`
- `classification_reasons`

Policy:

- `semantic_type` is one of `section`, `requirement`, `definition`, `parameter`, `procedure_step`, `note`, `warning`, `reference`.
- `text` is extracted source text, not a summary or paraphrase.
- `normative_strength` is one of `required`, `prohibited`, `recommended`, `optional`, `informative`, `unknown`.
- Low-confidence normative or definition candidates are not promoted to semantic records.

## requirements_rag.jsonl

Default JSONL output containing the `semantic_type == "requirement"` subset of `semantic_units_rag.jsonl`.

Required per JSONL record:

- Same field contract as `semantic_units_rag.jsonl`

Policy:

- Only clear normative keywords such as `shall`, `shall not`, `should`, `may`, `required`, `prohibited`, `mandatory`, and `optional` are emitted.
- `will` is treated as informative and is not promoted to a requirement.

## cross_refs_rag.jsonl

Default JSONL output for section/table/figure/appendix and technical reference provenance.

Required per JSONL record:

- `ref_id`
- `source_refs`
- `source_text`
- `target_type`
- `target_label`
- `target_key`
- `normalized_target_key`
- `candidate_count`
- `target_ref`
- `resolved`
- `unresolved_reason`
- `heading_path`
- `classification_confidence`
- `classification_reasons`

Policy:

- `target_type` may include `section`, `table`, `figure`, `appendix`, `requirement`, `log_page`, `feature`, `opcode`, `register`, or `unknown`.
- Unresolved references are preserved with `resolved: false`, `unresolved_reason`, `normalized_target_key`, and `candidate_count` for downstream diagnostics.

## requirement_traceability_rag.jsonl

Default JSONL output for requirement traceability and conformance matrix ingestion.

Required per JSONL record:

- `trace_id`
- `trace_index`
- `requirement_id`
- `normative_strength`
- `text`
- `condition`
- `applicability`
- `dependency_refs`
- `exception_text`
- `testability_hint`
- `page_range`
- `bbox`
- `heading_path`
- `source_refs`
- `classification_confidence`
- `classification_reasons`

Policy:

- Records are derived from conservative requirement semantic units and stable table rows such as OCP-style `Requirement ID / Description` tables.
- `testability_hint` is deterministic metadata only. It is not a generated test case.
- Customer-confidential source text is preserved only in local output; use `--confidential-safe-mode` when sharing metadata outside the local workspace.

## technical_tables_rag.jsonl

Default JSONL output for typed technical table rows used by storage/security spec RAG.

Required per JSONL record:

- `technical_table_unit_id`
- `technical_table_unit_index`
- `unit_type`
- `page`
- `table_id`
- `table_row_id`
- `row_index`
- `text`
- `raw_cells`
- `bit_range`
- `field_name`
- `value`
- `meaning`
- `reset_default`
- `access`
- `requirement_ref`
- `opcode`
- `command`
- `log_identifier`
- `feature_identifier`
- `bbox`
- `source_refs`
- `classification_confidence`
- `classification_reasons`

Policy:

- `unit_type` is conservative and may include `command_opcode`, `opcode`, `log_page`, `feature_identifier`, `register_field`, `bitfield`, `enum_value`, `requirement_row`, `security_method`, `security_object`, `security_authority`, `security_field`, or `technical_parameter`.
- Original `raw_cells` and `text` remain the source of truth. Normalized fields are populated only when header/cell evidence is clear.

## retrieval_chunks_rag.jsonl

Default JSONL output for vector DB ingest candidates. It is derived from text blocks, semantic units, requirements, table rows, and opt-in domain units.

Required per JSONL record:

- `chunk_id`
- `schema_version`
- `chunk_index`
- `chunk_type`
- `text`
- `source_sha256`
- `source_refs`
- `page_range`
- `bbox`
- `heading_path`
- `semantic_types`
- `normative_strength`
- `retrieval_priority`
- `char_count`
- `token_estimate`
- `section_path`
- `chunk_group_id`
- `source_record_count`
- `source_dedupe_key`
- `chunk_boundary_policy`
- `chunk_boundary_reasons`
- `parent_chunk_id` / `chunk_part_index` / `chunk_part_count` when a source chunk is split by token budget

Optional per JSONL record:

- `embedding_text`: context-prefixed text for index embedding. It may add section, caption, header, table id, or unit type context for table-like chunks.
- `embedding_token_estimate`: token budget estimate for `embedding_text`.
- `embedding_text_strategy`: deterministic strategy label such as `table_context_prefix`.
- `merged_source_chunk_ids`: original chunk ids represented by a merged sibling text chunk.
- `merged_source_chunk_count`: number of original text chunks represented by a merged sibling text chunk.
- `merge_strategy`: deterministic strategy label such as `adjacent_text_block_same_section_token_budget`.
- `previous_chunk_id`: previous chunk id in the same `chunk_group_id`, when relationship metadata is enabled and a previous chunk exists.
- `next_chunk_id`: next chunk id in the same `chunk_group_id`, when relationship metadata is enabled and a next chunk exists.
- `section_anchor_chunk_id`: first chunk id with the same `section_path`, omitted when the current chunk is already the section anchor.
- `related_chunk_ids`: ordered list of available neighbor/section-anchor chunk ids for lightweight citation expansion.
- `relationship_strategy`: deterministic strategy label such as `chunk_group_prev_next_section_anchor`.

Policy:

- `text` remains extracted source text or deterministic row text, not a summary or paraphrase.
- `embedding_text`, when present, is an index helper only. It must not replace `text` for citation or source-of-truth checks.
- `rag_merge_sibling_text_chunks`, when enabled, only merges adjacent `text_block` chunks with the same page/section/heading context and only while the combined `token_estimate` stays within `retrieval_chunk_max_tokens`.
- Merged sibling text chunks use `chunk_boundary_policy="merged_sibling_text_blocks"` and keep every original source id in `source_refs`; requirement, requirement trace, table row, technical table, and domain unit chunks are not merged by this policy.
- `rag_chunk_relationship_metadata`, when enabled, is added after merge/split optimization so `previous_chunk_id`, `next_chunk_id`, and `section_anchor_chunk_id` point to final chunk ids in the same JSONL file.
- `source_refs` must be sufficient to trace a chunk back to the originating block, table row, requirement, requirement trace, technical table unit, or domain unit.
- `source_sha256` is the lowercase SHA-256 of the input PDF and is copied into each chunk for downstream index identity checks.
- Chunk boundary fields are deterministic diagnostics for long technical specs; token-budget splitting does not summarize or rewrite source text.

## figures_rag.jsonl

Default JSONL output for figure/diagram provenance.

Required per JSONL record:

- `figure_id`
- `page`
- `figure_index`
- `record_type`
- `status`
- `path`
- `bbox`
- `caption_text`
- `caption_source`
- `caption_confidence`
- `heading_path`
- `ocr_candidates`
- `source_refs`
- `figure_kind`
- `diagram_candidate`
- `detected_labels`
- `nearby_text_refs`
- `classification_confidence`
- `classification_reasons`

Optional diagnostics:

- `diagram_label_diagnostics`
- `captionless_diagnostics`

Policy:

- The sidecar records extracted image assets and excluded image candidates.
- `figure_kind` is conservative metadata such as `image`, `diagram`, `state_machine`, `sequence_diagram`, or `register_layout`.
- Low-confidence OCR/label candidates stay in `diagram_label_diagnostics.rejected_ocr_candidates`; only promoted candidates appear in `detected_labels`.
- Captionless candidates may include `captionless_diagnostics` with evidence counts and rejection reasons. This is diagnostics-only metadata and does not create a generated caption or visual description.
- No generated visual description is added by default.

## domain_units_rag.jsonl

Optional JSONL output controlled by `--domain-adapter`.

Required per JSONL record:

- `domain_unit_id`
- `domain_unit_index`
- `domain`
- `unit_type`
- `name`
- `value`
- `description`
- `text`
- `source_refs`
- `page_range`
- `bbox`
- `heading_path`
- `classification_confidence`
- `classification_reasons`

Policy:

- Default adapter is `none`, so this file is only written when a domain adapter is explicitly selected.
- Supported adapter profiles are `nvme`, `pcie`, `ocp`, `tcg`, and `customer-requirements`.
- TCG domain units may use `security_method`, `security_object`, `security_authority`, or `security_field`; TCG is expected to map to SSD `HIL/TCG` without a CustomerRequirement fallback.
- Adapter profiles consume the typed technical table sidecar where possible and keep domain heuristics out of the default conversion path.

## corpus_manifest.json

Batch-mode JSON output for multi-PDF RAG corpus ingest.

Required:

- `schema_version`
- `purpose`
- `input_dir`
- `output_dir`
- `documents`

Required per `documents[]` record:

- `doc_id`
- `input_pdf`
- `source_sha256`
- `output_dir`
- `status`
- `selected_pages`
- `skipped`
- `files`

Policy:

- `purpose` is `rag_corpus_ingest`.
- `files` contains core outputs and any generated RAG sidecars for that document.

## corpus_diff_report.json

Batch-mode JSON output emitted when `--previous-corpus-manifest` is provided.

Required:

- `schema_version`
- `purpose`
- `previous_manifest`
- `current_manifest`
- `entries`
- `summary`

Stable fields:

- `entries[].doc_id`
- `entries[].status`: one of `added`, `changed`, `unchanged`, `removed`
- `entries[].previous_source_sha256`
- `entries[].current_source_sha256`
- `summary.changed_count`, `summary.unchanged_count`, `summary.removed_count`, `summary.added_count`

Policy:

- Diffing is deterministic and based on `doc_id` plus `source_sha256`.
- It is intended to minimize corpus reconversion and vector DB re-indexing.

## requirement_change_impact_report.json

Batch-mode JSON output emitted with `corpus_diff_report.json` when `--previous-corpus-manifest` is provided.

Required:

- `schema_version`
- `purpose`
- `previous_manifest`
- `current_manifest`
- `entries`
- `summary`

Stable fields:

- `entries[].doc_id`
- `entries[].requirement_key`
- `entries[].requirement_id`
- `entries[].status`: one of `added`, `changed`, `removed`
- `entries[].changed_fields`
- `entries[].previous_trace_ids`, `entries[].current_trace_ids`
- `entries[].previous_texts`, `entries[].current_texts`
- `entries[].previous_source_refs`, `entries[].current_source_refs`
- `entries[].previous_normative_strengths`, `entries[].current_normative_strengths`
- `entries[].previous_testability_hints`, `entries[].current_testability_hints`
- `summary.changed_count`, `summary.removed_count`, `summary.added_count`, `summary.unchanged_count`
- `summary.documents_compared`, `summary.documents_with_requirement_changes`

Policy:

- The report compares `requirement_traceability_rag.jsonl` records across corpus manifests.
- It preserves original requirement text and source refs; it does not summarize, paraphrase, or infer impact.
- Records without explicit requirement IDs use deterministic `unidentified:<source_id>` keys so downstream tools can still trace source provenance.

## index_contract_report.json

Local-only JSON output from `scripts/validate_index_contract.py`.

Required:

- `schema_version`
- `purpose`
- `status`
- `passed`
- `output_dir`
- `targets`
- `summary`
- `files`
- `findings`

Policy:

- `purpose` is `rag_index_contract_validation`.
- `targets` may include `openai`, `azure-ai-search`, `langchain`, and `llamaindex`.
- `findings[]` are sorted deterministically by severity, file, line, field, and code.
- `severity` is one of `error`, `warning`, or `info`.
- The validator checks required field and type coverage for `retrieval_chunks_rag.jsonl`, `tables_rag.jsonl`, `technical_tables_rag.jsonl`, and `requirement_traceability_rag.jsonl` before external indexing.
- The validator must not call external services or create embeddings.
- Confidential-safe findings are advisory for metadata sharing. The validator does not redact source `text`.

## provenance_integrity_report.json

Local-only JSON output from `scripts/validate_provenance_integrity.py`.

Required:

- `schema_version`
- `purpose`
- `status`
- `passed`
- `output_dir`
- `summary`
- `files`
- `findings`

Policy:

- `purpose` is `rag_provenance_integrity_validation`.
- `findings[]` are sorted deterministically by severity, file, line, field, code, source type, and source id.
- `source_refs` must resolve to the corresponding local sidecar record whenever the source type is supported.
- Retrieval chunk `source_record_count` and `source_dedupe_key` are checked against actual `source_refs`.
- The validator must not call external services or infer missing provenance.

## artifact_integrity_report.json

Local-only JSON output from `scripts/validate_artifact_integrity.py`.

Required:

- `schema_version`
- `purpose`
- `status`
- `passed`
- `output_dir`
- `summary`
- `files`
- `findings`

Stable summary fields:

- `checked_files`, `checked_records`, `checked_links`, `checked_assets`
- `missing_assets`, `orphan_assets`, `sidecar_count_mismatches`, `file_map_missing_count`
- `error_count`, `warning_count`, `info_count`

Finding fields:

- `severity`
- `code`
- `file`
- `line`
- `record_id`
- `field`
- `path`
- `message`

Policy:

- `purpose` is `output_artifact_integrity_validation`.
- Missing referenced assets and sidecar count mismatches are errors.
- Orphan assets and confidential-safe absolute paths are warnings.
- The validator checks local files only and does not mutate conversion outputs.

## local_corpus_evidence_pack.json

Optional redacted JSON output from `scripts/run_ssd_corpus_profile.py --evidence-pack`.

Required:

- `schema_version`
- `purpose`
- `profile_label`
- `profile_fingerprint`
- `redaction_policy`
- `summary`
- `domains`
- `documents`
- `failure_signatures`

Stable summary fields:

- `document_count`, `failed_document_count`, `failure_signature_count`
- `conversion_failure_count`, `contract_error_count`, `contract_warning_count`
- `rag_threshold_failure_count`, `budget_failure_count`

Policy:

- `purpose` is `local_technical_corpus_evidence_pack`.
- The evidence pack uses redacted document labels such as `document-000001`.
- Raw `input_pdf`, `output_dir`, command arguments, profile path, source filename, and eval query text are not included.
- Failure signatures are deterministic and group conversion, SSD contract, RAG threshold, and budget failures by domain/spec/category/code/metric.
- The pack is intended for sharing failure patterns from private/local technical corpora without sharing source PDFs or local filesystem metadata.

## corpus_evidence_analysis_report.json

Local-only JSON output from `scripts/analyze_corpus_evidence_pack.py`.

Required:

- `schema_version`
- `purpose`
- `source_profile_label`
- `source_profile_fingerprint`
- `summary`
- `category_hotspots`
- `domain_hotspots`
- `followup_hints`

Policy:

- `purpose` is `corpus_evidence_signature_analysis`.
- The report consumes only redacted `local_corpus_evidence_pack.json` input.
- Hotspots group failure signatures by category and domain/spec profile with deterministic ordering.
- Follow-up hints are deterministic backlog signals only. They do not infer missing source text or call external RAG/indexing services.

Example:

```bash
python scripts/analyze_corpus_evidence_pack.py --evidence-pack local_corpus_evidence_pack.json
```

## corpus_evidence_trend_report.json

Local-only JSON output from `scripts/compare_corpus_evidence_packs.py`.

Required:

- `schema_version`
- `purpose`
- `baseline_profile_fingerprint`
- `current_profile_fingerprint`
- `passed_trend_gate`
- `summary`
- `signatures`

Policy:

- `purpose` is `corpus_evidence_trend_comparison`.
- Baseline/current packs are compared by deterministic `signature_id`.
- `signatures[].status` is one of `added`, `persisting`, or `resolved`.
- `--fail-on-new-signature` returns non-zero when new error signatures appear.
- The comparison uses redacted evidence packs only and does not access source PDFs, raw paths, commands, or query text.

Example:

```bash
python scripts/compare_corpus_evidence_packs.py --baseline old.json --current new.json --fail-on-new-signature
```

## requirement_impact_review_pack.json / requirement_impact_review_pack.md

Optional reviewer-friendly output generated by `scripts/build_requirement_impact_review_pack.py`.

Stable JSON fields:

- `schema_version`
- `purpose`
- `source_report`
- `previous_manifest`, `current_manifest`
- `summary.total_review_items`
- `summary.status_counts`
- `summary.changed_field_counts`
- `review_items[]`
- `review_items[].review_id`
- `review_items[].doc_id`
- `review_items[].requirement_key`
- `review_items[].requirement_id`
- `review_items[].status`
- `review_items[].changed_fields`
- `review_items[].recommendation`
- `review_items[].previous_text_preview`, `review_items[].current_text_preview`
- `review_items[].previous_source_refs`, `review_items[].current_source_refs`

Policy:

- The pack is derived from `requirement_change_impact_report.json`.
- Recommendations are deterministic status/changed-field labels, not generated impact explanations.

## sanitized_report.json

Optional JSON output emitted by `--confidential-safe-mode`.

Policy:

- The report schema matches `report.json`.
- Public metadata records `confidential_safe_mode: true` and local-only/no-external-call options in `manifest.json`.
- Batch file maps and manifest paths are redacted to filenames or document ids where possible.

## debug/

Debug artifacts are opt-in with `--debug` and are not part of the stable public schema. They should remain deterministic enough for local diagnosis, but external integrations should not depend on their exact field set.

Typical files:

- `page-0001-raw-lines.json`
- `page-0001-ordered-lines.json`
- `page-0001-normalized-lines.json`
- `page-0001-table-candidates.json`
- `page-0001-image-candidates.json`

## Release Smoke

릴리스 전에 다음을 확인한다.

```bash
python -m build
python -m pip install dist/*.whl
python -m pdf2md --help
pdf2md --help
python scripts/export_output_schema.py --check
```

새 runtime dependency를 추가하면 README, Windows guide, CI Python matrix 문서를 함께 갱신한다.
