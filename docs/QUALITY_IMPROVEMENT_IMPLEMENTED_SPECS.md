# Quality Improvement Implemented Specs

이 문서는 완료된 quality improvement Q 작업의 개발 명세와 구현 결과를 보관하는 archive다.

Active backlog는 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`, active 개발 명세는 `docs/QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md`에서 관리한다.
구현 완료, 테스트 통과, PR merge까지 끝난 명세만 이 문서로 옮긴다.

## Archive 범위

- Q34-Q42: 2026-05-14 기준 97/100 평가를 만든 RAG 운영/검증/병렬화 개선
- Q43: Q31-Q42 이후 scorecard refresh와 다음 backlog 축소
- Q46: RAG expected source coverage gate
- Q44: domain technical table typed coverage 확장
- Q47: local technical corpus evidence pack
- Q48-Q52: evidence pack analysis/trend, appendix fixture, captionless diagnostics, docs/schema contract
- Q53: minimal desktop GUI wrapper
- Q54: GUI runtime and install diagnostics
- Q55: GUI conversion result review UX

## 공통 원칙

- 외부 RAG/indexing 서비스 호출은 구현 범위에 포함하지 않는다.
- 모든 검증과 fixture 생성은 local-only, deterministic 동작을 기본으로 한다.
- PDF 원문 텍스트, 표, 이미지 provenance는 요약하거나 재서술하지 않는다.
- 새 public JSON 출력이 생기면 `docs/OUTPUT_SCHEMA.md`와 `docs/schema/` 계약을 함께 갱신한다.
- 실패는 가능한 한 구조화된 report로 남기고, 어느 파일/record/field/page가 문제인지 식별 가능해야 한다.
- 테스트는 작은 unit test, script smoke test, golden regression test를 우선한다.

## P1 / Q34. Offline Index Contract Validator

### 목표

`pdf2md`가 생성한 RAG sidecar를 OpenAI Vector Store/generic embedding pipeline, Azure AI Search, LangChain, LlamaIndex mapping recipe에 넣기 전에 local-only로 검증하는 validator를 추가한다.
검증은 외부 네트워크나 실제 indexer 호출 없이 수행하며, 실패 위치를 deterministic JSON report로 남긴다.

### 사용자 가치

- 운영자가 `retrieval_chunks_rag.jsonl`과 관련 sidecar를 업로드하기 전에 field 누락, 타입 불일치, metadata 과대, source provenance 손실을 빠르게 발견한다.
- confidential-safe 공유 모드에서 path, filename, source hash 같은 민감 metadata가 노출되는지 사전 점검한다.
- RAG adapter별 mapping recipe가 문서에만 머무르지 않고 CI에서 검증 가능한 계약이 된다.

### 입력

- 기본 입력: `--output-dir`로 지정한 단일 변환 산출물 디렉터리
- 필수 검증 대상: `retrieval_chunks_rag.jsonl`
- 선택 검증 대상:
  - `text_blocks_rag.jsonl`
  - `semantic_units_rag.jsonl`
  - `requirements_rag.jsonl`
  - `cross_refs_rag.jsonl`
  - `requirement_traceability_rag.jsonl`
  - `technical_tables_rag.jsonl`
  - `tables_rag.jsonl`
  - `figures_rag.jsonl`
  - `domain_units_rag.jsonl`
  - `manifest.json`
  - `report.json`

### CLI 설계

새 스크립트:

```bash
python scripts/validate_index_contract.py --output-dir output
python scripts/validate_index_contract.py --output-dir output --target openai
python scripts/validate_index_contract.py --output-dir output --target azure-ai-search
python scripts/validate_index_contract.py --output-dir output --target langchain
python scripts/validate_index_contract.py --output-dir output --target llamaindex
python scripts/validate_index_contract.py --output-dir output --target all --confidential-safe --fail-on-error
```

권장 옵션:

- `--output-dir`: 변환 산출물 디렉터리
- `--target`: `all`, `openai`, `azure-ai-search`, `langchain`, `llamaindex`
- `--report-file`: 기본값 `index_contract_report.json`
- `--confidential-safe`: confidential-safe 공유 가능 metadata만 허용하는 추가 검사
- `--metadata-max-bytes`: metadata payload 크기 제한. target별 기본값을 갖고 명시값으로 override 가능
- `--fail-on-warning`: warning이 있어도 exit code 1
- `--fail-on-error`: error가 있으면 exit code 1

### 검증 규칙

공통 record contract:

- JSONL 각 줄은 유효한 JSON object여야 한다.
- `retrieval_chunks_rag.jsonl` record는 `docs/OUTPUT_SCHEMA.md`의 required field를 포함해야 한다.
- `chunk_id`, `chunk_index`, `chunk_type`, `text`, `source_refs`, `page_range`, `source_dedupe_key` 타입을 엄격히 검증한다.
- `schema_version`과 `source_sha256`은 모든 retrieval chunk에 존재해야 한다.
- `source_refs`는 비어 있으면 error다.
- `source_refs[]`의 `source_type`, `source_id`, `page`는 citation lookup에 필요한 최소 field로 취급한다.
- `page_range`는 `[start, end]` 형태의 양의 정수 배열이어야 하며 `start <= end`여야 한다.
- `token_estimate`, `char_count`, `retrieval_priority`는 정수여야 한다.

Target별 mapping contract:

- OpenAI/generic:
  - `id`, `text`, `metadata`로 매핑 가능해야 한다.
  - metadata는 JSON 직렬화 가능해야 하고 target metadata size limit을 넘으면 warning 또는 error로 분류한다.
- Azure AI Search:
  - key field `id`는 문자열이고 비어 있으면 안 된다.
  - `page_start`, `page_end`, `retrieval_priority`, `token_estimate`는 정수형 index field로 변환 가능해야 한다.
  - `semantic_types`는 문자열 collection으로 변환 가능해야 한다.
  - `source_refs_json`은 deterministic JSON string으로 직렬화 가능해야 한다.
- LangChain:
  - `page_content=record["text"]`가 빈 문자열이면 error다.
  - metadata에 들어가는 값은 JSON-serializable scalar/list/dict여야 한다.
- LlamaIndex:
  - `TextNode(id_=chunk_id, text=text, metadata=...)`로 매핑 가능해야 한다.
  - metadata key는 문자열이어야 하고, nested object는 deterministic JSON-compatible이어야 한다.

Confidential-safe contract:

- public metadata allowlist를 둔다.
- 허용 기본 field: `chunk_id`, `chunk_type`, `page_range`, `section_path`, `semantic_types`, `retrieval_priority`, `token_estimate`, redacted `source_refs`
- raw `input_pdf` path, absolute asset path, local output path, 원본 filename, customer/product codename 후보는 warning 이상으로 보고한다.
- `source_sha256`는 공유 전 검토 대상으로 warning 처리한다.
- 원문 `text` 자동 익명화는 하지 않는다. 대신 report에 `text_redaction_not_performed` advisory를 남긴다.

### 출력 report

기본 파일: `index_contract_report.json`

필수 구조:

```json
{
  "schema_version": "1.0",
  "purpose": "rag_index_contract_validation",
  "status": "passed",
  "targets": ["openai", "azure-ai-search", "langchain", "llamaindex"],
  "summary": {
    "checked_files": 1,
    "checked_records": 10,
    "error_count": 0,
    "warning_count": 0
  },
  "files": [],
  "findings": []
}
```

Finding field:

- `severity`: `error`, `warning`, `info`
- `code`: deterministic snake_case code
- `target`: target 이름 또는 `common`
- `file`: 산출물 파일명
- `line`: JSONL line number, 파일 단위 finding이면 `null`
- `record_id`: `chunk_id` 또는 sidecar record id
- `field`: 문제 field path
- `message`: 사람이 읽는 설명

정렬 순서:

1. severity: error, warning, info
2. file name
3. line number
4. field
5. code

### 구현 위치

- `scripts/validate_index_contract.py`
- 필요 시 순수 로직 모듈: `pdf2md/utils/index_contract.py`
- target별 mapping helper는 스크립트 내부 함수로 시작하고, 중복이 커질 때만 모듈화한다.
- report 모델이 public schema로 승격되면 `pdf2md/models.py`, `docs/schema/`에 추가한다.

### 테스트

- `tests/test_index_contract_validator.py`
- 정상 `retrieval_chunks_rag.jsonl` fixture가 모든 target에서 passed 되는지 확인한다.
- required field 누락, 타입 오류, 빈 `source_refs`, 잘못된 `page_range`를 각각 error로 검증한다.
- metadata size 초과를 warning/error 정책에 맞게 검증한다.
- confidential-safe 모드에서 absolute path와 filename 노출을 탐지한다.
- JSONL line number와 finding 정렬이 deterministic인지 확인한다.
- script smoke:

```bash
python scripts/validate_index_contract.py --output-dir output --target all --fail-on-error
```

### 완료 조건

- validator가 외부 서비스 호출 없이 동작한다.
- 정상 golden corpus는 통과하고, 의도적으로 깨진 fixture는 안정적인 finding을 낸다.
- `docs/RAG_INDEXER_INTEGRATION_RECIPES.md`에 local validation 명령이 추가된다.
- release/rag gate에 optional로 연결할 수 있는 함수 또는 script command가 준비된다.

### 비범위

- OpenAI/Azure/LangChain/LlamaIndex SDK 의존성 추가
- 실제 embedding 생성 또는 index upload
- 원문 text anonymization

## P2 / Q35. Rendered Diagram Fixture Suite

### 목표

state machine, sequence diagram, register layout을 포함한 synthetic PDF fixture를 렌더링 기반으로 추가하고, `figures_rag.jsonl`의 diagram provenance와 diagnostics를 golden으로 고정한다.
OCR runtime 유무에 따라 기대 diagnostics를 분리해 CI가 환경 차이 때문에 흔들리지 않게 한다.

### 사용자 가치

- 다이어그램/그림 sidecar가 단순 이미지 추출을 넘어 bbox, caption, heading, label diagnostics를 안정적으로 유지하는지 회귀 방지한다.
- OCR이 없는 CI에서도 deterministic golden을 유지하고, OCR이 있는 로컬/확장 CI에서는 더 풍부한 label diagnostics를 검증한다.
- storage/security spec의 state/register/sequence diagram 분석용 RAG provenance 품질을 높인다.

### Fixture 범위

추가 synthetic PDF:

- state machine diagram
  - 상태 노드 3개 이상
  - 전이 화살표 2개 이상
  - transition label 예: `READY`, `ERROR`, `RESET`
  - Figure caption과 section heading 포함
- sequence diagram
  - lifeline 2개 이상
  - message arrow 2개 이상
  - message label 예: `Command`, `Completion`
  - Figure caption과 nearby text 포함
- register layout
  - bit range cell 예: `31:16`, `15:8`, `7:0`
  - field label 예: `RSVD`, `STATUS`, `ENABLE`
  - table이 아니라 figure/diagram 후보로도 잡힐 수 있는 렌더링 케이스 포함

권장 위치:

- 생성 helper: `tests/fixtures/pdf_builder.py` 확장 또는 `tests/fixtures/diagram_pdf_builder.py`
- golden output: `tests/golden/corpus/diagram_*`
- fixture source PDF는 repo policy에 따라 작고 deterministic한 synthetic 파일만 커밋한다.

### 기대 산출물

각 fixture 변환 시 최소 확인 대상:

- `document.md`
- `manifest.json`
- `report.json`
- `figures_rag.jsonl`
- 필요한 경우 `text_blocks_rag.jsonl`, `retrieval_chunks_rag.jsonl`

`figures_rag.jsonl` golden에서 고정할 field:

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
- `source_refs`
- `figure_kind`
- `diagram_candidate`
- `detected_labels`
- `diagram_label_diagnostics`
- `nearby_text_refs`
- `classification_confidence`
- `classification_reasons`

### OCR 분기 정책

기본 CI 경로:

- OCR runtime이 없어도 통과해야 한다.
- `ocr_candidates`는 비어 있거나 runtime unavailable diagnostic을 가진다.
- low-confidence 또는 unavailable OCR 결과는 promoted label로 고정하지 않는다.

OCR available 경로:

- 별도 test marker 또는 runtime preflight로 분기한다.
- OCR label 후보가 `diagram_label_diagnostics.ocr_candidates` 또는 동등 diagnostics에 남는지 확인한다.
- promoted `detected_labels`는 confidence threshold를 넘는 deterministic 후보만 허용한다.

권장 test 구성:

- OCR-independent golden test: 항상 실행
- OCR runtime dependent test: `pytest.importorskip` 또는 기존 OCR runtime check helper로 조건부 실행

### 구현 요구사항

- synthetic PDF는 폰트/좌표/도형을 고정해 플랫폼별 layout drift를 최소화한다.
- bbox 비교는 소수점 고정 또는 tolerance-normalization helper를 사용한다.
- asset filename은 기존 deterministic 규칙을 따른다.
- caption과 heading provenance는 source_refs로 추적 가능해야 한다.
- register layout이 table extractor와 충돌하는 경우에도 figure diagnostics가 보존되는지 확인한다.

### 테스트

- `tests/test_rag_figures.py`에 diagram fixture 단위 테스트 추가
- `tests/test_golden_corpus.py`에 diagram corpus golden 포함
- OCR 없는 환경에서 `figures_rag.jsonl` expected output 고정
- OCR 있는 환경에서 label candidate diagnostics 별도 assertion
- caption/heading/source_refs가 누락되면 실패

권장 smoke:

```bash
python -m pytest tests/test_rag_figures.py tests/test_golden_corpus.py
python -m pdf2md tests/fixtures/diagram_state_machine.pdf -o /tmp/pdf2md-diagram-smoke --figure-crop-fallback
```

### 완료 조건

- state machine, sequence diagram, register layout fixture가 추가된다.
- OCR 미설치 CI에서 golden이 안정적으로 통과한다.
- OCR 설치 환경에서 추가 diagnostics test가 통과한다.
- `figures_rag.jsonl`의 diagram/caption/heading/source provenance 회귀가 잡힌다.

### 비범위

- 다이어그램 의미 해석 완성
- VLM 기반 이미지 설명 생성
- Mermaid/PlantUML로의 변환

## P2 / Q36. Page-Level Parallel Extractor

### 목표

문서 단위 증분 캐시 이후 page extraction, read-order, table 후보 생성을 page worker 단위로 병렬화할 수 있는 executor를 추가한다.
기본값은 기존 single-worker 경로를 유지하고, `--page-workers`를 명시했을 때만 병렬 경로를 사용한다.
병렬 실행에서도 출력 순서, warning/report ordering, asset naming, JSONL record order는 기존 deterministic contract를 유지해야 한다.

### 사용자 가치

- 긴 기술 PDF 변환 시간을 줄인다.
- 병렬화를 opt-in으로 두어 기존 안정성을 유지한다.
- 운영자는 benchmark gate로 속도 향상과 결과 동일성을 함께 확인할 수 있다.

### CLI/API 설계

CLI 옵션:

```bash
python -m pdf2md spec.pdf -o output --page-workers 4
python -m pdf2md spec.pdf -o output --page-workers 1
```

Config 추가:

- `page_workers: int = 1`

Validation:

- `page_workers >= 1`
- 기본값 `1`
- `1`이면 기존 single-worker behavior와 동일해야 한다.
- 너무 큰 값은 page 수 또는 CPU 수 기준으로 내부 cap을 둘 수 있지만, cap 적용 시 report에 diagnostic을 남긴다.

Manifest/report 추가 후보:

- `manifest.options.page_workers`
- `report.summary.page_worker_count`
- `report.summary.page_parallel_enabled`
- `report.summary.page_worker_effective_count`

public schema에 추가하면 `docs/OUTPUT_SCHEMA.md`, schema export test를 함께 갱신한다.

### 병렬화 대상

1차 범위:

- page text extraction/read-order 후보 생성
- page table candidate extraction
- page-level structure normalization 준비 데이터

보수적 제외 대상:

- final Markdown serialization
- manifest/report write
- RAG sidecar write
- image asset file write와 asset naming
- OCR execution

이미지 추출은 파일명과 dedupe ordering이 민감하므로 Q36 1차 구현에서는 single path를 유지한다.

### 아키텍처

권장 구조:

- `pdf2md/extractors/page_worker.py`
  - `PageWorkerInput`
  - `PageWorkerResult`
  - `extract_page_worker(input) -> PageWorkerResult`
- `pdf2md/utils/page_executor.py`
  - `run_page_workers(inputs, worker_count) -> list[PageWorkerResult]`

Worker result는 page number를 포함하고, parent process에서 반드시 page number 순으로 merge한다.

`PageWorkerResult` 최소 field:

- `page`
- `text_lines`
- `raw_lines`
- `text_metadata`
- `page_text`
- `table_assets`
- `table_blocks`
- `rag_tables`
- `table_debug_candidates`
- `warnings`
- `failed`
- `duration_ms`

### 결정성 규칙

- merge는 항상 `selected_pages` 순서를 기준으로 한다.
- warning은 `(page, code, message)` 기준으로 정렬하거나 selected page merge 순서를 유지한다.
- table/image/figure asset index는 병렬 worker 내부 최종값을 그대로 믿지 말고 parent merge 단계에서 page-local deterministic index를 재확정한다.
- JSONL record는 기존 builder의 입력 순서를 page-sorted로 제공한다.
- stage duration은 전체 wall-clock duration과 worker duration aggregate를 구분한다.
- debug artifact 파일명은 기존 `page-0001-*` 규칙을 유지한다.

### 구현 단계

1. `Config`와 CLI에 `page_workers`를 추가하고, `1`일 때 기존 테스트가 그대로 통과하게 한다.
2. text extraction을 page worker로 호출할 수 있도록 순수 page 단위 함수 경계를 만든다.
3. table 후보 추출을 page 단위로 분리하되, 기존 `extract_tables` public behavior는 유지한다.
4. `--page-workers > 1`에서 executor를 사용하고 parent merge로 기존 자료구조를 복원한다.
5. 동일 입력에 대해 single-worker와 multi-worker output diff가 없는지 테스트한다.
6. benchmark script 또는 release gate에 opt-in 성능 검증을 연결한다.

### 테스트

- CLI parser test: `--page-workers` 기본값과 validation
- config/model test: `page_workers` serialization
- deterministic equivalence test:
  - 같은 fixture를 `--page-workers 1`과 `--page-workers 2`로 변환
  - volatile field를 normalize한 뒤 `document.md`, `manifest.json`, `report.json`, JSONL sidecar 비교
- partial failure ordering test:
  - 특정 page worker 실패를 모의하고 warning/report ordering이 안정적인지 확인
- benchmark smoke:

```bash
python scripts/benchmark_conversion.py --input tests/fixtures/multi_page.pdf --page-workers 1
python scripts/benchmark_conversion.py --input tests/fixtures/multi_page.pdf --page-workers 4
```

### 완료 조건

- 기본 `page_workers=1` 경로에서 기존 golden이 변하지 않는다.
- `--page-workers > 1`에서 결과 산출물 내용이 single-worker와 동일하다.
- report에 worker count와 parallel enabled 여부가 남는다.
- benchmark gate가 결과 동일성과 최소 성능 신호를 함께 확인한다.

### 비범위

- batch document-level 병렬화
- OCR 병렬화
- image extraction/file write 병렬화
- distributed execution

## P1 / Q37. Cross-Sidecar Provenance Integrity Validator

### 목표

Q34의 index mapping 검증을 통과한 산출물이라도 내부 sidecar provenance가 깨져 있으면 RAG citation과 test script 수정 범위 계산이 잘못될 수 있다.
Q37은 모든 RAG sidecar의 `source_refs`가 실제 원본 record로 해소되는지 local-only로 검증한다.

### 주요 검증

- `retrieval_chunks_rag.jsonl.source_refs[].source_id`가 대응 sidecar record id에 존재하는지 확인한다.
- `source_refs[].page`, chunk `page_range`, record `page`, `bbox`가 상호 모순되지 않는지 확인한다.
- `source_record_count`가 실제 `source_refs` 개수와 일치하는지 확인한다.
- `source_dedupe_key`가 source id 집합에서 deterministic하게 복원 가능한지 확인한다.
- manifest/report summary count와 실제 JSONL record count가 어긋나면 warning 또는 error로 분류한다.

### 구현 위치

- 새 스크립트: `scripts/validate_provenance_integrity.py`
- 필요 시 helper: `pdf2md/utils/provenance_integrity.py`
- 출력 report: `provenance_integrity_report.json`
- release gate optional: `--gates provenance-integrity`

### 테스트

- 정상 golden corpus가 통과하는 test
- 없는 `source_id`, 잘못된 page, bbox page mismatch, count mismatch fixture test
- finding 정렬과 line/record id 위치가 deterministic인지 확인

### 완료 조건

- 외부 서비스 호출 없이 단일 output directory를 검증한다.
- 오류가 어느 sidecar/file/line/source_ref에서 발생했는지 report로 추적 가능하다.
- release gate에서 opt-in으로 실행 가능하다.

## P1 / Q38. Layout Stress Golden Corpus

### 목표

기존 synthetic corpus는 핵심 경로를 잘 막지만, 실제 기술 문서에서 문제가 되는 multi-column, sidebar, floated figure, footnote, mixed-language layout 조합은 더 강한 회귀 방어가 필요하다.
Q38은 reading order와 heading/source provenance 품질을 golden corpus로 고정한다.

### Fixture 범위

- 2-column 본문 + 우측 sidebar note
- figure가 본문 중간에 떠 있고 caption이 다음 줄/이전 줄에 있는 page
- 하단 footnote가 많은 page
- section heading이 다음 column/page 본문에 carry-over되는 page
- Korean/English mixed paragraph와 list

### 검증 대상

- `document.md`의 원문 순서
- `text_blocks_rag.jsonl.block_type`, `heading_path`, `parent_heading_block_id`
- `semantic_units_rag.jsonl.source_refs`
- `retrieval_chunks_rag.jsonl.page_range`, `section_path`, `source_refs`
- `report.summary.structure_low_confidence_count`, `page_results[].reading_order_strategy`

### 테스트

- `tests/fixtures/pdf_builder.py` 또는 별도 builder에 layout stress PDF 생성 함수 추가
- `tests/golden/corpus/layout_*` golden 추가
- volatile field normalize 후 golden corpus test에 포함

### 완료 조건

- layout stress fixture가 기본 CI에서 안정적으로 통과한다.
- reading order가 바뀌면 `document.md` 또는 RAG sidecar golden diff로 바로 드러난다.

## P1 / Q39. Table Reconstruction Accuracy Pack

### 목표

표는 이 프로젝트의 두 번째 우선순위이며 RAG 운영에서는 table row, technical table unit, domain unit의 source of truth다.
Q39는 복잡 표를 억지로 GFM으로 내보내지 않는 정책과 row-level structured sidecar 정확도를 더 강하게 검증한다.

### Fixture 범위

- merged cell / multi-row header
- stub column + footnote row
- continued table with repeated header
- repeated template table false-positive 방지
- register bitfield layout: `31:16`, `15:8`, `7:0`
- command/opcode/log page/feature/security method 형태의 technical table

### 검증 대상

- 단순 표만 GFM 사용
- 복잡 표는 HTML fallback 유지
- `tables_rag.jsonl.headers`, `cells`, `row_text`, `bbox`, `fallback_reasons`
- `technical_tables_rag.jsonl.unit_type`, `bit_range`, `field_name`, `value`, `source_refs`
- `report.summary.table_fallback_reason_counts`, `table_low_quality_count`

### 테스트

- 기존 `tests/test_tables.py`, `tests/test_rag_tables.py`, `tests/test_rag_technical_tables.py` 확장
- golden corpus에 table accuracy pack 추가
- unsafe GFM coercion이 발생하면 실패하는 regression test 추가

### 완료 조건

- 잘못된 GFM 표 생성 가능성이 낮아진다.
- register/bitfield/technical table row provenance가 RAG sidecar에서 안정적으로 추적된다.

## P2 / Q40. OCR Confidence And Language Calibration Matrix

### 목표

OCR은 환경 의존성이 크므로, runtime 없음/있음과 언어 데이터 상태에 따른 기대 diagnostics를 명확히 분리해야 한다.
Q40은 OCR 결과를 임의 교정하지 않는 원문 보존 정책과 confidence warning/report 계약을 고정한다.

### Fixture 범위

- OCR runtime unavailable path
- low-confidence scanned text
- empty OCR result
- Korean+English mixed scanned page
- scanned simple table

### 검증 대상

- `warnings[].code`: `OCR_RUNTIME_UNAVAILABLE`, `OCR_CONFIDENCE_WARN`, `OCR_CONFIDENCE_CRITICAL`, `OCR_EMPTY_RESULT`
- `page_results[].ocr_attempted`, `ocr_runtime_available`, `ocr_confidence_mean`, `low_conf_token_ratio`
- OCR text가 spelling correction이나 paraphrase 없이 그대로 sidecar/Markdown에 들어가는지 확인

### 테스트

- OCR 없는 환경에서도 통과하는 deterministic test
- OCR runtime이 있는 경우에만 실행되는 conditional test
- language data missing report test

### 완료 조건

- OCR 환경 차이 때문에 CI가 흔들리지 않는다.
- 낮은 confidence 결과가 정답처럼 소비되지 않고 warning/report로 드러난다.

## P2 / Q41. Output Artifact Integrity Gate

### 목표

변환 자체가 성공해도 Markdown link, asset file, manifest/report count, sidecar file map이 어긋나면 downstream agent가 실패한다.
Q41은 산출물 파일 간 무결성을 local gate로 검증한다.

### 주요 검증

- `document.md`의 image relative link가 실제 asset file을 가리키는지 확인한다.
- manifest `images[]`, `tables[]`, report summary count, 실제 sidecar record count가 일치하는지 확인한다.
- batch/corpus manifest의 file map이 실제 파일과 일치하는지 확인한다.
- orphan asset, missing asset, stale path, sidecar count mismatch를 deterministic finding으로 출력한다.

### 구현 위치

- 새 스크립트: `scripts/validate_artifact_integrity.py`
- 출력 report: `artifact_integrity_report.json`
- release gate optional: `--gates artifact-integrity`

### 테스트

- 정상 single output과 batch/corpus output 통과 test
- missing image file, broken Markdown link, stale manifest path, sidecar count mismatch fixture test
- confidential-safe mode에서 absolute path가 섞이지 않는지 확인

### 완료 조건

- 변환 결과가 downstream에서 바로 소비 가능한 파일 세트인지 자동 점검할 수 있다.
- partial success와 실제 artifact 누락을 report에서 구분할 수 있다.

## P2 / Q42. Full Page Worker Table Candidate Parallelization

### 목표

Q36에서 도입한 `--page-workers` text/read-order 병렬 경로를 table candidate extraction까지 확장한다.
기본값 `page_workers=1`의 기존 deterministic 경로는 유지하고, `--page-workers > 1`에서만 page-local table 후보 생성을 worker로 분산한다.

### 구현 범위

- `extract_tables`의 public behavior는 유지한다.
- page-local table candidate collection은 worker에서 수행한다.
- continuation grouping, table asset index, warning/report ordering, RAG table record ordering은 parent merge에서 selected page 순서로 재확정한다.
- image extraction, OCR, manifest/report write는 계속 single path로 둔다.

### 검증 대상

- `document.md`, `manifest.json`, `report.json`, `tables_rag.jsonl`, `technical_tables_rag.jsonl`가 worker 수와 무관하게 동일해야 한다.
- continuation table, repeated template table, complex HTML fallback, simple GFM table fixture에서 결과 동일성을 확인한다.
- `report.summary.page_worker_effective_count`, `page_parallel_enabled`, `pdf_open_count`가 병렬 실행을 설명할 수 있어야 한다.

### 테스트

- single-worker와 multi-worker output diff test
- worker 내부 table candidate 실패 시 page-scoped warning ordering test
- benchmark smoke 또는 release gate optional check

### 완료 조건

- table candidate extraction까지 병렬화해도 기존 golden corpus가 변하지 않는다.
- multi-worker 경로의 결과 동일성과 최소 성능 신호가 CI 또는 release gate에서 검증된다.

### 구현 결과

- `--page-workers > 1` 경로에서 worker가 isolated PDF open 1회로 page-local text/read-order와 table raw candidate를 함께 수집한다.
- `extract_tables`는 precomputed page candidate를 받아 parent에서 selected page 순서로 pruning, fallback warning, table index, continuation, RAG table ordering을 재확정한다.
- image extraction, OCR, manifest/report write는 single parent path를 유지한다.
- benchmark smoke는 `scripts/benchmark_conversion.py --page-workers 1,2`처럼 worker count별 실행과 core artifact hash 동등성 신호를 기록한다.

## P1 / Q43. Quality Scorecard Refresh

### 목표

Q31-Q42 구현 후 현재 품질 상태를 97/100 기준으로 재평가하고, 다음 backlog를 Q46/Q44로 축소한다.

### 구현 범위

- `docs/QUALITY_SCORECARD.md`에 2026-05-14 평가 항목을 추가한다.
- `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에는 완료된 Q43을 남기지 않고 다음 실제 작업인 Q46, Q44만 유지한다.
- Q46/Q44는 기능 구현 전 개발 명세와 테스트 기준을 이 문서에 추가한다.

