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

- `processed_pages`, `warning_count`, `failed_page_count`, `partial_success`
- `page_status_counts`
- `table_total`, `table_html_count`, `table_gfm_count`, `table_fallback_count`
- `table_fallback_reason_counts`, `table_low_quality_count`, `table_quality`
- `stage_durations_ms`, `pdf_open_count`, `pages_per_second`
- `page_cache_hits`, `page_cache_misses`, `text_line_extract_count`
- `heading_count`, `list_item_count`, `code_block_count`, `hyphenation_repair_count`
- `rag_table_output`, `rag_table_record_count`, `rag_table_file_count`
- `rag_text_block_record_count`, `rag_text_block_file_count`
- `semantic_unit_record_count`, `semantic_unit_file_count`
- `requirement_record_count`, `requirement_file_count`
- `cross_ref_record_count`, `cross_ref_file_count`
- `semantic_low_confidence_count`, `unresolved_cross_ref_count`, `normative_requirement_count`
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

Default JSONL output for section/table/figure/appendix reference provenance.

Required per JSONL record:

- `ref_id`
- `source_refs`
- `source_text`
- `target_type`
- `target_label`
- `target_ref`
- `resolved`
- `heading_path`
- `classification_confidence`
- `classification_reasons`

Policy:

- `target_type` is one of `section`, `table`, `figure`, `appendix`, `unknown`.
- Unresolved references are preserved with `resolved: false` for downstream diagnostics.

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
