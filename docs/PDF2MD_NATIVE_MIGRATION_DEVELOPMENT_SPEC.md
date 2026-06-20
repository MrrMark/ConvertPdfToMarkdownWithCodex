# PDF2MD Native Migration Development Spec

이 문서는 Docling을 runtime backend로 붙이지 않고, Docling에서 참고할 만한 설계 아이디어를 `pdf2md` 네이티브 기능으로 재구성한 개발 명세와 구현 이력이다.

## 배경

latest NVMe Base Spec 비교 결과, Docling은 범용 문서 변환, `DoclingDocument`, serialization, chunking, OCR/plugin extension 설계 측면에서 참고 가치가 있었다. 그러나 `pdf2md`가 요구하는 기술 스펙용 `manifest.json`, `report.json`, RAG sidecar, provenance validator, domain adapter 계약은 Docling 기본 산출물이 아니다.

따라서 운영 방향은 다음과 같이 확정한다.

- canonical conversion pipeline은 `pdf2md`로 유지한다.
- Docling은 필수 dependency로 추가하지 않는다.
- Docling Markdown/JSON을 canonical artifact로 채택하지 않는다.
- 참고할 설계는 `pdf2md` 내부 IR, layout, table, chunking, OCR, figure, domain adapter 구조로 네이티브 구현한다.

## 공통 원칙

- 텍스트 원문은 요약, 재서술, 교정 없이 보존한다.
- 복잡하거나 애매한 표는 HTML fallback을 우선한다.
- generated figure description은 원문과 분리하고 기본 비활성 상태를 유지한다.
- 새 public JSON/JSONL 산출물이 생기면 `docs/OUTPUT_SCHEMA.md`, `docs/schema/`, validator, golden tests를 함께 갱신한다.
- 기존 `document.md`, `manifest.json`, `report.json`, RAG sidecar contract를 breaking change 없이 유지한다.
- 대형 스펙은 page-window와 deterministic merge 경로에서도 같은 schema를 유지해야 한다.
- 모든 신규 기능은 local-only, deterministic 검증을 우선한다.

## 전체 실행 순서

1. Q118 - Native Document IR and Serializer Boundary
2. Q119 - Table Confidence v2
3. Q120 - Native Hybrid Chunking v2
4. Q121 - Layout Sidecar and Reading Order Diagnostics
5. Q122 - Region OCR Evidence v2
6. Q123 - OCR Backend Registry Expansion
7. Q124 - Figure Semantics v2
8. Q125 - Domain Adapter Registry Hardening

이 순서는 내부 IR과 table/chunk contract를 먼저 안정화한 뒤, layout/OCR/figure/domain 확장을 얹기 위한 것이다.

## Q118 - Native Document IR and Serializer Boundary

Status: Implemented in Q118.

### 목표

pipeline 내부에서 흩어져 있는 text, table, figure, page layout, source reference를 하나의 내부 문서 표현으로 수렴한다. 외부 산출물 schema는 유지하되, serializer와 RAG sidecar 생성기가 같은 source-of-truth 구조를 읽도록 만든다.

### 범위

- `pdf2md/document_ir.py` 또는 동등한 내부 module 추가
- `Pdf2MdDocument`, `Pdf2MdPage`, `TextBlock`, `TableBlockRef`, `FigureBlockRef`, `SourceRef`, `PageLayoutSummary` 후보 모델 정의
- 기존 `PageResult`, `TableAsset`, figure record, text block sidecar와 연결되는 adapter layer 추가
- Markdown serializer 입력 경로와 RAG serializer 입력 경로의 중복 축소
- source hash, page number, bbox, stable source id 생성 책임 정리

### 제외 범위

- public output schema 변경
- Docling JSON import
- Docling runtime dependency 추가
- table/figure extraction heuristic의 대규모 변경

### 산출물

- `pdf2md/document_ir.py` 내부 IR 모델과 mapper
- `pdf2md/pipeline.py`의 `rag_text_blocks` stage 직후 IR 생성
- Markdown serializer와 RAG/semantic/figure/chunk serializer 입력의 legacy record adapter
- 기존 public output schema 유지

### 검증