### 완료 조건

- scorecard가 현재 merge 상태와 남은 리스크를 설명한다.
- next plan에는 앞으로 할 작업만 남는다.
- 문서 계약 테스트와 diff check가 통과한다.

## P1 / Q46. RAG Golden Query Expected Source Coverage

### 목표

RAG 평가가 단순 keyword hit뿐 아니라 expected source id를 맞히는지 검증한다.

### 구현 범위

- eval set query에 `expected_source_ids`와 optional `expected_source_types`를 지원한다.
- `scripts/run_rag_eval.py`는 retrieved chunk의 `source_refs[].source_id`와 chunk id를 비교해 source coverage를 계산한다.
- report summary에 `expected_source_coverage`, `expected_source_hit_count`, `expected_source_total_count`를 추가한다.
- release gate threshold로 `--min-expected-source-coverage`를 추가한다.

### 검증 대상

- requirement query가 requirement/text source id를 찾는지 확인한다.
- table-field query가 table row 또는 technical table unit source id를 찾는지 확인한다.
- missing source id는 query별 diagnostics와 gate regression으로 남긴다.

### 완료 조건

- Q46 fixture/eval test가 deterministic하게 통과한다.
- 기존 hit@k/MRR/citation coverage 동작은 유지된다.
- release gate `rag` command에서 expected source coverage threshold를 전달할 수 있다.

