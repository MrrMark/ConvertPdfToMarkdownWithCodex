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
- `docs/schema/docling_benchmark_report.schema.json`
- `docs/schema/docling_artifact_comparison.schema.json`
- `docs/schema/latest_nvme_spec_benchmark_report.schema.json`
- `docs/schema/latest_ocp_datacenter_nvme_ssd_benchmark_report.schema.json`
- `docs/schema/ocr_backend_probe_report.schema.json`
- `docs/schema/figure_description_eval_report.schema.json`
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

- `options.image_mode`, `options.table_mode`, `options.rag_table_output`, `options.rag_profile` when a non-default RAG profile was selected, `options.rag_text_blocks_output`, `options.semantic_layer_output`, `options.ocr_lang`, `options.ocr_backend`
- `options.rag_text_blocks_jsonl_filename`, `options.semantic_units_jsonl_filename`, `options.requirements_jsonl_filename`, `options.cross_refs_jsonl_filename`
- `options.requirement_traceability_jsonl_filename`, `options.technical_tables_jsonl_filename`
- `options.retrieval_chunks_jsonl_filename`, `options.figures_rag_jsonl_filename`, `options.figure_descriptions_jsonl_filename`, `options.figure_structures_jsonl_filename`, `options.domain_adapter`, `options.domain_units_jsonl_filename`
- `options.manual_domain_adapter_label`, `options.manual_domain_adapter_keywords` when `options.domain_adapter="manual"` and those inputs were provided
- `options.retrieval_chunk_max_tokens`, `options.retrieval_tokenizer`, `options.rag_contextual_embedding_text`, `options.rag_merge_sibling_text_chunks`, `options.rag_chunk_relationship_metadata`, `options.rag_figure_text_chunks` when enabled
- `options.figure_region_ocr`, `options.rag_generated_figure_descriptions`, `options.figure_description_backend`, `options.figure_structure_extraction` when enabled
- `options.output_profile`, `options.rag_sidecar_scope`, `options.rag_sidecar_omitted_outputs`, `options.rag_sidecar_omitted_reason` when a non-full output scope was selected
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
- `technical_profile_domain_adapter_missing`
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

Non-full sidecar scope summary fields:

- `output_profile`: `full` or `fast`, present when a non-full output scope is selected.
- `rag_sidecar_scope`: effective sidecar scope, one of `full`, `minimal`, or `none`.
- `rag_sidecar_omitted_outputs`: sidecar filenames skipped compared with the default full scope.
- `rag_sidecar_omitted_reason`: stable reason code, currently `rag_sidecar_scope_omitted`.

Assetless figure text summary fields:

- `rag_figure_text_chunks`: present and `true` when `--rag-figure-text-chunks` was enabled.
- `figure_text_chunk_record_count`: final `retrieval_chunks_rag.jsonl` records with `chunk_type="figure_text"`.
- `figure_region_ocr`: present and `true` when `--figure-region-ocr` was enabled.
- `figure_region_ocr_attempted_count`, `figure_region_ocr_candidate_count`, `figure_region_ocr_promoted_label_count`, `figure_region_ocr_low_confidence_count`: deterministic OCR evidence promotion counters.
- `figure_region_ocr_render_attempted_count`, `figure_region_ocr_region_candidate_count`, `figure_region_ocr_accepted_region_count`, `figure_region_ocr_rejected_region_count`, `figure_region_ocr_crop_rejected_count`, `figure_region_ocr_runtime_unavailable_count`: report-only figure bbox crop OCR counters.
- `rag_generated_figure_descriptions`: present and `true` when `--rag-generated-figure-descriptions` was enabled.
- `figure_description_backend`: selected backend label, currently emitted for deterministic context-only description records.
- `figure_description_record_count`, `figure_description_file_count`, `figure_description_low_confidence_count`, `figure_description_skipped_no_evidence_count`, `figure_description_chunk_record_count`: generated figure description sidecar and chunk counters.
- `figure_structure_extraction`: present and `true` when `--figure-structure-extraction` was enabled.
- `figure_structure_record_count`, `figure_structure_file_count`, `figure_structure_low_confidence_count`, `figure_structure_skipped_no_structure_count`, `figure_structure_chunk_record_count`: conservative figure structure sidecar and chunk counters.
- `manual_domain_adapter_label`, `manual_domain_adapter_keywords`: present only when `--domain-adapter manual` was selected and those inputs were provided.