- `.venv311/bin/python -m pytest -q`
- `.venv311/bin/python -m pytest tests/test_document_ir.py tests/test_rag_text_blocks.py tests/test_markdown_serializer.py`
- `.venv311/bin/python -m pdf2md pdf/NVM-Express-Base-Specification-Revision-2.3-2025.08.01-Ratified.pdf -o output/q118_nvme_base_full_smoke --pages 1-3 --image-mode none --rag-sidecar-scope full --domain-adapter nvme`
- `.venv311/bin/python scripts/validate_index_contract.py --output-dir output/q118_nvme_base_full_smoke --fail-on-error`
- `.venv311/bin/python scripts/validate_provenance_integrity.py --output-dir output/q118_nvme_base_full_smoke --fail-on-error`
- `.venv311/bin/python scripts/validate_artifact_integrity.py --output-dir output/q118_nvme_base_full_smoke --fail-on-error`
- `git diff --check`

### 완료 조건

- 기본 변환 산출물의 파일명과 schema가 유지된다.
- artifact/index/provenance validator가 기존 golden corpus에서 통과한다.
- serializer와 RAG sidecar가 같은 IR source refs를 공유한다.

## Q119 - Table Confidence v2

Status: Implemented in Q119.

### 목표

기술 스펙 표를 더 안전하게 재처리하기 위해 table confidence, fallback reason, header/body/stub 구조, continued table linkage를 강화한다.

### 범위

- table candidate별 confidence field 정의
- cell matching, row density, header confidence, stub column, multi-row header, merged cell suspicion 점수화
- continued table linkage confidence와 linkage reason 기록
- caption/table bbox/source paragraph 연결 강화
- `technical_tables_rag.jsonl`에 field/row confidence와 source_ref consistency metric 추가 후보 검토
- report summary에 table confidence 분포와 actionable/advisory reason count 추가

### 제외 범위

- 복잡 표를 GFM으로 강제 변환
- 모델 기반 table result의 무검증 승격
- table Markdown 렌더링 미관 우선 최적화

### 산출물

- `table_confidence_v2`, `table_confidence_v2_bucket`, `table_confidence_v2_reasons`
- `manifest.json` table asset, `report.summary.table_quality[]`, `tables_rag.jsonl`, `technical_tables_rag.jsonl` confidence propagation
- `report.summary.table_confidence_v2_buckets`, `report.summary.table_confidence_v2_average`
- complex/continued/NVMe/OCP golden fixture 갱신
- `docs/OUTPUT_SCHEMA.md`와 `docs/schema/` 갱신

### 검증

- `.venv311/bin/python -m pytest tests/test_tables.py tests/test_rag_tables.py tests/test_rag_technical_tables.py tests/test_docs_examples.py tests/test_output_schema_contract.py -q`
- `.venv311/bin/python -m pytest tests/test_golden_corpus.py -q`
- latest NVMe Base table slice smoke
- artifact/index/provenance validator

### 완료 조건

- GFM 승격 기준은 더 보수적이거나 동일해야 한다.
- low-quality/fallback reason이 report에서 재현 가능하게 설명된다.
- technical table source refs가 validator를 통과한다.

## Q120 - Native Hybrid Chunking v2

Status: Implemented in Q120.

### 목표

Docling의 document-native/hybrid chunking 개념을 `pdf2md` RAG sidecar에 맞게 네이티브로 재구현한다. table, requirement, figure context가 chunk boundary에서 깨지지 않도록 한다.

### 범위

- section hierarchy 기반 chunk boundary
- table row/table unit atomic chunk 유지
- repeated header context를 table chunk에 포함
- section breadcrumb/contextual embedding text 개선
- sibling text chunk merge의 section-safe 조건 강화
- figure/table 주변 문맥 연결
- chunk relationship metadata의 previous/next/parent/section anchor consistency 강화

### 제외 범위

- 외부 vector DB, embedding service, LangChain/LlamaIndex output을 canonical으로 채택
- raw query/result text를 benchmark report에 저장
- generated summary를 원문 chunk text로 대체

### 산출물