### 구현 결과

- eval set query에 `expected_source_types`를 추가해 chunk id와 source_refs source type을 함께 검증할 수 있다.
- `rag_eval_report.json` metrics에 `expected_source_coverage`, hit/total/miss count를 추가했다.
- query별 결과에 `missing_expected_source_ids`를 기록해 golden source id 누락 원인을 바로 추적할 수 있다.
- `scripts/run_release_gates.py`의 `rag` gate가 `--rag-min-expected-source-coverage` threshold를 전달한다.

## P1 / Q44. Domain Technical Table Coverage Expansion

### 목표

NVMe/PCIe/OCP/TCG technical table row를 더 구체적인 typed unit으로 분류해 agent가 register/opcode/security table provenance를 안정적으로 추적하게 한다.

### 구현 범위

- `technical_tables_rag.jsonl` classification을 보강한다.
- register map/bitfield, command opcode, log page, feature identifier, security method/object/authority/field fixture를 확장한다.
- domain adapter output이 technical table unit provenance를 유지하는지 테스트한다.

### 검증 대상

- `unit_type`, `bit_range`, `field_name`, `opcode`, `command`, `log_identifier`, `feature_identifier`, `source_refs`가 안정적으로 채워지는지 확인한다.
- conservative confidence와 classification reasons가 불명확한 row를 과분류하지 않는지 확인한다.