`summary.table_quality[]` optional diagnostics:

- `strategy_runs`: table extraction strategies actually executed for the page when adaptive strategy skipping occurred.
- `adaptive_skipped_strategies`: fallback strategies skipped because the default candidate met conservative quality thresholds.
- `adaptive_skip_reason`: stable reason code for adaptive skipping, currently `default_candidate_quality_sufficient`.

Warning taxonomy policy:

- Known warning codes have a stable domain and default severity in code.
- `actionable_warning_count` and `advisory_warning_count` are derived from that taxonomy plus limited context-sensitive rules, such as blank-page `OCR_EMPTY_RESULT`.
- Advisory warnings, including expected complex table HTML fallback, do not by themselves set `partial_success` or exit code `2`.
- Actionable OCR/table/image warnings and failed-page signals may set `partial_success` and exit code `2`.

## debug/table-quality-review-pack.json

Optional local-only artifact written when `--debug` is enabled.

Fields:

- `schema_version`
- `item_count`, `low_quality_count`
- `triage_counts.actionable`, `triage_counts.advisory`
- `items[].page`, `table_id`, `table_index`, `bbox`, `mode`, `quality_score`
- `items[].fallback_reasons`, `header_strategy`, `header_confidence`
- `items[].row_count`, `empty_cell_ratio`, `column_placeholder_header_ratio`
- `items[].technical_table_unit_count`, `domain_unit_count`
- `items[].sample_row_text_sha256`, `sample_row_text_preview`
- `items[].triage_status`, `triage_reasons`

Policy:

- The pack is for local quality triage and is not written by default.
- `sample_row_text_preview` is truncated; full source text remains in the normal local outputs.

## docling_benchmark_report.json

Optional local-only benchmark output written by `scripts/benchmark_docling_comparison.py` and reused by
`scripts/run_latest_nvme_command_set_eval.py`.

Required:

- `schema_version`
- `purpose="docling_benchmark_comparison"`
- `document_label`
- `source_sha256`
- `local_only=true`
- `raw_content_included=false`
- `image_bytes_included=false`
- `customer_paths_included=false`
- `summary`
- `runs[]`
- `findings[]`

Stable summary fields:

- `compared`
- `current_tool_status`
- `docling_status`
- `docling_available`
- `finding_count`
- `error_count`
- `warning_count`
- `layout_comparison_mode`: `off` or `summary`
- `layout_comparison_enabled`

Stable run fields:

- `tool`: `pdf2md` or `docling`
- `status`: `success`, `partial_success`, `failed`, or `skipped`
- `output_dir`: sanitized output folder name only, never an absolute customer path
- `duration_ms`
- `pages_per_second`
- `metrics`
- `artifact_hashes`
- `error_code`
- `advisory`

Policy:

- Docling 미설치 환경은 실패가 아니라 `status="skipped"`와 `docling_not_installed` advisory finding으로 기록한다.
- `--require-docling` 또는 release gate `--gates docling`이 명시된 경우 Docling 미설치는 `docling_required_not_available` error finding으로 기록한다.
- script는 current-tool metric과 validator status를 계속 생성한다.
- raw Markdown body, raw Docling document dict, image bytes, input file path는 report에 넣지 않는다.
- optional OCR backend availability는 module availability boolean만 기록한다.
- current-tool metrics may include table count, low-quality table count, domain unit count, figure text chunk count,
  figure description/structure chunk count, and validator pass booleans.
- When `--layout-comparison-mode summary` is used, current-tool and Docling runs add sanitized count-only metrics such as `layout_table_candidate_count`, `layout_figure_candidate_count`, `layout_page_candidate_count`, and `layout_text_container_key_count`. These metrics are derived from report summaries or Docling dictionary keys, not raw document text.

## docling_artifact_comparison.json

Optional local-only sanitized artifact comparison written by `scripts/benchmark_docling_comparison.py`.

Required:

- `schema_version`
- `purpose="docling_sanitized_artifact_comparison"`
- `document_label`
- `source_sha256`
- `local_only=true`
- `raw_content_included=false`
- `image_bytes_included=false`
- `customer_paths_included=false`
- `summary`
- `artifacts[]`
- `metric_deltas[]`
- `findings[]`

Stable summary fields:

- `current_artifact_count`
- `docling_artifact_count`
- `comparable_metric_count`
- `hash_match_count`
- `hash_mismatch_count`
- `layout_comparison_mode`
- `layout_comparable`

Stable artifact fields:

- `tool`
- `artifact`
- `exists`
- `size_bytes`
- `sha256`
- `virtual` for Docling in-memory exports

Policy:

- current-tool artifacts are represented by existence, byte size, and SHA-256 for committed-safe filenames only.
- Docling Markdown/dict exports are not written as raw files by the harness; only virtual artifact hash and size are recorded.
- Layout comparison mode is comparison-only. It records count metrics and metric deltas; it does not merge Docling layout into `document.md`, tables, figures, or RAG sidecars.

## latest_nvme_spec_benchmark_report.json

Optional local-only benchmark summary written by `scripts/run_latest_nvme_spec_benchmark.py`.

Required:

- `schema_version`
- `purpose="latest_nvme_spec_benchmark"`
- `spec_document_type`: `base` or `nvm_command_set`
- `latest_spec_set`
- `latest_release_date`
- `expected_spec_title`
- `source_url`
- `source_sha256`
- `mode`: `full_precision` or `fast_smoke`
- `option_matrix`
- `summary_counts`
- `command_set_eval`

Stable summary fields:

- `page_count`
- `conversion_duration_ms`
- `sidecar_file_count`
- `sidecar_total_bytes`
- `sidecar_file_sizes`
- `retrieval_chunk_count`
- `requirement_count`
- `traceability_record_count`
- `technical_table_unit_count`
- `domain_unit_count`
- `contract_validation_status`
- `contract_validation_passed`
- `command_set_eval_status`
- `command_set_eval_passed`
- `command_set_eval_query_count`
- `command_set_eval_expected_source_coverage`
- `warning_count`
- `error_count`

Policy:

- This report covers the latest NVMe Base and NVM Command Set benchmark paths under the same `technical_spec_rag + domain_adapter=nvme` contract.
- `full_precision` is for whole-document local evaluation. `fast_smoke` defaults to the first five pages unless `--pages` overrides it.
- For `spec_document_type="nvm_command_set"`, `command_set_eval` records the P2 local query gate for representative `command_opcode`, `command_dword_field`, `command_pointer_field`, and `status_code` rows.
- `command_set_eval` is metrics-only: status, pass/fail, query count, required/covered/missing unit types, and aggregate retrieval metrics such as `hit_at_k`, `mrr`, `expected_source_coverage`, and `table_field_coverage`.
- The report includes source URL, source SHA-256, option matrix, sidecar file sizes, summary counts, sanitized SSD contract status, and sanitized Command Set eval status only.
- Raw spec text, raw Markdown body, generated query strings, retrieved chunk text, table row content, image bytes, and local input PDF paths are not embedded.
- The converted output directory is referenced by label only (`conversion`); keep the source PDF and full converted output outside committed fixtures unless intentionally creating sanitized test artifacts.

## latest_ocp_datacenter_nvme_ssd_benchmark_report.json

Optional local-only benchmark summary written by `scripts/run_latest_ocp_datacenter_nvme_ssd_benchmark.py`.

Required:

- `schema_version`
- `purpose="latest_ocp_datacenter_nvme_ssd_benchmark"`
- `expected_spec_title="Datacenter NVMe SSD Specification"`
- `expected_version="2.7"`
- `expected_date_marker="01082026"`
- `source_url`
- `source_sha256`
- `mode`: `full_precision` or `fast_smoke`
- `option_matrix`
- `summary_counts`

Stable summary fields:

- `page_count`
- `conversion_duration_ms`
- `sidecar_file_count`
- `sidecar_total_bytes`
- `sidecar_file_sizes`
- `retrieval_chunk_count`
- `requirement_count`
- `traceability_record_count`
- `technical_table_unit_count`
- `domain_unit_count`
- `ocp_requirement_unit_count`
- `contract_validation_status`
- `contract_validation_passed`
- `warning_count`
- `error_count`

