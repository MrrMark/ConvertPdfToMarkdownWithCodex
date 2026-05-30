# Quality Improvement Development Specs

이 문서는 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에 남아 있는 **active Q 작업**을 실제 구현 PR로 옮기기 위한 개발 명세다.

완료된 Q 작업의 명세와 구현 결과는 이 문서에 남기지 않고 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에서 관리한다.

## 운영 규칙

- `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에 신규 Q 항목이 추가되면, 구현 전에 이 문서에 대응 개발 명세를 작성한다.
- 구현 중 범위가 바뀌면 Next Plan 항목과 이 문서를 함께 갱신한다.
- 구현 완료, 테스트 통과, PR merge까지 끝난 Q 항목은 이 문서에서 제거하고 완료 명세 archive로 옮긴다.
- 완료 이력은 Git commit, PR, release note, changelog, 그리고 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에서 추적한다.
- 이 문서에는 앞으로 구현할 active 명세만 있어야 한다.

## 공통 원칙

- 외부 RAG/indexing 서비스 호출은 구현 범위에 포함하지 않는다.
- 모든 검증과 fixture 생성은 local-only, deterministic 동작을 기본으로 한다.
- PDF 원문 텍스트, 표, 이미지 provenance는 요약하거나 재서술하지 않는다.
- 새 public JSON 출력이 생기면 `docs/OUTPUT_SCHEMA.md`와 `docs/schema/` 계약을 함께 갱신한다.
- 실패는 가능한 한 구조화된 report로 남기고, 어느 파일/record/field/page가 문제인지 식별 가능해야 한다.
- 테스트는 작은 unit test, script smoke test, golden regression test를 우선한다.

## 현재 Active Development Specs

### Q85. RAG Preset Status And Warning Severity Calibration

#### 배경

2026-05-30 로컬 GUI headless 비교에서 최신 NVMe Base Specification 2.3 전체 784페이지를 `RAG 등록용(최적화)`와 `기술 스펙 RAG`로 변환했다. 두 프리셋은 동일한 option matrix를 사용했고 `document.md`, `manifest.json`, RAG sidecar, image asset은 SHA 기준 동일했다. 두 변환 모두 `partial_success`였고 warning은 974건이었다.

주요 수치:

- `TABLE_COMPLEXITY_HTML_FALLBACK`: 973건
- `OCR_EMPTY_RESULT`: 1건, page 24
- `table_total`: 1080
- `table_html_count`: 973
- `table_gfm_count`: 107
- `table_low_quality_count`: 41
- `retrieval_chunk_record_count`: 23718
- `retrieval_chunk_over_target_count`: 0
- `artifact_integrity`: passed, warning/error 0
- `index_contract`: passed, warning/error 0

현재 `TABLE_COMPLEXITY_HTML_FALLBACK`은 advisory warning이지만, `OCR_EMPTY_RESULT`와 `table_low_quality_count > 0` 때문에 전체 status가 `partial_success`가 된다. RAG 등록용 preset 점수를 높이려면 정상적인 보수적 fallback을 실패처럼 보고하지 않고, 실제 운영자가 조치해야 하는 품질 리스크만 actionable로 남겨야 한다.

#### 목표

- `rag_optimized`가 의도한 보수적 HTML fallback과 실제 변환 위험을 분리한다.
- GUI summary에서 `partial_success` 원인이 무엇인지 즉시 알 수 있게 한다.
- OCR empty result가 blank/decorative/low-content page에서 발생한 경우 advisory로 분류한다.
- low-quality table이 RAG sidecar와 artifact/index validation을 통과한 경우 advisory low-quality로 분류하고, 실제 row/header provenance가 깨진 경우만 actionable로 남긴다.

#### 구현 범위

1. Warning severity taxonomy 확장
   - `reporting.py`의 advisory/actionable 분류를 code-only에서 code+details 기반으로 확장한다.
   - `TABLE_COMPLEXITY_HTML_FALLBACK`은 계속 advisory로 유지한다.
   - `OCR_EMPTY_RESULT`는 아래 조건 중 하나를 만족하면 advisory 후보로 분류한다.
     - `force_ocr == false`
     - page text extraction 결과가 실제로 empty이고 OCR 결과도 empty
     - page image/text diagnostics가 blank/decorative/low-content로 판단됨
   - 강제 OCR, scan-only page, 또는 OCR이 유일한 text recovery 경로인 경우에는 actionable로 유지한다.

2. Status decision 개선
   - `determine_conversion_status()`가 raw `table_low_quality_count` 대신 `table_actionable_low_quality_count`를 사용하게 한다.
   - report summary에 아래 필드를 추가한다.
     - `actionable_warning_count`
     - `advisory_warning_count`
     - `table_actionable_low_quality_count`
     - `table_advisory_low_quality_count`
     - `ocr_actionable_warning_count`
     - `ocr_advisory_warning_count`
   - 기존 schema 호환을 위해 `table_low_quality_count`는 유지한다.

3. GUI summary 개선
   - summary row에 전체 warning count만 표시하지 않고 actionable/advisory count를 분리한다.
   - `partial_success`인 경우 primary cause를 `actionable OCR`, `actionable table quality`, `failed page`, `extraction failed` 중 하나로 표시한다.

#### 수용 기준

- NVMe Base 2.3 `rag_optimized` 변환에서 artifact/index validation이 passed이고 actionable warning이 0이면 status는 `success`가 될 수 있어야 한다.
- 의도된 HTML fallback은 `warning_count`에는 남지만 `actionable_warning_count`에는 포함되지 않는다.
- 강제 OCR 실패나 scan page OCR empty는 계속 `partial_success`를 유발한다.
- 기존 tests/golden의 warning/report schema는 후방 호환된다.

#### 테스트 계획

- `tests/test_pipeline_reporting.py`
  - advisory `OCR_EMPTY_RESULT`는 success 유지
  - force OCR empty result는 partial 유지
  - advisory table fallback + advisory table quality는 success 유지
  - actionable low-quality table은 partial 유지
- `tests/test_gui_runner.py`
  - GUI summary에 actionable/advisory warning count가 반영되는지 확인
- `tests/test_output_schema_contract.py`
  - report schema 신규 필드 검증
- 실제 corpus smoke
  - NVMe Base 2.3 `rag_optimized`
  - 기존 NVMe focused fixture

### Q86. Full Technical Spec Table Quality Triage And Recovery

#### 배경

NVMe Base 2.3 전체 변환에서는 1080개 table 중 973개가 HTML fallback으로 보존됐고, 41개 table이 low-quality로 집계됐다. HTML fallback 자체는 제품 원칙상 올바른 보수적 선택이다. 문제는 low-quality 판정이 실제 위험인지, 아니면 기술 스펙 특유의 byte/bit layout, merged header, footnote row, repeated descriptor pattern 때문인지 구분이 부족하다는 점이다.

#### 목표

- low-quality table 41건을 원인별로 분류하고 실제 복구 우선순위를 만든다.
- RAG sidecar 관점에서 row provenance가 충분하면 advisory로 낮추고, header/cell alignment가 의심되는 경우만 actionable로 남긴다.
- 기술 스펙 table shape별 fixture를 추가해 회귀를 막는다.

#### 구현 범위

1. Table evidence pack
   - `table_quality_review_pack.json` 또는 기존 debug artifact에 다음 정보를 기록한다.
     - page, table_id, bbox, quality_score
     - fallback reasons
     - header strategy, header confidence
     - row count, empty-cell ratio, `Column N` header ratio
     - technical/domain unit 생성 여부
     - sample row_text hash 또는 sanitized preview
   - raw 원문 전체를 저장하지 않고 local-only 검토용으로 제한한다.

2. Technical table recovery
   - `Bytes / Description / Value` register layout table의 repeated descriptor pattern 복구
   - `Column N` placeholder header를 주변 header/row text로 재명명
   - continued table stitch 후보 탐지
   - footnote row 분리 후 table body score 재계산

3. Quality classification
   - `quality_score < 0.55`라도 아래 조건이면 advisory low-quality 후보로 둔다.
     - row count가 충분함
     - source_refs가 모두 유효함
     - technical/domain unit 생성 가능
     - artifact/index/provenance validation 통과
   - header alignment, row split, missing source_refs, sidecar mismatch가 있으면 actionable로 유지한다.

#### 수용 기준

- NVMe Base 2.3 기준 `table_actionable_low_quality_count`를 0에 가깝게 낮춘다.
- `table_low_quality_count`는 보존하되, status 판정은 actionable low-quality 기준으로 동작한다.
- table row 수와 technical table unit 수가 비의도적으로 감소하지 않는다.
- 복잡 표를 억지로 GFM으로 내보내지 않는다.

#### 테스트 계획

- `tests/test_tables.py`
  - descriptor layout recovery
  - continued table candidate
  - placeholder header renaming
- `tests/test_rag_tables.py`
  - recovered header가 `tables_rag.jsonl`에 반영되는지 확인
- `tests/test_rag_technical_tables.py`
  - byte/bit register table typed unit 유지
- golden corpus
  - table accuracy pack에 NVMe-style byte/descriptor table fixture 추가

### Q87. Technical Spec RAG Preset Domain Profile UX

#### 배경

현재 `rag_optimized`와 `technical_spec_rag`는 `rag_profiles.py`에서 동일한 option matrix를 사용한다. GUI에서는 preset이 `custom`이 아니면 advanced options가 잠기며, `domain_adapter`도 잠긴다. 따라서 GUI 사용자가 `기술 스펙 RAG`를 선택하면 실제로는 `domain_adapter=none`으로 변환되고, NVMe/PCIe/OCP/TCG domain unit이 생성되지 않는다.

#### 목표

- `기술 스펙 RAG`가 `RAG 등록용(최적화)`와 명확히 다른 산출물을 만들 수 있게 한다.
- 기술 스펙 preset에서는 spec family 선택을 first-class UX로 제공한다.
- CLI와 GUI의 profile/preset 계약을 동일하게 유지한다.

#### 구현 범위

1. Preset model 정리
   - `rag_optimized`: 일반 문서 RAG ingest용. domain adapter 기본값은 `none`.
   - `technical_spec_rag`: storage/security technical spec ingest용. domain adapter 선택을 요구하거나 권장한다.
   - GUI에는 `Technical domain` 또는 `Spec family` 선택을 별도 노출한다.
   - `technical_spec_rag` 선택 시 `domain_adapter`는 잠그지 않고 `none/nvme/pcie/ocp/tcg/spdm` 중 선택 가능하게 한다.

2. CLI profile 개선
   - `--rag-profile technical_spec_rag` 사용 시 `--domain-adapter`가 없으면 report advisory를 남긴다.
   - optional strict mode: `--require-domain-adapter-for-technical-profile`
   - batch/corpus profile에서는 domain adapter를 문서별로 지정할 수 있게 한다.

3. Output differentiation
   - technical profile + domain adapter는 `domain_units_rag.jsonl`을 생성한다.
   - `retrieval_chunks_rag.jsonl`에 `chunk_type=domain_unit`이 포함된다.
   - report summary에 `technical_profile_domain_adapter_missing` 또는 `domain_unit_record_count`를 명확히 기록한다.

#### 수용 기준

- GUI에서 `기술 스펙 RAG + NVMe` 선택 후 변환하면 `manifest.options.domain_adapter == "nvme"`이고 `domain_units_rag.jsonl`이 생성된다.
- `RAG 등록용(최적화)`와 `기술 스펙 RAG + domain` 산출물은 domain sidecar/chunk 기준으로 차이가 난다.
- `technical_spec_rag` without domain adapter는 변환은 계속하되 advisory를 남긴다.
- 기존 custom preset은 현재 동작을 유지한다.

#### 테스트 계획

- `tests/test_gui_presets.py`
  - technical preset에서 domain field editable
  - technical preset에 domain을 적용하는 helper 추가
- `tests/test_gui_runner.py`
  - GUI technical domain config가 pipeline으로 전달되는지 확인
- `tests/test_cli.py`
  - technical profile without domain advisory
  - technical profile with domain creates domain sidecar
- `tests/test_docs_examples.py`
  - README/GUI guide의 preset 설명 갱신

### Q88. Storage And Security Domain Adapter Expansion

#### 배경

현재 domain adapter는 `nvme`, `pcie`, `ocp`, `tcg`, `customer-requirements`를 지원한다. 사용자 대상 corpus는 SSD storage 관련 NVMe/PCIe/OCP와 security 관련 TCG/SPDM까지 포함한다. SPDM은 현재 first-class adapter가 없고, TCG adapter도 method/object/authority/security field 중심이라 security protocol message/measurement/certificate/algorithm table coverage는 더 확장해야 한다.

#### 목표

- Storage domain: NVMe, PCIe, OCP table shape coverage를 확장한다.
- Security domain: TCG와 SPDM을 별도 first-class profile로 다룬다.
- domain unit이 RAG eval expected source coverage와 SSD agent contract에 직접 연결되게 한다.

#### 기술 요인

- NVMe: command/opcode, feature identifier, log page identifier, status code, register field, bit range, CNS/CSI/LID/FID 같은 식별자.
- PCIe: capability/register/offset/address, bit field, access/reset/default, link state, error reporting, ECN-style change table.
- OCP: Requirement ID, requirement text, optional/mandatory, telemetry/log page, compliance condition, testability hint.
- TCG: method, UID/object, authority, security provider, session, locking range, key management, table-driven state.
- SPDM: message code, request/response pair, version negotiation, measurement index/slot, certificate chain, algorithm suite, key exchange, session state, transcript/hash dependency.

#### 구현 범위

1. Schema/model
   - `DomainAdapterMode.SPDM = "spdm"` 추가
   - `docs/schema/manifest.schema.json`, `docs/OUTPUT_SCHEMA.md`, GUI domain combo, CLI help 갱신
   - SSD contract mapping에 `spdm -> HIL/SPDM` 추가

2. Domain extraction
   - `SPDM_HEADER_TOKENS` 추가
   - SPDM-specific unit types:
     - `spdm_message`
     - `spdm_request_response`
     - `spdm_measurement`
     - `spdm_certificate`
     - `spdm_algorithm`
     - `spdm_key_exchange`
     - `spdm_session`
   - TCG unit types 보강:
     - `security_provider`
     - `locking_range`
     - `key_management`
     - `session_state`

3. Retrieval chunk integration
   - `domain_unit` chunk priority를 technical/security 질의에 맞게 높인다.
   - domain unit에는 `domain`, `adapter_profile`, `unit_type`, normalized identifier fields를 metadata로 유지한다.

4. Corpus profile
   - local-only profile 예시:
     - NVMe Base / NVMe Command Set
     - PCIe Base or capability-focused sample
     - OCP Datacenter NVMe SSD
     - TCG storage/security sample
     - SPDM sample

#### 수용 기준

- 각 domain adapter focused fixture에서 최소 3개 이상의 distinct unit_type이 생성된다.
- SPDM fixture에서 message/request-response/measurement/certificate or algorithm unit이 생성된다.
- `retrieval_chunks_rag.jsonl`에 domain unit source_refs가 포함된다.
- `validate_ssd_rag_contract.py`가 SPDM first-class spec type을 통과한다.

#### 테스트 계획

- `tests/test_rag_domain_adapters.py`
  - SPDM adapter fixtures 추가
  - TCG expanded unit type fixtures 추가
- `tests/test_rag_chunks.py`
  - domain unit chunk priority/source_refs 검증
- `tests/test_ssd_rag_contract.py`
  - SPDM first-class `HIL/SPDM` mapping 추가
- `tests/test_output_schema_contract.py`
  - schema enum 갱신

### Q89. Real Corpus Preset Evaluation And Score Gate

#### 배경

이번 비교는 수동 headless GUI script로 수행했다. 반복 가능한 품질 평가를 위해 preset별 conversion, artifact/index/provenance validation, score 산정을 local-only runner로 고정해야 한다.

#### 목표

- GUI preset별 산출물 차이와 점수를 자동 산출한다.
- RAG 등록용과 기술 스펙 RAG의 목적별 score를 분리한다.
- 실제 corpus를 커밋하지 않고 sanitized report/evidence pack만 남긴다.

#### 구현 범위

1. Preset comparison runner
   - `scripts/benchmark_gui_presets.py` 또는 `scripts/run_preset_eval.py` 추가
   - 입력: PDF path, preset list, optional domain adapter, output root
   - 출력:
     - `preset_eval_report.json`
     - `preset_artifact_comparison.json`
     - `preset_scorecard.md`

2. Score model
   - RAG 등록용 100점 기준:
     - artifact/index/provenance integrity 20
     - actionable warning 15
     - chunk token compliance 15
     - source-ref presence/duplicate guard 15
     - table/requirement/figure sidecar coverage 15
     - cross-ref resolved coverage 10
     - conversion performance/repeatability 10
   - 기술 스펙 RAG 100점 기준:
     - domain unit coverage 20
     - technical table typed coverage 15
     - requirement traceability 15
     - cross-ref resolved coverage 15
     - SSD contract validation 15
     - artifact/index/provenance integrity 10
     - actionable warning/performance 10

3. Gates
   - `rag_optimized` target:
     - actionable warnings == 0
     - retrieval chunks over target == 0
     - artifact/index/provenance warnings == 0
   - `technical_spec_rag + domain` target:
     - domain_unit_record_count > 0
     - technical_table_record_count > 0
     - SSD contract pass
     - representative RAG eval coverage thresholds pass

#### 수용 기준

- NVMe Base 2.3 또는 focused NVMe sample에서 preset score report가 생성된다.
- `rag_optimized`와 `technical_spec_rag + nvme`의 차이가 domain unit/chunk/score에 나타난다.
- report는 raw PDF text, table body, image content를 대량 복사하지 않는다.

#### 테스트 계획

- `tests/test_quality_gate_scripts.py`
  - score calculation unit test
  - missing domain adapter warning
  - score threshold fail/pass
- `tests/test_gui_smoke_evidence.py`
  - preset comparison summary가 raw content를 저장하지 않는지 확인
- release gate optional wiring
  - `scripts/run_release_gates.py --gates preset-eval`

## 완료 명세 Archive

완료된 Q34-Q84 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