### 완료 조건

- `tests/test_rag_technical_tables.py`, `tests/test_rag_domain_adapters.py`, golden corpus 또는 focused fixture가 통과한다.
- Q46 expected source coverage query가 Q44 technical table source ids를 검증할 수 있다.

### 구현 결과

- `technical_tables_rag.jsonl`가 TCG `security_object`, `security_authority`, `security_field` row를 `security_method`와 구분해 typed unit으로 분류한다.
- security field/description/UID 계열 header를 normalized fields와 classification reasons에 보존한다.
- domain adapter records built from technical table rows now carry both `table_row` and `technical_table_unit` source refs.
- Q46 expected source coverage로 `technical_table_unit` source id를 검증하는 focused test를 추가했다.

## P1 / Q47. Local Technical Corpus Evidence Pack

### 목표

비공개/대형 technical corpus에서만 드러나는 failure pattern을 원본 PDF, local path, command, customer/vendor filename, eval query text 없이 공유 가능한 local-only evidence pack으로 정리한다.

Q47은 97/100 이후 남은 리스크를 “새 heuristic을 먼저 추가”하는 방식이 아니라, 실제 local corpus 운영 중 반복되는 실패 signature를 축적하고 우선순위를 판단할 수 있게 만드는 작업이다.

### 구현 범위