Policy:

- This report covers the latest OCP Datacenter NVMe SSD benchmark path under `technical_spec_rag + domain_adapter=ocp`.
- OCP validation requires requirement domain units with normalized `requirement_id`, `requirement_prefix`, `requirement_family`, and source table row metadata.
- The report includes source URL, source SHA-256, option matrix, sidecar file sizes, summary counts, and sanitized SSD contract status only.
- Raw spec text, raw Markdown body, generated query strings, retrieved chunk text, table row content, image bytes, and local input PDF paths are not embedded.
- OCP P2 query eval is intentionally tracked as a planned metrics-only extension and is not enabled in the P0 benchmark report.

## ocr_backend_probe_report.json

Optional local-only OCR backend readiness probe written by `scripts/probe_ocr_backends.py`.

Required:

- `schema_version`
- `purpose="multi_ocr_backend_probe"`
- `ocr_lang`
- `local_only=true`
- `raw_content_included=false`
- `image_bytes_included=false`
- `customer_paths_included=false`
- `summary`
- `backends[]`

Stable summary fields:

- `total_backend_count`
- `available_backend_count`
- `ready_backend_count`
- `requested_languages`
- `ready_backends`
- `unavailable_backends`
- `recommended_backend`
- `require_ready`

Stable backend fields:

- `backend`: `tesseract`, `tesseract-cli`, `rapidocr`, `easyocr`, `ocrmac`, or `docling`
- `status`: `ready`, `available`, or `unavailable`
- `ready`
- `module`, `module_available`
- `executable`, `executable_available`
- `platform_supported`
- `confidence_normalization`
- `language_data`
- `dependencies[]`
- `hints[]`

Policy:

- The probe never runs OCR on document content and does not include PDF text, image bytes, or customer paths.
- Tesseract language data is checked when the backend uses the Tesseract runtime.
- Non-Tesseract backend language support is recorded as unchecked until a backend adapter normalizes it.
- Confidence values are not compared across backends until normalized into the reported `normalized_unit`.
- metric deltas compare numeric values only and leave non-numeric or nested values with `delta=null`.

## figure_description_eval_report.json

Optional local-only evaluation output written by `scripts/evaluate_figure_descriptions.py`.

Required:

- `schema_version`
- `purpose="local_figure_description_eval"`
- `local_only=true`
- `raw_images_included=false`
- `raw_pdf_text_included=false`
- `customer_paths_included=false`
- `min_confidence`
- `summary`
- `findings[]`

Stable summary fields:

- `figure_record_count`
- `description_record_count`
- `figure_description_chunk_count`
- `generated_text_record_count`
- `evidence_backed_record_count`
- `low_confidence_count`
- `missing_source_ref_count`
- `missing_source_evidence_count`
- `visual_pixels_interpreted_count`
- `backend_invoked_count`
- `missing_retrieval_chunk_count`
- `error_count`
- `warning_count`
- `passed`

Stable finding fields:

- `severity`: `error` or `warning`
- `code`
- `description_id`
- `figure_id`
- `chunk_id`
- `message`
- `details`

Policy:

- The evaluator reads `figure_descriptions_rag.jsonl`, `figures_rag.jsonl`, and `retrieval_chunks_rag.jsonl` only.
- It does not read raw image files or PDF pages and does not call VLM, Docling picture description, remote APIs, or embedding services.
- Passing records must be generated helper text with `generated_text=true`, `backend_status="not_invoked_context_only"`, source refs, source evidence, and retrieval chunk linkage.
- `visual_pixels_interpreted=true` or any backend invocation is an error in this local-only evaluation path.
- Low confidence and missing retrieval chunk linkage are warnings unless a stricter release policy wraps the report.

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

Additional stable identity fields when an input source hash is available:

- `source_sha256`
- `source_dedupe_key`
- `stable_source_id`
- `stable_requirement_seed`

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
- `target_ref` normally points to an extracted heading, caption, table, or table row target. When a reference is resolved by a deterministic fallback target rather than an extracted block, `target_ref` may start with `pdf-outline-` or `pdf-list-`.
- Fallback-resolved records identify their source through `classification_reasons` such as `target_source_pdf_outline` or `target_source_pdf_list`; these are provenance hints only and do not add generated text to `document.md`.
- External document references and terminology labels that are not local targets may be skipped instead of being emitted as unresolved local cross-references.
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
- `candidate_kind`
- `is_requirement_candidate`
- `exclusion_reason`
- `domain_unit_id`
- `technical_table_unit_id`
- `table_id`
- `table_row_id`
- `section_path`
- `verification_intent`
- `conditions`
- `exceptions`
- `applicability_hint`
- `source_sha256`
- `source_dedupe_key`
- `stable_source_id`
- `stable_requirement_seed`
- `classification_confidence`
- `classification_reasons`

Policy:

- Records are derived from conservative requirement semantic units and stable table rows such as OCP-style `Requirement ID / Description` tables.
- NVMe Base and NVM Command Set specs use the same candidate contract: explicit requirement IDs are preserved when present, and requirement-like paragraphs without explicit IDs still carry `stable_requirement_seed` for downstream ID generation.
- `candidate_kind` may be `normative_requirement`, `structured_requirement`, `technical_parameter`, `definition`, `note`, `example`, `front_matter`, or `review_only`.
- `is_requirement_candidate=false` and `exclusion_reason` tell downstream systems not to auto-promote definitions, notes, examples, legal/front matter, or other review-only records into business requirement IDs.
- Precision filters are metadata-only: source text is preserved, and filtered candidates are marked with `candidate_kind` / `exclusion_reason` instead of being rewritten.
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
- `command_dword`
- `command_scope`
- `queue_type`
- `pointer_type`
- `command_context`
- `command_context_source`
- `related_command_unit_id`
- `related_command_opcode`
- `relationship_hints`
- `log_identifier`
- `feature_identifier`
- `register_name`
- `offset`
- `status_code_type`
- `status_code_value`
- `status_code_group`
- `error_class`
- `retry_hint`
- `controller_support`
- `namespace_support`
- `scope`
- `bbox`
- `source_refs`
- `source_sha256`
- `source_dedupe_key`
- `stable_source_id`
- `stable_requirement_seed`
- `classification_confidence`
- `classification_reasons`

Policy:

- `unit_type` is conservative and may include `command_opcode`, `opcode`, `command_dword_field`, `command_pointer_field`, `log_page`, `feature_identifier`, `register_field`, `status_code`, `queue_field`, `namespace_field`, `controller_field`, `support_requirement`, `data_structure_field`, `bitfield`, `enum_value`, `requirement_row`, `security_method`, `security_object`, `security_authority`, `security_field`, or `technical_parameter`.
- NVMe Base and NVM Command Set specs share the `domain_adapter="nvme"` contract. Command-set tables commonly map to `command_opcode`, `command_dword_field`, `command_pointer_field`, `status_code`, `feature_identifier`, `log_page`, `data_structure_field`, and `technical_parameter`; Base tables additionally commonly map to controller/register/queue/namespace fields.
- Command Set records may include normalized command metadata: `command_dword` such as `CDW10`, `command_scope`/`queue_type` such as `admin` or `io`, and `pointer_type` such as `metadata` or `data`.
- Command Set relationship metadata may include `command_context`, `command_context_source`, `related_command_unit_id`, `related_command_opcode`, and `relationship_hints`. These fields connect command opcode anchors with nearby CDW, pointer, and command-specific status rows when heading/table evidence is clear.
- Status code records may include deterministic taxonomy hints: `status_code_group`, `error_class`, and `retry_hint`. These are metadata hints only; `text` and `raw_cells` remain the source of truth.
- Original `raw_cells` and `text` remain the source of truth. Normalized fields are populated only when header/cell evidence is clear.

## retrieval_chunks_rag.jsonl

Default JSONL output for vector DB ingest candidates. It is derived from text blocks, semantic units, requirements, table rows, opt-in domain units, and opt-in figure text chunks.

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
- `stable_source_id`
- `stable_requirement_seed`
- `chunk_boundary_policy`
- `chunk_boundary_reasons`
- `parent_chunk_id` / `chunk_part_index` / `chunk_part_count` when a source chunk is split by token budget