- `retrieval_chunks_rag.jsonl` relationship metadata v2 optional fields
  - `relationship_metadata_version`
  - `chunk_group_index`, `chunk_group_count`
  - `section_chunk_index`, `section_chunk_count`
  - `parent_section_path`, `parent_section_anchor_chunk_id`
  - `relationship_reasons`
- table-like chunk `context_metadata`
  - repeated header/caption inheritance for table row chunks
  - table confidence, domain, command, requirement, and relationship hint metadata
- relationship and table context regression tests
- `docs/OUTPUT_SCHEMA.md`, active backlog, implemented spec archive 갱신

### 검증

- `.venv311/bin/python -m pytest tests/test_rag_chunks.py tests/test_rag_eval.py tests/test_index_contract_validator.py -q`
- `.venv311/bin/python -m pytest tests/test_docs_examples.py -q`
- `.venv311/bin/python -m pytest tests/test_golden_corpus.py -q`
- `.venv311/bin/python scripts/run_rag_eval.py --fixture tests/fixtures/rag_eval_queries.json --output-dir output/q120_rag_eval`
- latest NVMe Base chunk smoke 및 artifact/index/provenance validator

### 완료 조건

- table/requirement/figure source type별 retrieval chunk가 source refs를 잃지 않는다.
- 기존 RAG sidecar consumer가 backward compatible하게 읽을 수 있다.
- chunk eval metric이 기존 baseline을 악화하지 않는다.

## Q121 - Layout Sidecar and Reading Order Diagnostics

Status: Implemented in Q121.

### 목표

multi-column, page furniture, caption linkage, bbox normalization을 구조화해 기술 스펙의 reading order와 layout provenance를 강화한다.

### 범위

- page layout summary record 정의
- column detection 진단 고도화
- body/furniture/header/footer layer 분리 기록
- text/table/figure bbox normalization
- caption과 table/figure linkage record
- debug artifact에만 있던 ordered lines/table candidates 중 재처리 가치가 있는 count/summary를 sidecar 또는 report로 승격

### 제외 범위

- Docling layout 결과 병합
- OCR 또는 model layout 결과를 text source-of-truth로 대체
- raw full page text를 layout report에 저장

### 산출물

- `page_layout_rag.jsonl` technical spec profile sidecar
  - page-level `reading_order_strategy`, `column_count_estimate`, `multi_column_detected`
  - raw text 없는 `region_refs` for text/table/figure source ids, roles, bbox, order index
  - `caption_links` for table/figure caption source-to-target linkage
- `report.summary` optional layout metrics
  - `page_layout_record_count`, `page_layout_file_count`
  - `layout_region_ref_count`, `layout_caption_link_count`
  - `layout_multi_column_page_count`, `layout_header_footer_suppressed_page_count`
- index/artifact/provenance/MCP/batch sidecar registry updates
- NVMe/OCP technical golden page layout sidecars

### 검증

- `.venv311/bin/python -m pytest tests/test_rag_layout.py tests/test_index_contract_validator.py -q`
- `.venv311/bin/python -m pytest tests/test_cli.py tests/test_mcp_server.py tests/test_artifact_integrity_validator.py tests/test_provenance_integrity_validator.py tests/test_rag_tables.py -q`
- `.venv311/bin/python -m pytest tests/test_output_schema_contract.py tests/test_docs_examples.py tests/test_golden_corpus.py -q`
- latest NVMe front matter and table slice smoke with artifact/index/provenance validator

### 완료 조건

- layout sidecar가 raw full text 없이 source refs와 count/position metadata를 제공한다.
- reading order regression이 기존 golden baseline을 악화하지 않는다.

## Q122 - Region OCR Evidence v2

Status: Implemented in Q122.

### 목표

figure/table bbox crop OCR을 원문 대체가 아닌 evidence sidecar로 강화한다. 이미지 업로드가 어려운 RAG 환경에서 diagram label과 image-only table 후보 검색성을 높인다.

### 범위

- figure/table region crop OCR evidence model
- accepted/rejected reason taxonomy
- OCR confidence, language/backend, bbox, page source ref 기록
- `figure_text`, `ocr_evidence`, `generated_description` field 분리
- Markdown 본문과 기본 text blocks 오염 방지 test

### 제외 범위

