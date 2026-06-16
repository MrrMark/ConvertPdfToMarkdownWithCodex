# PDF2MD MCP NVMe Base Stability Development Spec

Status: Implemented Q117 development spec.

## 1. Purpose

`ssd-verification-agent`에서 pdf2md MCP를 사용해 NVMe Base Specification 전체 PDF를 변환할 때
대형 문서, image/figure extraction, 장시간 실행, interrupt 상황에서 운영자가 재시도와 원인 분석을 할 수 있게 한다.

이번 작업의 우선 목표는 `SpecAnalysisAgent`가 요구하는 text/table/requirement/domain sidecar ingest 품질을 유지하면서,
이미지/도식 evidence가 필요 없는 경로에서는 image/figure 처리 비용을 명시적으로 제거하는 것이다.

## 2. Current Findings

현재 코드 기준 확인 사항:

- `ImageMode.PLACEHOLDER`는 Markdown image link 대신 placeholder comment를 쓰는 모드다.
- `placeholder`에서도 pipeline은 `pdf_context.get_image_boxes(page)`와 `extract_images(...)`를 호출한다.
- `technical_spec_rag_visual`은 figure text, region OCR, deterministic figure description, figure structure sidecar를 켠다.
- MCP `pdf2md_convert_pdf`는 단일 PDF 변환 tool만 제공하며, page-window orchestration과 merge contract는 없다.
- report에는 stage duration이 있으나 image extraction 중 page-level progress, timeout fallback, last processed image/page 정보가 부족하다.
- 변환 중단 시 최종 `report.json`을 항상 남기는 interrupted-state contract는 없다.

판단:

- `placeholder` 의미를 바꿔 image extraction을 skip하면 기존 assetless RAG 계약을 깨므로 별도 no-image mode가 필요하다.
- NVMe Base full conversion은 single-run보다 page-window conversion과 deterministic merge가 운영 안정성에 유리하다.
- `ssd-verification-agent`의 SpecAnalysisAgent ingest용 기본 경로는 visual sidecar보다 text/table/requirement/domain sidecar 우선이다.

## 3. Scope

이 repo에서 담당할 범위:

- true no-image conversion option and profile override
- image/figure extraction progress and timeout reporting
- page-window conversion and sidecar merge contract
- interrupted/partial report and conversion state journal
- MCP tool/API surface for windowed conversion
- schema/docs/tests for public output contracts

이 repo에서 담당하지 않을 범위:

- `ssd-verification-agent` DB/API/MCP implementation
- external RAG server upload/indexing
- visual LLM/VLM pixel interpretation
- raw image bytes, raw PDF text, or full Markdown body in MCP response
- automatic semantic correction of OCR or extracted text

## 4. Target Workflows

### 4.1 SpecAnalysisAgent Text-First NVMe Base Ingest

Recommended no-image conversion:

```bash
python3 -m pdf2md nvme-base.pdf -o output/nvme-base \
  --rag-profile technical_spec_rag \
  --domain-adapter nvme \
  --image-mode none
```

Expected MCP equivalent:

```text
pdf2md_convert_pdf(
  input_pdf="nvme-base.pdf",
  output_dir="output/nvme-base",
  rag_profile="technical_spec_rag",
  domain_adapter="nvme",
  image_mode="none"
)
```

### 4.2 Visual Evidence Required

When diagram/register/waveform evidence is required, keep `technical_spec_rag_visual`.
Do not use `image_mode=none` for that path because figure sidecars require image/figure provenance.

### 4.3 Large Full-PDF MCP Run

Recommended page-window workflow:

```text
pdf2md_convert_pdf_windowed(
  input_pdf="nvme-base.pdf",
  output_dir="output/nvme-base-windowed",
  rag_profile="technical_spec_rag",
  domain_adapter="nvme",
  image_mode="none",
  window_size=100
)
```

The workflow converts `1-100`, `101-200`, etc., validates each window, then merges the sidecars into one output directory.

## 5. P0 Implementation Plan

### P0-1. True No-Image Mode

Add an explicit `ImageMode.NONE = "none"` or equivalent public option.

Required behavior:

- Skip `pdf_context.get_image_boxes(page)`.
- Skip `extract_images(...)`.
- Skip figure crop fallback.
- Skip `figures_rag.jsonl`, generated figure description, figure structure, and figure region OCR.
- Preserve normal text/table/domain sidecars.
- Keep figure captions as ordinary text when they are present in the PDF text layer.
- Write manifest/report options showing `image_mode="none"`.
- Write report summary fields:
  - `image_extraction_skipped=true`
  - `image_extraction_skip_reason="image_mode_none"`
  - `figure_sidecars_skipped=true`

Compatibility policy:

- Do not change `ImageMode.PLACEHOLDER`.
- `placeholder` continues to support assetless RAG figure provenance.
- If `technical_spec_rag_visual` is combined with `image_mode=none`, no-image mode wins and a structured warning records that visual sidecars were skipped.

### P0-2. Image/Figure Extraction Timeout and Page Progress

Add page-level progress and timeout fallback to image/figure stages.