Optional per JSONL record:

- `embedding_text`: context-prefixed text for index embedding. It may add section, caption, header, table id, unit type, or NVMe command relationship context for table-like chunks.
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

`figure_text` chunk policy:

- `chunk_type` is `figure_text`.
- It is generated only when `--rag-figure-text-chunks` is enabled.
- It uses observed caption text, heading path, detected labels, nearby text refs, and conservative `figure_kind` metadata.
- It does not contain generated picture descriptions, inferred semantics, or paraphrased explanations.
- `source_refs[]` points to `figures_rag.jsonl` by `figure_id`, page, and bbox. The retrieval chunk source ref intentionally omits image file path.
- Captionless or low-confidence records are skipped when they are diagnostics-only, or emitted with lower `retrieval_priority` when promoted evidence is present.

`figure_description` and `figure_structure` chunk policy:

- `chunk_type` is `figure_description` or `figure_structure`.
- They are generated only when `--rag-generated-figure-descriptions` or `--figure-structure-extraction` is enabled.
- `figure_description.generated_text=true` marks generated index helper text. It is not inserted into `document.md`.
- Current built-in records use deterministic context-only evidence: caption, heading path, detected labels, nearby text, and existing OCR candidates. They do not claim that raw pixels were interpreted by an external model.
- `figure_structure` records are context-derived structure hints for diagrams, waveforms, block diagrams, and circuit/schematic figures. Edges remain empty unless there is deterministic evidence.
- `source_refs[]` points to `figures_rag.jsonl` and the corresponding figure semantic sidecar record. Retrieval chunks intentionally omit image file paths.

Policy:

- `text` remains extracted source text or deterministic row text, not a summary or paraphrase.
- `embedding_text`, when present, is an index helper only. It must not replace `text` for citation or source-of-truth checks.
- Command Spec technical table chunks use higher `retrieval_priority` for command opcode, CDW, pointer, and command-linked status records. This is a deterministic re-ranking hint, not a change to source text.
- `rag_merge_sibling_text_chunks`, when enabled, only merges adjacent `text_block` chunks with the same page/section/heading context and only while the combined `token_estimate` stays within `retrieval_chunk_max_tokens`.
- Merged sibling text chunks use `chunk_boundary_policy="merged_sibling_text_blocks"` and keep every original source id in `source_refs`; requirement, requirement trace, table row, technical table, and domain unit chunks are not merged by this policy.
- `rag_chunk_relationship_metadata`, when enabled, is added after merge/split optimization so `previous_chunk_id`, `next_chunk_id`, and `section_anchor_chunk_id` point to final chunk ids in the same JSONL file.
- `source_refs` must be sufficient to trace a chunk back to the originating block, table row, requirement, requirement trace, technical table unit, figure record, or domain unit.
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
- `figure_region_ocr`: includes existing OCR candidate promotion plus optional report-only bbox crop OCR diagnostics. Nested `region_ocr.report_only=true` and `region_ocr.text_replaced=false` mean the OCR result did not replace Markdown/text extraction output.

Policy:

- The sidecar records extracted image assets and excluded image candidates.
- In `image_mode=placeholder` or `embedded`, `path` may be provenance only and the image file may not exist on disk.
- `figure_kind` is conservative metadata such as `image`, `diagram`, `state_machine`, `sequence_diagram`, or `register_layout`.
- Low-confidence OCR/label candidates stay in `diagram_label_diagnostics.rejected_ocr_candidates`; only promoted candidates appear in `detected_labels`.
- `figure_region_ocr.region_ocr` may record `candidate`, `runtime_unavailable`, or `rejected` status with reasons such as `missing_bbox`, `invalid_bbox`, `empty_result`, `language_data_missing`, or `ocr_failed`. Label-pattern and confidence rejection details stay in `figure_region_ocr.rejected_candidates`.
- Captionless candidates may include `captionless_diagnostics` with evidence counts and rejection reasons. This is diagnostics-only metadata and does not create a generated caption or visual description.
- No generated visual description is added by default.

## figure_descriptions_rag.jsonl