- `scripts/run_ssd_corpus_profile.py`에 opt-in `--evidence-pack`, `--evidence-pack-path`, `--evidence-profile-label` 옵션을 추가한다.
- `ssd_corpus_profile_report.json`의 contract finding code/path를 보존해 evidence pack signature 생성에 사용한다.
- `local_corpus_evidence_pack.json` public JSON 출력을 추가한다.
- evidence pack은 redacted `document-000001` 형태 label만 사용하고 raw `input_pdf`, `output_dir`, command, document name, query text를 포함하지 않는다.
- conversion exit code, SSD contract error/warning, RAG threshold failure, corpus budget failure를 deterministic `sig-<hash>` signature로 집계한다.
- `docs/OUTPUT_SCHEMA.md`, `docs/schema/local_corpus_evidence_pack.schema.json`, README, Windows guide, RAG indexer recipe를 갱신한다.

### 출력 구조

- `schema_version`: `1.0`
- `purpose`: `local_technical_corpus_evidence_pack`
- `profile_label`
- `profile_fingerprint`
- `redaction_policy`
- `summary`
- `domains`
- `documents`
- `failure_signatures`

### 테스트

- `tests/test_ssd_rag_contract.py`
  - raw path, filename, command, query text가 evidence pack에 포함되지 않는지 확인한다.
  - 동일 입력에서 `profile_fingerprint`와 failure signature id가 결정적인지 확인한다.
  - contract/budget/RAG threshold failure가 signature로 집계되는지 확인한다.
  - CLI option이 evidence pack 파일을 쓰는지 확인한다.
