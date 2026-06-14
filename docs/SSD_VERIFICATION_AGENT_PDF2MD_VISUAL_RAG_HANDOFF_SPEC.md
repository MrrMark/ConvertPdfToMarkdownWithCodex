# SSD Verification Agent PDF2MD Visual RAG Handoff Spec

## 1. Purpose

이 문서는 `ssd-verification-agent` repo에서 pdf2md 산출물을 사용해 NVMe Base Specification,
NVM Command Set Specification, OCP Datacenter NVMe SSD Specification을 분석할 때 필요한 개발 계획과
handoff 계약을 정리한다.

핵심 목표는 `ssd-verification-agent`가 PDF 변환 로직을 재구현하지 않고, pdf2md가 만든 local sidecar bundle을
source of truth로 저장한 뒤 RAG server 검색 결과와 결합해 `SpecAnalysisAgent` 품질을 높이는 것이다.

## 2. Ownership Boundary

### ConvertPdfToMarkdown 책임

- PDF -> Markdown/sidecar/report 변환
- NVMe/OCP domain adapter metadata 생성
- figure/OCR/visual sidecar 생성
- output schema와 local validator 제공
- benchmark report/scorecard 생성

### ssd-verification-agent 책임

- pdf2md sidecar bundle 등록/저장/ingest
- local DB evidence와 RAG server result reconciliation
- `SpecAnalysisAgent` candidate scoring과 citation quality 평가
- API/MCP/workflow orchestration
- 운영 report/dashboard/export

금지:

- `ssd-verification-agent`에서 PDF parsing/conversion logic을 재구현하지 않는다.
- pdf2md가 `ssd-verification-agent` DB schema나 workflow policy를 직접 알게 만들지 않는다.
- RAG server result만 source of truth로 사용하지 않는다.

## 3. Current Agent Baseline

확인된 `ssd-verification-agent` 구조:

- `Pdf2mdSidecarIngestService`가 다음 sidecar를 direct ingest한다.
  - `retrieval_chunks_rag.jsonl`
  - `requirements_rag.jsonl`
  - `requirement_traceability_rag.jsonl`
  - `technical_tables_rag.jsonl`
  - `domain_units_rag.jsonl`
- `SpecAnalysisAgent`는 citation/source metadata, stable seed, technical table id, command metadata를 점수화한다.
- OCP normalized fields promotion이 존재한다.
- MCP에는 `analyze_spec_requirements`, `extract_requirements`, workflow tools가 있지만
  pdf2md sidecar direct ingest tool은 아직 없다.
- Upload-analysis API는 PDF를 RAG service로 upload한 뒤 분석하는 경로이며, pdf2md sidecar source-of-truth 경로와는 다르다.
- Figure sidecars are not first-class ingest candidates yet.

## 4. Target Architecture

권장 운영 구조:

```text
pdf2md conversion
  -> local sidecar bundle
  -> ssd-verification-agent direct sidecar ingest
  -> local evidence DB as source of truth
  -> retrieval_chunks_rag.jsonl optionally indexed to RAG server
  -> RAG query results reconciled with local evidence
  -> SpecAnalysisAgent uses local evidence-backed candidates first
```

RAG server 역할:

- semantic search
- top-k 후보 검색
- user query exploration

Local sidecar 역할:

- authoritative citation
- source hash/page/bbox/table row/requirement id 보존
- deterministic replay
- audit/report/review evidence

## 5. Required API and MCP Additions

### P0. Sidecar Direct Ingest API

Add endpoint candidate:

```text
POST /api/rag-documents/{rag_document_ref_id}/pdf2md-sidecars/ingest
```

Request fields:

- `sidecar_dir: str`
- `include_domain_unit_candidates: bool = false`
- `include_figure_candidates: bool = false`
- `validate_before_ingest: bool = true`
- `confidential_safe: bool = false`

Response fields:

- `rag_document_ref_id`
- `sidecar_dir_label`
- `sidecar_record_counts`
- `accepted_requirement_count`
- `accepted_figure_evidence_count`
- `accepted_visual_chunk_count`
- `skipped_candidate_count`
- `duplicate_requirement_count`
- `missing_provenance_count`
- `linked_retrieval_chunk_count`
- `validation_summary`
- `analysis_run_id`

Policy:

- Accept only existing local directories allowed by deployment policy.
- Do not return raw spec text, full Markdown, table contents, image bytes, or local PDF path.
- Store sidecar label/path according to existing security policy.

### P0. MCP Tool

Add MCP tool candidate:

```text
ingest_pdf2md_sidecars(
  rag_document_ref_id: str,
  sidecar_dir: str,
  include_domain_unit_candidates: bool = false,
  include_figure_candidates: bool = false,
  validate_before_ingest: bool = true,
  compact: bool = true
)
```

MCP response should be compact by default and include counts/status only.

### P1. Workflow Tool

Add combined workflow candidate:

```text
run_pdf2md_sidecar_spec_analysis(
  rag_document: dict,
  sidecar_dir: str,
  analysis_limit: int = 20,
  include_figure_candidates: bool = true,
  compact: bool = true
)
```

Expected steps:

1. Register `RagDocumentRef`.
2. Validate sidecar bundle shape.
3. Direct ingest sidecars.
4. Run `SpecAnalysisAgent`.
5. Persist analysis run summary.
6. Return candidate counts and warning summary.

## 6. Sidecar Ingest Enhancements

### 6.1 Figure Sidecars

Add supported sidecars:

- `figures_rag.jsonl`
- `figure_descriptions_rag.jsonl`
- `figure_structures_rag.jsonl`

Recommended behavior:

- Do not create `Requirement` rows from every raw `figures_rag.jsonl` record by default.
- Create evidence records or visual candidate rows for:
  - `retrieval_chunks_rag.jsonl` records with `chunk_type=figure_text`
  - `chunk_type=figure_description`
  - `chunk_type=figure_structure`
- Preserve `generated_text`, `generation_strategy`, `figure_kind`, `detected_labels`, `figure_region_ocr`, `source_refs`.
- Treat visual candidates as lower priority than normative requirements unless linked to explicit requirement/table metadata.

### 6.2 Metadata Preservation

Preserve these metadata keys when present:

- `chunk_type`
- `figure_id`
- `figure_kind`
- `diagram_candidate`
- `detected_labels`
- `generated_text`
- `generation_strategy`
- `figure_region_ocr`
- `source_refs`
- `page_range`
- `bbox`
- `heading_path`
- `source_sha256`
- `stable_source_id`
- `source_dedupe_key`

Do not store:

- image bytes
- full Markdown body
- raw uploaded PDF path in public summaries
- generated prompts or raw query text in report summaries

### 6.3 Provenance Requirements

Minimum accepted visual evidence:

- `source_refs` exists
- `page_range` exists
- `source_sha256` exists
- `chunk_id` or stable source identifier exists

If a visual chunk lacks minimum provenance, skip it and increment `missing_provenance_count`.

## 7. SpecAnalysisAgent Enhancements

### P1. Candidate Source Quality

Extend source quality scoring with visual checks:

- `has_figure_id`
- `has_visual_source_ref`
- `has_bbox`
- `has_generated_text_flag_when_generated`
- `has_figure_kind`
- `has_detected_labels`

### P1. Candidate Kind

New candidate kind candidates:

- `visual_evidence`
- `figure_text`
- `figure_description`
- `figure_structure`

Ranking policy:

- Normative requirement candidates remain highest priority.
- Technical table candidates remain high priority for command/log/feature/status analysis.
- Visual evidence is used as supporting evidence unless it carries explicit command/log/register/status metadata.
- Generated visual descriptions should carry review-only or supporting-evidence status unless backed by nearby text/caption.

### P1. NVMe/OCP Visual Categories