Optional JSONL output controlled by `--rag-generated-figure-descriptions`.

Required per JSONL record:

- `description_id`
- `description_index`
- `figure_id`
- `page`
- `bbox`
- `heading_path`
- `figure_kind`
- `text`
- `generated_text`
- `generation_strategy`
- `backend`
- `backend_status`
- `source_evidence`
- `source_refs`
- `classification_confidence`
- `classification_reasons`

Policy:

- Description text is generated helper text and is always separated from source Markdown.
- The current local implementation records `backend_status="not_invoked_context_only"` and `source_evidence.visual_pixels_interpreted=false`.
- Records are skipped when no caption, heading, detected label, or nearby text evidence exists.

## figure_structures_rag.jsonl

Optional JSONL output controlled by `--figure-structure-extraction`.

Required per JSONL record:

- `structure_id`
- `structure_index`
- `figure_id`
- `page`
- `bbox`
- `heading_path`
- `figure_kind`
- `structure_type`
- `nodes`
- `edges`
- `signals`
- `text`
- `generated_text`
- `derived_from_context`
- `source_refs`
- `classification_confidence`
- `classification_reasons`

Policy:

- Structure records are conservative, deterministic hints for retrieval, not a replacement for the original PDF image.
- Nodes and signals are created only from detected labels or other observed context. Edges remain empty unless deterministic evidence is available.
- Records are skipped when no diagram/label/structure signal is available.

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
- `source_sha256`
- `source_dedupe_key`
- `stable_source_id`
- `stable_requirement_seed`
- `classification_confidence`
- `classification_reasons`

Policy:

- Default adapter is `none`, so this file is only written when a domain adapter is explicitly selected.
- Supported adapter profiles are `nvme`, `pcie`, `ocp`, `tcg`, `spdm`, `customer-requirements`, and `manual`.
- NVMe domain units cover both NVMe Base and NVM Command Set specs. They may use `command`, `command_dword_field`, `command_pointer_field`, `log_page`, `feature`, `register_field`, `status_code`, `queue_field`, `namespace_field`, `controller_field`, `support_requirement`, `data_structure_field`, or `enum_value`. Their `normalized_fields` may include `canonical_name`, `opcode`, `command_dword`, `command_scope`, `queue_type`, `pointer_type`, `command_context`, `command_context_source`, `related_command_unit_id`, `related_command_opcode`, `relationship_hints`, `log_identifier`, `feature_identifier`, `register_name`, `offset`, `bit_range`, `field_name`, `status_code_type`, `status_code_value`, `status_code_group`, `error_class`, `retry_hint`, `controller_support`, `namespace_support`, `scope`, `access`, `reset_default`, and `requirement_ref`; empty values are omitted.
- OCP domain units use `requirement`. Their `normalized_fields` include `requirement_id`, `requirement_prefix`, `requirement_number`, `requirement_family`, `normative_strength`, `ssd_requirement_status`, related NVMe hints such as `related_command`, `related_log_identifier`, `related_feature_identifier`, and source row fields `source_table_id`/`source_table_row_id`; empty values are omitted.
- TCG domain units may use `security_method`, `security_object`, `security_authority`, `security_field`, `security_provider`, `locking_range`, `key_management`, or `session_state`; TCG is expected to map to SSD `HIL/TCG` without a CustomerRequirement fallback.
- SPDM domain units may use `spdm_message`, `spdm_request_response`, `spdm_measurement`, `spdm_certificate`, `spdm_algorithm`, `spdm_key_exchange`, or `spdm_session`; SPDM maps to SSD `HIL/SPDM`.
- Manual domain units keep `domain="manual"` and set `adapter_profile` to `--manual-domain-adapter-label` when provided, otherwise `manual`. `--manual-domain-adapter-keywords` only expands deterministic table header recognition; record `text`, `name`, `value`, and `description` are copied from observed table/technical-table provenance and are not generated.
- Adapter profiles consume the typed technical table sidecar where possible and keep domain heuristics out of the default conversion path.
- `stable_source_id` and `stable_requirement_seed` are deterministic metadata seeds. They do not replace the ordinal `domain_unit_id`; downstream systems should prefer them when generating business IDs across repeated conversions.

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