- `tests/test_output_schema_contract.py`
  - 새 schema export/check 계약을 추가한다.
- `tests/test_docs_examples.py`
  - Q47 archive와 새 schema/output 문서 계약을 확인한다.

### 구현 결과

- private corpus 운영 결과를 raw output 대신 redacted signature pack으로 공유할 수 있다.
- 새 fixture나 heuristic을 추가하기 전에 domain/spec/category/metric/code별 반복 실패를 먼저 확인할 수 있다.
- public JSON schema 계약에 `local_corpus_evidence_pack.schema.json`이 추가됐다.

## P1 / Q48. Corpus Evidence Signature Analysis Report

### 목표

Q47 `local_corpus_evidence_pack.json`을 단일 실행 단위로 분석해 failure signature를 category/domain/spec/code/metric 기준으로 재집계하고, deterministic follow-up 후보를 제공한다.

### 구현 결과

- `scripts/analyze_corpus_evidence_pack.py`를 추가해 redacted evidence pack만 입력으로 사용하는 local-only 분석 report를 생성한다.
- `corpus_evidence_analysis_report.json`은 category hotspot, domain/spec hotspot, follow-up hint를 deterministic하게 정렬한다.
- public schema `docs/schema/corpus_evidence_analysis_report.schema.json`와 `docs/OUTPUT_SCHEMA.md`, README, Windows guide, RAG indexer recipe를 갱신했다.
- `tests/test_corpus_evidence_tools.py`가 report model validation, script smoke, follow-up hint 계약을 검증한다.

