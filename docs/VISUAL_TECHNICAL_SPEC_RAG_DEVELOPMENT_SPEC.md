# Visual Technical Spec RAG Development Spec

## 1. Purpose

이 문서는 NVMe Base Specification, NVM Command Set Specification, OCP Datacenter NVMe SSD Specification처럼
본문/표뿐 아니라 figure, diagram, waveform, state machine, register layout 이미지가 분석 품질에 영향을 줄 수 있는
technical specification을 `ssd-verification-agent`에서 더 안정적으로 사용하기 위한 pdf2md 쪽 개발 명세다.

현재 `technical_spec_rag + domain_adapter=nvme|ocp` 경로는 본문, 표, requirement, command/log/feature/status metadata에
대해서는 agent-ready 수준이다. 다만 이미지 내부 OCR과 도식 의미 검색은 기본 preset에서 보수적으로 opt-in 처리되어
있으므로, 운영자가 매번 옵션을 조합하지 않아도 되는 표준 visual profile과 회귀 gate가 필요하다.

## 2. Scope

이 repo에서 담당할 범위:

- PDF 변환 옵션/preset 정의
- figure/OCR/visual sidecar 생성 계약
- retrieval chunk에 figure evidence를 안전하게 포함
- official NVMe/OCP benchmark summary에 visual quality metric 추가
- JSON schema/docs/tests/golden fixture 갱신
- MCP/GUI/agent skill에서 같은 option bundle을 선택할 수 있게 노출

이 repo에서 담당하지 않을 범위:

- `ssd-verification-agent` DB schema/API/MCP 구현
- 외부 RAG server upload/index implementation
- 외부 VLM/LLM 호출
- raw image bytes 또는 raw spec 전문을 agent 응답에 포함
- OCR 결과를 원문 text로 교정하거나 대체하는 공격적 후처리

## 3. Current Baseline

현재 확인된 상태:

- OCP Datacenter NVMe SSD v2.7 official full conversion:
  - `page_count=253`
  - `conversion_status=success`
  - `contract_validation_passed=true`
  - `ocp_eval_hit_at_k=1.0`
  - `ocp_eval_expected_source_coverage=1.0`
  - `ocp_eval_table_field_coverage=1.0`
  - `figure_rag_record_count=31`
  - `ocr_actionable_warning_count=0`
  - `ocr_advisory_warning_count=0`
- NVMe Command Set historical local artifact:
  - page OCR was not used for born-digital text layer pages
  - `figure_rag_record_count=58`
  - structure marker OCR/recovery exists for tiny section-marker images

판단:

- Born-digital NVMe/OCP spec의 본문/표 분석에는 OCR이 핵심 병목이 아니다.
- Figure sidecar는 생성되지만, visual semantics options는 기본 profile에서 켜지지 않는다.
- `ssd-verification-agent`가 image/figure evidence까지 분석하려면 `retrieval_chunks_rag.jsonl`에
  `figure_text`, `figure_description`, `figure_structure` chunk가 안정적으로 포함되어야 한다.

## 4. Target Profiles

### 4.1 `technical_spec_rag`

기존 profile은 유지한다. 목적은 본문/표/requirement/technical table 중심의 기본 운영 경로다.

Expected options:

- `rag_table_output=both`
- `keep_page_markers=true`
- `remove_header_footer=true`
- `repair_hyphenation=true`
- `retrieval_tokenizer=regex`
- `rag_contextual_embedding_text=true`
- `rag_merge_sibling_text_chunks=true`
- `rag_chunk_relationship_metadata=true`
- visual semantics options default off

### 4.2 `technical_spec_rag_visual`

새 profile 후보다. 목적은 이미지/도식 검색성과 local sidecar evidence를 함께 강화하는 것이다.

Default options:

- all `technical_spec_rag` options
- `image_mode=referenced`
- `rag_figure_text_chunks=true`
- `figure_region_ocr=true`
- `rag_generated_figure_descriptions=true`
- `figure_structure_extraction=true`
- `figure_description_backend=local-vlm`