- region OCR 결과를 본문 Markdown에 기본 삽입
- OCR 결과로 table/text extraction 결과 자동 대체
- remote OCR/VLM 호출

### 산출물

- `figure_ocr_evidence_rag.jsonl` 신규 sidecar
  - `evidence_id`, `target_type`, `target_id`, `bbox`, `ocr_backend`, `ocr_lang`
  - `status`, `accepted_reason`, `rejected_reason`, `confidence`, `ocr_text`
  - `report_only=true`, `text_replaced=false`, `markdown_inserted=false`
  - `source_refs[]` for figure/excluded_figure/table ids
- report summary counters
  - `figure_ocr_evidence_record_count`, `figure_ocr_evidence_file_count`
  - `region_ocr_evidence_figure_record_count`, `region_ocr_evidence_table_record_count`
  - `region_ocr_evidence_accepted_count`, `region_ocr_evidence_rejected_count`
  - `region_ocr_evidence_runtime_unavailable_count`, `region_ocr_evidence_not_attempted_count`
- index/artifact/provenance/MCP/batch sidecar registry updates

### 검증

- `.venv311/bin/python -m pytest tests/test_rag_figures.py tests/test_index_contract_validator.py -q`
- `.venv311/bin/python -m pytest tests/test_cli.py tests/test_mcp_server.py tests/test_output_schema_contract.py tests/test_docs_examples.py tests/test_artifact_integrity_validator.py tests/test_provenance_integrity_validator.py -q`
- no Markdown text pollution regression
- artifact/index/provenance validator

### 완료 조건

- OCR evidence는 source refs와 confidence를 포함한다.
- rejected evidence가 구조화된 reason으로 남는다.
- 본문 원문 추출 결과는 region OCR로 바뀌지 않는다.

## Q123 - OCR Backend Registry Expansion

Status: Implemented in Q123.

### 목표

현재 `tesseract` 중심 OCR backend contract를 유지하면서 optional backend를 `pdf2md` 네이티브 protocol로 확장한다.

### 범위

- `tesseract-cli`, `rapidocr`, `ocrmac` adapter 후보 구현
- backend별 availability probe와 conversion-time warning 통합
- confidence normalization policy 정의
- backend별 language option mapping 문서화
- CLI/GUI/MCP option contract 갱신

### 제외 범위

- optional backend를 기본값으로 변경
- backend 미설치를 fatal error로 처리
- OCR text를 자동 교정하거나 재서술
- Docling OCR adapter를 우선 구현

### 산출물

- OCR backend registry 확장
  - conversion backend: `tesseract`, `tesseract-cli`, `rapidocr`, `ocrmac`
  - default backend: `tesseract`
- backend별 structured warning/report fields
  - `ocr_backend_raw_confidence_unit`
  - `ocr_backend_normalized_confidence_unit`
  - `ocr_backend_higher_is_better`
  - `ocr_backend_supports_languages`
- optional backend adapter modules
  - `pdf2md/extractors/ocr_backends/tesseract_cli.py`
  - `pdf2md/extractors/ocr_backends/rapidocr.py`
  - `pdf2md/extractors/ocr_backends/ocrmac.py`
- CLI/MCP/config supported backend choices 갱신
- wheel contract에 OCR backend adapter files 포함

### 검증

- `.venv311/bin/python -m pytest tests/test_ocr.py tests/test_config_and_io.py tests/test_quality_gate_scripts.py -q`
- `.venv311/bin/python -m pytest tests/test_cli.py tests/test_mcp_server.py tests/test_docs_examples.py -q`
- `scripts/probe_ocr_backends.py`
- optional dependency 미설치 환경 test

### 완료 조건

- `tesseract` 기본 동작이 유지된다.
- optional backend 미설치 시 structured warning만 남고 기본 경로는 깨지지 않는다.
- backend confidence 의미가 report에 구분된다.

## Q124 - Figure Semantics v2

Status: Implemented in Q124.

### 목표

figure kind, observed text, generated description, structure evidence를 분리해 visual technical spec RAG 품질을 높인다.

### 범위

- figure kind classifier 강화
- register map, waveform, block diagram, flow diagram, table-like image category 후보
- observed text와 generated description 분리 강화
- hallucination risk/review flag
- figure structure record의 relationship/source ref 강화