## P1 / Q49. Appendix Clause Requirement Fixture Expansion

### 목표

긴 appendix, nested clause, vendor-specific requirement table 주변 heading carry-over를 synthetic fixture와 regression test로 고정한다.

### 구현 결과

- `build_appendix_clause_requirement_pdf` synthetic fixture를 추가했다.
- appendix heading과 nested numeric clause heading path를 requirement text, requirement table row, technical table row, customer requirement domain unit에 보수적으로 carry-over한다.
- carry-over는 high-risk appendix/clause/requirement/vendor heading context에만 적용해 기존 table golden 출력의 불필요한 churn을 피한다.
- `tests/test_appendix_clause_requirements.py`가 Appendix A와 Table 1 cross-reference 해소, `VEND-APP-1`, `VEND-APP-2` traceability, technical/domain provenance를 검증한다.

## P2 / Q50. Captionless Diagram Diagnostics Hardening

### 목표

caption 없는 diagram/image 후보를 환각 없이 diagnostics-only로 기록하고, OCR/nearby text label 승격이 보수적으로 동작하는지 고정한다.

### 구현 결과

- `figures_rag.jsonl` record에 optional `captionless_diagnostics`를 추가했다.
- caption이 없고 낮은 confidence OCR 후보만 있는 경우 promoted label이나 caption을 만들지 않고 `low_confidence`, `missing_caption`, `no_promoted_ocr_labels` 같은 rejection reason만 남긴다.
- `docs/OUTPUT_SCHEMA.md`에서 `diagram_label_diagnostics`와 `captionless_diagnostics`를 optional diagnostics로 명확히 설명했다.
- `tests/test_rag_figures.py`가 captionless low-confidence 후보가 hallucinated caption 없이 diagnostics-only로 남는지 검증한다.

## P2 / Q51. Evidence Pack History Comparison Gate

### 목표

baseline/current `local_corpus_evidence_pack.json`을 비교해 신규, 해결, 지속 failure signature를 local-only report로 만든다.

### 구현 결과

- `scripts/compare_corpus_evidence_packs.py`를 추가했다.
- `corpus_evidence_trend_report.json`은 signature id 기준 `added`, `persisting`, `resolved` 상태와 summary count를 deterministic하게 산출한다.
- `--fail-on-new-signature`가 신규 error signature에서 non-zero exit code를 반환한다.
- public schema `docs/schema/corpus_evidence_trend_report.schema.json`와 운영 문서를 갱신했다.
- `tests/test_corpus_evidence_tools.py`가 trend report model validation, script smoke, failure gate를 검증한다.

## P2 / Q52. Quality Document And Schema History Contract

### 목표

scorecard, next plan, development specs, implemented archive, output schema 사이의 stale 히스토리 표현을 더 강하게 자동 검증한다.

### 구현 결과