정책:

- local artifact storage가 가능한 운영에서는 `image_mode=referenced`를 기본으로 둔다.
- RAG server가 image asset을 받을 수 없는 경우에는 `image_mode=placeholder` override 또는
  GUI의 assetless preset을 사용한다.
- generated figure description은 deterministic context summary만 허용한다.
- visual pixels interpreted flag는 실제 VLM이 붙기 전까지 `false`여야 한다.
- OCR/region OCR text는 source evidence로만 사용하고 Markdown 원문을 대체하지 않는다.

### 4.3 Assetless Visual Operation

이미지 asset 업로드가 불가능한 RAG 환경에서는 다음 조합을 표준으로 사용한다.

```bash
python3 -m pdf2md spec.pdf -o output/spec \
  --rag-profile technical_spec_rag_visual \
  --domain-adapter nvme \
  --image-mode placeholder
```

profile 추가 전까지의 equivalent command:

```bash
python3 -m pdf2md spec.pdf -o output/spec \
  --rag-profile technical_spec_rag \
  --domain-adapter nvme \
  --image-mode placeholder \
  --rag-figure-text-chunks \
  --figure-region-ocr \
  --rag-generated-figure-descriptions \
  --figure-structure-extraction
```

## 5. Output Contract

### 5.1 Required Files

Visual profile output must include:

- `document.md`
- `manifest.json`
- `report.json`
- `retrieval_chunks_rag.jsonl`
- `figures_rag.jsonl`
- `figure_descriptions_rag.jsonl`
- `figure_structures_rag.jsonl`
- domain adapter sidecars:
  - `domain_units_rag.jsonl`
  - `requirement_traceability_rag.jsonl`
  - `technical_tables_rag.jsonl`

### 5.2 Retrieval Chunk Types

`retrieval_chunks_rag.jsonl` must preserve these chunk types:

- `figure_text`
- `figure_description`
- `figure_structure`

Required fields:

- `chunk_id`
- `chunk_type`
- `text`
- `source_refs`
- `page_range`
- `bbox`
- `heading_path`
- `semantic_types`
- `retrieval_priority`
- `source_sha256`
- `schema_version`

For generated descriptions:

- `generated_text=true`
- `generation_strategy=deterministic_context_summary`
- `source_refs` must include both figure and generated description provenance when available
- raw image bytes must not be embedded

### 5.3 Figure Sidecar Fields

`figures_rag.jsonl` records should preserve:

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
- `sha256`
- `ocr_candidates`
- `figure_kind`
- `diagram_candidate`
- `detected_labels`
- `nearby_text_refs`
- `source_refs`
- `classification_confidence`
- `classification_reasons`
- optional `figure_region_ocr`

`figure_region_ocr.region_ocr.report_only` must remain `true`.
`figure_region_ocr.region_ocr.text_replaced` must remain `false`.

## 6. Implementation Plan

### P0. Visual Profile and Option Wiring

Tasks:

1. Add `technical_spec_rag_visual` to `SUPPORTED_RAG_PURPOSE_PROFILES`.
2. Add a `RagProfileOptions` bundle with visual options enabled.
3. Expose the profile in CLI, MCP `pdf2md_list_profiles`, and agent-pack workflow docs.
4. Add GUI preset or map existing assetless preset to use the new visual bundle where appropriate.
5. Keep `technical_spec_rag` behavior backward compatible.

Acceptance:

- `python -m pdf2md --help` lists/accepts the profile.
- MCP `pdf2md_list_profiles` includes `technical_spec_rag_visual`.
- GUI preset lock/editability stays deterministic.
- Existing `technical_spec_rag` tests remain unchanged.

### P1. Visual Sidecar Contract and Validators

Tasks:

1. Extend output schema docs for figure sidecars and visual chunk types.
2. Strengthen `validate_index_contract.py` checks for `figure_text`, `figure_description`, `figure_structure`.
3. Strengthen `validate_provenance_integrity.py` source ref resolution for figure sidecars.
4. Add confidential-safe checks for generated figure description metadata.

Acceptance:

- Visual chunks resolve to `figures_rag.jsonl` source refs.
- Generated figure descriptions never include image bytes or local input paths.
- Validators report missing figure provenance as structured findings.

### P2. Official Benchmark Visual Metrics

Tasks:

1. Add visual metrics to latest NVMe Base/Command benchmark reports.
2. Add visual metrics to OCP benchmark report.
3. Keep reports metrics-only and raw-content-free.
4. Add scorecard rows for visual sidecar count and region OCR status.

Required summary fields:

- `figure_rag_record_count`
- `figure_text_chunk_record_count`
- `figure_description_record_count`
- `figure_description_chunk_record_count`
- `figure_structure_record_count`
- `figure_structure_chunk_record_count`
- `figure_region_ocr_attempted_count`
- `figure_region_ocr_promoted_label_count`
- `figure_region_ocr_runtime_unavailable_count`

Acceptance:

- Official benchmark wrappers can run with visual mode.
- Smoke mode remains fast and does not force expensive visual OCR unless requested.
- Full precision visual mode records metrics without query/result/raw text.

### P3. Visual Eval Gate

Tasks:

1. Add a small deterministic visual eval query set.
2. Cover figure label lookup, structure chunk retrieval, and page/source ref resolution.
3. Keep eval report aggregate-only.

Acceptance:

- `hit_at_k`, `expected_source_coverage`, and figure source ref coverage are reported.
- Generated query text and retrieved text are not stored in public benchmark reports.
- Failure can be promoted to non-zero exit with an opt-in flag.

## 7. Test Plan

Required tests:

```bash
.venv311/bin/python -m pytest tests/test_rag_figures.py tests/test_rag_chunks.py -q
.venv311/bin/python -m pytest tests/test_mcp_server.py tests/test_gui_presets.py -q
.venv311/bin/python -m pytest tests/test_output_schema_contract.py tests/test_docs_examples.py -q
.venv311/bin/python -m pytest tests/test_quality_gate_scripts.py -q
git diff --check
```

Recommended official local validation:

```bash
.venv311/bin/python scripts/run_latest_nvme_spec_benchmark.py \
  --input-pdf /tmp/NVMe-Base-latest.pdf \
  --output-dir /tmp/pdf2md-latest-nvme-base-visual \
  --spec-document base \
  --mode full_precision \
  --fail-on-contract-error

.venv311/bin/python scripts/run_latest_nvme_spec_benchmark.py \
  --input-pdf /tmp/NVM-Express-NVM-Command-Set-Specification-Revision-1.2-2025.08.01-Ratified.pdf \
  --output-dir /tmp/pdf2md-latest-nvme-command-set-visual \
  --spec-document nvm_command_set \
  --mode full_precision \
  --fail-on-contract-error \
  --fail-on-command-eval-error

.venv311/bin/python scripts/run_latest_ocp_datacenter_nvme_ssd_benchmark.py \
  --input-pdf /tmp/datacenter-nvme-ssd-specification-v2-7-final.pdf \
  --output-dir /tmp/pdf2md-latest-ocp-datacenter-nvme-ssd-visual \
  --mode full_precision \
  --fail-on-contract-error \
  --fail-on-ocp-eval-error
```

## 8. Done Definition

완료 조건:

- `technical_spec_rag_visual` 또는 동등한 공식 visual preset이 CLI/MCP/GUI/skill docs에 일관되게 노출된다.
- Visual sidecar와 visual retrieval chunk schema가 문서화된다.
- Validators가 figure source ref/provenance를 검증한다.
- Latest NVMe Base/Command/OCP benchmark가 visual metrics를 기록한다.
- `ssd-verification-agent` handoff 문서가 ingest/scoring 요구사항을 명확히 제공한다.