### 제외 범위

- generated description 기본 활성화
- generated description을 `document.md` 본문에 삽입
- external VLM/API 호출 기본 연결

### 산출물

- `figure_structures_rag.jsonl` schema 확장 후보
- `figure_descriptions_rag.jsonl` review metadata
- visual RAG eval query 보강

### 검증

- `python -m pytest tests/test_rag_figures.py tests/test_rag_semantics.py tests/test_quality_gate_scripts.py`
- `scripts/visual_rag_eval.py`
- `scripts/evaluate_figure_descriptions.py`

### 완료 조건

- figure semantic records가 source refs와 confidence/review metadata를 포함한다.
- generated content와 observed content가 명확히 분리된다.
- visual eval metric이 기존 baseline을 악화하지 않는다.

## Q125 - Domain Adapter Registry Hardening

Status: Implemented in Q125.

### 목표

NVMe/OCP/PCIe/TCG/SPDM/Caliptra/manual domain adapter를 registry/protocol 구조로 정리해 cross-spec 재처리와 고객별 adapter 확장을 안정화한다.

### 범위

- domain adapter protocol 정의
- adapter metadata: spec type, revision hints, keyword profile, unit taxonomy, evaluator hooks
- NVMe command/status/field taxonomy와 OCP requirement taxonomy 경계 명확화
- manual/customer requirement adapter 확장 point 정리
- cross-spec source id/stable id compatibility check

### 제외 범위

- 외부 plugin package loading을 기본 활성화
- customer-specific private schema를 core에 고정
- downstream SSD verification agent 구현

### 산출물

- `DomainAdapterSpec` 기반 domain adapter registry
- `domain_units_rag.jsonl.adapter_metadata`
- `domain_units_rag.jsonl.cross_spec_compatibility`
- adapter-specific unit tests
- SSD-RAG contract validator의 registry metadata check

### 검증

- `python -m pytest tests/test_rag_domain_adapters.py tests/test_ssd_rag_contract.py tests/test_requirement_change_impact.py`
- latest NVMe Base/Command benchmark
- OCP Datacenter NVMe SSD benchmark
- SSD/RAG contract validator

### 완료 조건

- 기존 domain adapter output이 backward compatible하다.
- adapter별 taxonomy와 source refs가 validator를 통과한다.
- cross-spec stable id/revision metadata가 deterministic하게 생성된다.

### 구현 결과

- NVMe/OCP/PCIe/TCG/SPDM/Caliptra/customer-requirements/manual adapter가 registry metadata를 공유한다.
- registry는 adapter별 SSD agent spec type, revision hints, keyword profile, unit taxonomy, evaluator hooks, required normalized fields를 제공한다.
- manual adapter는 고객 전용 private schema를 core에 고정하지 않고 `HIL/CustomerRequirement`로 매핑한다.
- `adapter_metadata`가 없는 legacy domain unit record는 validator에서 warning으로 처리해 backward compatibility를 유지한다.

## 공통 Release Gate

각 Q 작업은 최소 다음 검증 중 관련 범위를 실행한다.

```bash
python -m pytest
python -m pytest tests/test_golden_corpus.py
python -m pytest tests/test_output_schema_contract.py
python scripts/run_release_gates.py --help
git diff --check
```

대형 스펙 변경이 있는 경우:

```bash
python scripts/run_latest_nvme_base_benchmark.py \
  --input-pdf pdf/NVM-Express-Base-Specification-Revision-2.3-2025.08.01-Ratified.pdf \
  --output-dir output/latest_nvme_base_current_full \
  --spec-document base \
  --mode fast_smoke
```

## 성공 기준

- `pdf2md` 단일 실행으로 기술 스펙 변환, RAG sidecar 생성, provenance 검증이 가능하다.
- Docling 없이도 layout/table/chunk/OCR/figure/domain 품질 개선이 진행된다.
- 기존 CLI/GUI/MCP 사용자는 breaking change 없이 같은 산출물 계약을 사용할 수 있다.
- 새 기능은 모두 report/manifest/schema/test에 반영된다.