- `tests/test_output_schema_contract.py`가 `scripts/export_output_schema.py`의 public schema 목록이 `docs/OUTPUT_SCHEMA.md`에 모두 문서화되어 있는지 확인한다.
- Q48-Q52 완료 후 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`와 `docs/QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md`는 active backlog 없음 상태로 돌아왔다.
- 이 archive와 `docs/QUALITY_SCORECARD.md`가 Q48-Q52 구현 결과를 포함하도록 갱신했다.

## P2 / Q53. Minimal Desktop GUI Wrapper

### 목표

CLI에 익숙하지 않은 비개발자와 간단한 설치/실행만 원하는 개발자가 PDF 파일 또는 폴더를 선택해 변환할 수 있도록 최소 desktop GUI를 추가한다.

Q53의 핵심은 새 변환 엔진을 만드는 것이 아니라, 기존 `Config`와 `run_conversion` 경로를 그대로 사용하는 얇은 GUI wrapper를 제공하는 것이다. GUI는 사용 편의성을 높이되, CLI와 다른 산출물 계약을 만들면 안 된다.

### 구현 범위

- `pdf2md/gui_runner.py`
  - GUI와 테스트가 함께 쓰는 순수 orchestration helper
  - 단일 파일 변환과 폴더 batch 변환 request를 `Config`로 변환
  - batch document naming은 CLI batch 계약과 맞춘다.
  - skip-existing은 core output인 Markdown, manifest, report가 모두 있을 때만 적용한다.
- `pdf2md/gui.py`
  - Tkinter app entry
  - 파일 선택 / 폴더 선택 / 출력 폴더 선택
  - 주요 옵션 form
  - worker thread 기반 실행
  - 진행 로그와 완료 summary 표시
- `pyproject.toml`
  - `pdf2md-gui = "pdf2md.gui:main"` entry point 추가

### 구현 결과

- `python -m pdf2md.gui`와 설치형 `pdf2md-gui` entry point로 최소 GUI를 실행할 수 있다.
- GUI는 단일 PDF와 폴더 batch 변환을 지원한다.
- GUI는 별도 변환 경로를 만들지 않고 `Config`와 `run_conversion`을 사용한다.
- headless CI에서는 Tk mainloop를 띄우지 않고 `python -m pdf2md.gui --help`, runner config, 단일 변환 산출물 동일성, batch skip-existing 정책을 테스트한다.
- README와 Windows guide에 GUI와 CLI의 역할 차이를 문서화했다.

### 비범위

- 대형 GUI application framework 도입
- Electron, Qt, web server 기반 UI
- PDF 미리보기/페이지 썸네일/본문 편집기
- 변환 산출물 수동 편집 기능
- 외부 RAG/indexing 서비스 호출
- GUI 전용 output schema 또는 CLI와 다른 변환 옵션 의미

## P1 / Q54. GUI Runtime And Install Diagnostics

### 목표

Q53 GUI wrapper가 실제 사용자 환경에서 시작되거나 변환을 실행하기 전에 실패할 수 있는 runtime/setup 문제를 core 변환 실패와 구분한다. 대상은 Python 버전, Tkinter runtime, module/entry point 설치 상태, input/output path 접근성이다.

### 구현 범위

- `pdf2md/gui_runner.py`
  - `GuiDiagnostic`, `GuiDiagnosticReport`, `GuiDiagnosticError` 추가
  - `check_gui_runtime()`로 Python 3.11+ 지원 범위, Tkinter import 가능성, `pdf2md.gui` module import, `pdf2md-gui` console script 설치 여부를 사전 점검
  - `validate_gui_request()`로 file/folder input, PDF 확장자, readable input, duplicate batch stem, output directory 생성 가능성을 변환 전 점검
  - `run_gui_conversion()`이 diagnostic error를 먼저 반환하도록 보호
- `pdf2md/gui.py`
  - GUI launch 전 runtime diagnostic error는 창을 띄우기 전에 stderr로 표시하고 종료
  - 변환 시작 전 request diagnostic error는 messagebox/log로 표시하고 worker thread를 시작하지 않음
  - warning은 변환을 막지 않고 GUI log에 남김
- `tests/test_gui_runner.py`
  - Tkinter 미설치, Python 버전 불일치, output path file collision을 headless unit test로 고정

### 구현 결과

- Tkinter/runtime/setup failure와 PDF 변환 실패가 GUI에서 구분된다.
- `python -m pdf2md.gui --help`는 계속 창을 띄우지 않고 종료한다.
- output path가 파일인 경우처럼 사용자가 직접 조치할 수 있는 오류는 raw traceback 대신 diagnostic message로 노출된다.
- CLI `pdf2md` 변환 경로와 public JSON schema는 변경하지 않았다.

### 비범위

- 설치형 GUI app packaging
- OS별 native installer
- GUI 전용 conversion schema
- 변환 중 결과 검토 UI, batch cancel/retry controls, distribution guide 확장

## P1 / Q55. GUI Conversion Result Review UX

### 목표

GUI 변환 완료 후 사용자가 Markdown만 확인하는 데서 끝나지 않고 `manifest.json`, `report.json`, partial success warning, failed/skipped 상태를 한 화면에서 확인할 수 있게 한다. 표시 정보는 구조화된 report/manifest 경로와 warning code/count로 제한하고, 원문 텍스트/표/이미지 내용을 요약하지 않는다.

### 구현 범위

- `pdf2md/gui_runner.py`
  - `GuiDocumentSummary`에 Markdown, manifest, report, assets path와 warning count/code를 추가
  - `format_gui_summary()`로 단일/배치 완료 summary를 deterministic 문자열로 생성
  - warning display는 message 본문 대신 sorted unique warning code와 count만 사용
  - skipped 문서도 기존 core output path를 summary에 포함
- `pdf2md/gui.py`
  - 완료 결과를 `ttk.Treeview` 표에 document/status/warnings/Markdown/report 열로 표시
  - 완료 message와 log가 동일한 structured summary를 사용
  - output folder 열기 실패는 변환 실패로 바꾸지 않고 GUI warning으로만 표시
- `tests/test_gui_runner.py`
  - single conversion artifact path summary 검증
  - skipped batch artifact path summary 검증
  - partial success warning count/code ordering과 warning message 미노출 검증

### 구현 결과

- GUI 완료 화면에서 success, partial_success, failed, skipped count와 문서별 core artifact path를 확인할 수 있다.
- warning은 원문 내용을 복사하지 않고 code/count 중심으로 표시된다.
- 기존 CLI output naming, `Config`, `run_conversion` 경로는 유지했다.

### 비범위

- report/manifest 내용 편집기
- PDF/Markdown preview
- 변환 중 취소와 재시도 후보 summary
- 새 public JSON schema
