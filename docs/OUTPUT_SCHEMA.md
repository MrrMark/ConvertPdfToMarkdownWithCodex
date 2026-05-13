# Output Schema Contract

이 문서는 `pdf2md` 산출물을 외부 RAG/indexing 파이프라인에서 안정적으로 참조하기 위한 schema 계약이다.

## 호환성 정책

- `schema_version`은 현재 `1.0`이다.
- required field 제거, 타입 변경, 의미 변경은 breaking change로 본다.
- optional field 추가는 backward-compatible 변경이다.
- JSON consumer는 모르는 field를 무시해야 한다.
- 산출물 경로와 asset 파일명은 동일 입력 + 동일 옵션 + 동일 버전에서 결정적으로 유지한다.

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

- `options.image_mode`, `options.table_mode`, `options.rag_table_output`, `options.ocr_lang`
- `images[].page`, `index`, `path`, `source`, `bbox`, `sha256`
- `images[].alt_text`, `caption_text`, `caption_source`, `dedupe_of`
- `excluded_images[].reason`, `classification`, `recovery_strategy`, `ocr_candidates`
- `tables[].page`, `index`, `mode`, `bbox`, `quality_score`, `fallback_reasons`
- `tables[].continuation_group`, `continued_from_page`, `continued_to_page`, `continuation_confidence`

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

## rag_tables.md

Optional output controlled by `--rag-table-output markdown|both`.

Required per table section:

- source page/table identity
- caption when available
- Markdown or HTML table body selected by table safety policy

## tables_rag.jsonl

Optional output controlled by `--rag-table-output jsonl|both`.

Required per JSONL record:

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
```

새 runtime dependency를 추가하면 README, Windows guide, CI Python matrix 문서를 함께 갱신한다.