Visual evidence may contribute to:

- `state_machine`
- `sequence_diagram`
- `timing`
- `register_layout`
- `architecture`
- `telemetry`
- `security`

For NVMe Command Set, visual evidence can support:

- command flow diagrams
- queue/doorbell diagrams
- register bitfield figures
- state transition diagrams

For OCP, visual evidence can support:

- form factor diagrams
- thermal/airflow diagrams
- device profile illustrations
- label/compliance figures

## 8. RAG Server Reconciliation

When RAG server results are available:

1. Use RAG server top-k for semantic candidate discovery.
2. Resolve returned `chunk_id`, `source_dedupe_key`, `stable_source_id`, or `source_refs` against local sidecar records.
3. If local evidence exists, prefer local citation/page/bbox/source metadata in final agent output.
4. If RAG metadata is missing or flattened, repair from local sidecar where identifiers match.
5. If no local match exists, mark candidate as `needs_review` and include a warning.

Recommended warning codes:

- `rag_result_missing_local_evidence`
- `rag_result_metadata_flattened`
- `visual_evidence_missing_provenance`
- `generated_visual_evidence_review_required`

## 9. Validation Plan

### Unit Tests

Add or extend:

- `tests/test_pdf2md_sidecar_ingest_service.py`
- `tests/test_spec_analysis_agent.py`
- `tests/test_rag_replay_end_to_end.py`
- `tests/test_mcp_server.py`
- `tests/test_spec_quality_fixtures.py`

Required cases:

- Ingest visual chunks without creating false normative requirements.
- Preserve figure metadata in evidence source metadata.
- Skip visual chunks with missing provenance.
- Reconcile RAG query result with local sidecar metadata.
- MCP tool returns counts only in compact mode.
- SpecAnalysisAgent ranks normative candidates above visual supporting evidence.

### Replay Fixtures

Add sanitized fixtures:

```text
tests/fixtures/sanitized_rag_replay/sidecar_direct/nvme_visual/
  retrieval_chunks_rag.jsonl
  figures_rag.jsonl
  figure_descriptions_rag.jsonl
  figure_structures_rag.jsonl

tests/fixtures/sanitized_rag_replay/sidecar_direct/ocp_visual/
  retrieval_chunks_rag.jsonl
  figures_rag.jsonl
  figure_descriptions_rag.jsonl
  figure_structures_rag.jsonl
```

Fixture policy:

- No raw official spec body.
- No image bytes.
- No local customer paths.
- Use small sanitized labels and metadata-only assertions.

### End-to-End Gates

Recommended gates:

- sidecar direct ingest gate
- multi-spec replay metric gate
- figure sidecar diagnostic gate
- SpecAnalysisAgent visual candidate ranking gate
- MCP compact response redaction gate

## 10. Implementation Sequence

Recommended PR order in `ssd-verification-agent`:

1. P0 API/MCP direct ingest exposure for existing sidecars.
2. P0 validation and compact response contract.
3. P1 figure sidecar/chunk ingest support.
4. P1 SpecAnalysisAgent visual source quality scoring.
5. P1 local sidecar and RAG server reconciliation.
6. P2 multi-spec visual replay metrics/dashboard.

Do not start with RAG server-only upload-analysis changes. The local sidecar source-of-truth path should come first.

## 11. Acceptance Criteria

The `ssd-verification-agent` work is complete when:

- pdf2md sidecar bundle can be registered/ingested through API and MCP.
- NVMe Base/Command and OCP sidecar direct ingest preserves citation, source hash, page, section, table, requirement, and visual metadata.
- `SpecAnalysisAgent` can summarize candidates from local sidecar evidence without relying on RAG upload-only flow.
- Figure/visual chunks are available as supporting evidence without polluting normative requirement candidates.
- Compact MCP/API responses do not expose raw spec text, table contents, image bytes, or local PDF paths.
- RAG server results can be reconciled with local evidence when identifiers match.