Required behavior:

- Emit progress events for:
  - `image_extraction_page_started`
  - `image_extraction_page_finished`
  - `image_extraction_page_skipped`
  - `image_extraction_stage_timeout`
- Include page number, image count, elapsed ms, and timeout reason when available.
- Add config/CLI/MCP options:
  - `image_extraction_page_timeout_seconds`
  - `image_extraction_stage_timeout_seconds`
  - `figure_semantics_stage_timeout_seconds`
- On timeout, skip the affected page/stage and continue where possible.
- Record warning codes:
  - `image_extraction_page_timeout`
  - `image_extraction_stage_timeout`
  - `figure_semantics_stage_timeout`
- Do not mark successfully extracted text/table data as failed because image extraction timed out.

### P0-3. Page-Window Batch Conversion and Merge Contract

Add an official page-window workflow for MCP and CLI/script use.

Required behavior:

- Split selected pages into deterministic windows, for example `1-100`, `101-200`.
- Write each window under a stable subdirectory:
  - `windows/pages-0001-0100/`
  - `windows/pages-0101-0200/`
- Validate each window output with existing artifact/index/provenance validators where applicable.
- Merge public sidecars into a final output directory:
  - `document.md`
  - `manifest.json`
  - `report.json`
  - RAG/domain sidecars
  - `page_window_merge_report.json`

Merge contract:

- Preserve original `source_sha256`.
- Preserve original page numbers.
- Rebuild sequential `chunk_index`.
- Avoid `chunk_id`, `requirement_id`, `stable_requirement_seed`, `technical_table_id`, and `domain_unit_id` collisions.
- Add `source_window_id` and `source_window_page_range` metadata when useful.
- Sort merged records by page, bbox/top, source record order, then original record id.
- Do not store raw full text in merge reports.

Recommended MCP tools:

- `pdf2md_plan_page_windows`
- `pdf2md_convert_page_window`
- `pdf2md_merge_window_outputs`
- `pdf2md_convert_pdf_windowed`

The one-shot `pdf2md_convert_pdf_windowed` may orchestrate the first three tools for simple clients.

### P0-4. Interrupted/Partial Report

Add a conversion state journal and best-effort report writer.

Required behavior:

- Maintain `conversion_state.json` during conversion.
- Track:
  - current stage
  - current page
  - completed pages
  - failed/skipped pages
  - artifacts written
  - elapsed ms by stage
  - last warning code
- On `KeyboardInterrupt`, timeout, or fatal exception after partial artifacts exist, write `interrupted_report.json`.
- If final `report.json` can be safely written, include:
  - `interrupted=true`
  - `interrupted_stage`
  - `interrupted_page`
  - `last_completed_page`
  - `artifacts_written`
  - `resume_hint`
- Exit with a non-zero code for interrupted/fatal states.
- Do not delete successful partial artifacts automatically.

## 6. Output Schema Updates

Update `docs/OUTPUT_SCHEMA.md` and generated schema files for:

- `image_mode="none"`
- `image_extraction_skipped`
- `figure_sidecars_skipped`
- image/figure timeout warning details
- page-window merge report
- interrupted conversion report fields

`page_window_merge_report.json` should include:

- `schema_version`
- `purpose="page_window_merge"`
- `source_pdf_sha256`
- `window_count`
- `windows[]`
- `merged_record_counts`
- `id_collision_count`
- `rewritten_id_count`
- `validation_summary`
- `warnings`

## 7. Test Plan

Required tests:

```bash
.venv311/bin/python -m pytest tests/test_images.py tests/test_pipeline_reporting.py -q
.venv311/bin/python -m pytest tests/test_mcp_server.py tests/test_rag_chunks.py -q
.venv311/bin/python -m pytest tests/test_provenance_integrity_validator.py tests/test_artifact_integrity_validator.py -q
.venv311/bin/python -m pytest tests/test_docs_examples.py tests/test_output_schema_contract.py -q
git diff --check
```

Fixture requirements:

- Small PDF with embedded images where `image_mode=none` produces no image assets and no figure sidecar.
- Synthetic multi-window technical spec fixture with stable page ranges.
- Collision fixture where two windows start with the same local chunk id and merge rewrites them deterministically.
- Timeout fixture using a fake image extractor hook.
- Interrupted conversion fixture using an injected exception after partial artifacts.

## 8. Acceptance Criteria

Q117 is complete when:

- `image_mode=none` is accepted by CLI, GUI, MCP, config, manifest, and report.
- No-image mode skips image box detection, image extraction, figure OCR, figure description, and figure structure generation.
- Image/figure extraction progress identifies the active page and elapsed time.
- Timeout fallback leaves structured warnings and preserves text/table/domain sidecars.
- Page-window MCP workflow can convert and merge a synthetic NVMe-like fixture deterministically.
- Merged sidecars pass artifact, index, and provenance validators.
- Interrupted or partially failed conversion leaves a usable JSON report.
- Documentation clearly recommends no-image page-window mode for `ssd-verification-agent` SpecAnalysisAgent text-first ingest.
