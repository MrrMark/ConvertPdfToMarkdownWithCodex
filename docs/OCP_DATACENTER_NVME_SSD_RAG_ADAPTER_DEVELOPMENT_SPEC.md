# OCP Datacenter NVMe SSD RAG Adapter Development Spec

## 1. Purpose

이 문서는 OCP Datacenter NVMe SSD Specification을 NVMe Base/NVM Command Set adapter와 동등한 수준의
RAG ingest 품질로 끌어올리기 위한 개발 명세다.

목표는 `SpecAnalysisAgent`가 OCP 요구사항을 분석할 때 다음 질문에 안정적으로 답할 수 있게 하는 것이다.

- 특정 OCP requirement ID가 어떤 요구사항을 정의하는가?
- 특정 NVMe log page, feature, command, telemetry/statistic, security, thermal, form-factor requirement가 어디에서 왔는가?
- requirement가 normative text, table row, section context, source reference와 함께 추적 가능한가?
- 공식 최신 OCP PDF 전체 문서에서 sanitized benchmark와 query eval gate가 통과하는가?

## 2. Official Source

검토한 공식 원문:

- URL: `https://www.opencompute.org/documents/datacenter-nvme-ssd-specification-v2-7-final-pdf-1`
- Title: `Datacenter NVMe SSD Specification`
- Version: `2.7`
- Date marker: `01082026`
- Page count observed from official PDF: `253`

문서 구조상 OCP Datacenter NVMe SSD spec은 NVMe command opcode 자체보다 requirement/conformance matrix 성격이 강하다.
본문에는 `Requirement ID / Description` 표가 반복되고, NVMe log page, feature, telemetry, security, thermal, form factor,
device profile 요구사항이 함께 섞여 있다.

대표 섹션:

- NVM Express requirements
- NVMe Admin Command Set / I/O Command Set
- Optional NVMe Feature Support
- Command Timeout
- Log Page Requirements
- Host and Controller Initiated Telemetry Log Pages
- Set/Get Features Requirements
- PCIe Requirements
- Optional Device Features
- Reliability / Endurance / Thermal
- Form Factor Requirements
- Management Support
- Security
- Device Profiles
- Labeling / Compliance

## 3. Current Repository State

현재 repo에는 `DomainAdapterMode.OCP`와 SSD contract의 `OCP` spec type mapping이 이미 있다.

이미 있는 기반:

- `--domain-adapter ocp`
- OCP-style `Requirement ID / SSD / Requirement Description` row를 `domain_units_rag.jsonl`의 `requirement`로 생성
- requirement traceability sidecar
- generic technical table sidecar
- SSD contract validator의 `domain_adapter=ocp -> spec_type=OCP` mapping

현재 gap:

- OCP official latest PDF 전용 full benchmark wrapper/report가 없다.
- OCP requirement ID taxonomy가 없다.
- OCP 전용 normalized fields가 부족하다.
- OCP query eval gate가 없다.
- OCP golden slice fixture가 없다.
- `Requirement ID / Description`이 페이지 경계/표 continuation으로 끊길 때의 보강 기준이 명확하지 않다.
- OCP 문서에 포함된 NVMe log page, feature identifier, telemetry statistic, security/SPDM/TCG, form-factor requirement를
  agent 검색 hint로 충분히 구조화하지 못한다.

## 4. Quality Target

NVMe Base/NVM Command Set과 같은 정책을 따른다.

- Raw PDF text, raw Markdown body, generated query, retrieved text, image bytes, local input path는 benchmark report에 넣지 않는다.
- 원문 PDF와 변환 전체 output은 repo에 커밋하지 않는다.
- 공유 가능한 산출물은 sanitized benchmark report, scorecard, schema/docs, 합성 fixture/golden만 허용한다.
- source citation은 `source_refs`, `stable_source_id`, `stable_requirement_seed`, `requirement_traceability_rag.jsonl`로 추적한다.

공식 OCP v2.7 full benchmark 기대 기준:

- `conversion_status` is `success` or acceptable `partial_success` with zero contract errors.
- `contract_validation_passed=true`.
- `requirement_count > 0`.
- `requirement_traceability_count > 0`.
- `domain_unit_count > 0`.
- OCP query eval `expected_source_coverage >= 1.0` for required local eval set.
- OCP query eval `hit_at_k >= 1.0` for required local eval set.
- OCP query eval report is sanitized metrics-only.

성능 목표:

- 253쪽 공식 PDF full precision conversion이 local workstation에서 운영 가능해야 한다.
- NVMe Command Set 158쪽 full run이 약 67초였던 점을 기준으로, OCP 253쪽은 문서 복잡도에 따라 더 오래 걸릴 수 있다.
- 초기 목표는 full benchmark 3분 이내, warning/error trend 기록, 이후 baseline 기반 regression gate 도입이다.

## 5. OCP Domain Model

### 5.1 Requirement Unit

OCP adapter의 중심 domain unit이다.

필수 normalized fields:

- `requirement_id`
- `requirement_prefix`
- `requirement_number`
- `requirement_family`
- `requirement_section`
- `requirement_level`
- `description`
- `normative_strength`
- `source_table_id`
- `source_table_row_id`

권장 normalized fields:

- `topic`
- `ocp_profile`
- `applies_to`
- `dependency_refs`
- `related_nvme_object`
- `related_log_identifier`
- `related_feature_identifier`
- `related_command`
- `related_security_protocol`
- `related_form_factor`

### 5.2 Requirement Taxonomy

Requirement ID prefix를 우선 taxonomy로 사용한다.

초기 taxonomy 후보:

- `NVMe-*`: NVMe protocol/admin/I/O/optional feature requirement
- `CTO-*`: command timeout requirement
- `STD-LOG-*`: standard log page requirement
- `SLOG-*`: SMART / Health Information Extended log page requirement
- `ERL-*`: error recovery log page requirement
- `LM-*`: latency monitor requirement
- `TEL-*`: telemetry requirement
- `DST-*`: device self-test requirement
- `FW-*`: firmware update requirement
- `DP-*`: deallocation / namespace / data placement requirement
- `SET-*` or feature-specific IDs: Set/Get Features requirement
- `PCIe-*`: PCIe requirement
- `REL-*`: reliability requirement
- `END-*`: endurance requirement
- `THM-*`: thermal requirement
- `FF-*`: form factor requirement
- `MGMT-*`: management / NVMe-MI / VPD requirement
- `SEC-*`: security requirement
- `TCG-*`: TCG requirement
- `SPDM-*`: SPDM requirement
- `LABL-*`: labeling requirement
- `COMP-*`: compliance requirement

실제 prefix는 official PDF full conversion에서 발견되는 ID set을 근거로 보정한다.

### 5.3 OCP Technical Units

OCP 전용 adapter는 `requirement`만 만들지 않고, agent filter/rerank에 도움이 되는 table-like technical unit도 보존한다.

초기 unit type 후보:

- `ocp_requirement`
- `ocp_log_page_requirement`
- `ocp_feature_requirement`
- `ocp_telemetry_requirement`
- `ocp_statistic`
- `ocp_event_fifo`
- `ocp_timeout_requirement`
- `ocp_power_requirement`
- `ocp_thermal_requirement`
- `ocp_form_factor_requirement`
- `ocp_security_requirement`
- `ocp_profile_requirement`
- `ocp_compliance_requirement`

단, source text는 바꾸지 않는다. unit type과 normalized fields는 sidecar metadata로만 추가한다.

## 6. Implementation Plan

### P0. Official OCP Benchmark Baseline and Core Requirement Coverage

목표:

- 공식 OCP v2.7 PDF 전체를 local-only sanitized benchmark로 실행할 수 있게 한다.
- OCP requirement row를 안정적으로 domain unit과 traceability record로 만든다.

작업:

1. `scripts/run_latest_ocp_datacenter_nvme_ssd_benchmark.py` 추가
   - input PDF, output dir, mode, pages, fail-on-contract-error 지원
   - official source URL, expected title, expected version, date marker 기록
   - raw content/path 미포함
2. OCP synthetic slice fixture 추가
   - Requirement ID / Description
   - STD-LOG style log page requirement
   - feature identifier requirement
   - telemetry/statistic requirement
   - security/form-factor requirement
3. OCP domain adapter normalized fields 추가
   - requirement ID parsing
   - prefix/family/number
   - normative strength
   - related log/feature/command/security/form-factor hints
4. SSD contract validator OCP deep shape 추가
   - OCP domain unit presence
   - normalized field presence
   - source refs and stable metadata

수용 기준:

- 합성 OCP slice golden 통과
- 공식 OCP v2.7 full benchmark에서 `contract_validation_passed=true`
- report에 raw PDF text/path/query/result 미포함

### P1. OCP Relationship Context and Retrieval Quality

목표:

- requirement를 section/topic/NVMe object와 묶어 agent 검색 품질을 높인다.

작업:

1. requirement context enrichment
   - section heading path에서 `Log Page`, `Feature`, `Telemetry`, `Security`, `Thermal`, `Form Factor` context 추출
   - repeated `Requirement ID Description` continuation 처리 보강
2. contextual embedding text 보강
   - requirement prefix/family
   - related log identifier
   - related feature identifier
   - related command/security/form-factor
   - section path
3. cross-reference / traceability 보강
   - `see Section`, `Log Identifier`, `Feature Identifier`, `NVMe-*`, `SEC-*`, `TCG-*`, `SPDM-*` references
4. tests
   - requirement family별 retrieval priority 확인
   - source_refs 유지 확인
   - context embedding이 text를 변경하지 않는지 확인

수용 기준:

- OCP requirement chunks가 requirement ID, family, related NVMe object query에서 top-k 회수된다.
- raw `text` 필드는 원문 보존, `embedding_text`만 context prefix 사용.

### P2. OCP Query Eval Gate

목표:

- NVMe Command Set P2처럼 공식 OCP PDF 품질을 자동 판정하는 sanitized query eval gate를 만든다.

작업:

1. OCP eval profile 추가
   - `ocp_datacenter_nvme_ssd_p2_retrieval`
2. required eval buckets
   - `requirement`
   - `log_page_requirement`
   - `feature_requirement`
   - `telemetry_requirement`
   - `security_requirement`
   - `form_factor_or_thermal_requirement`
3. dynamic query generation
   - sidecar metadata에서 대표 row를 고른다.
   - query/result raw text는 report에 저장하지 않는다.
4. metrics-only report
   - status, passed, query_count
   - required/covered/missing buckets
   - hit_at_k, mrr, expected_source_coverage, table_field_coverage
   - raw_content_included=false
   - queries_included=false
   - retrieved_text_included=false
5. `--fail-on-ocp-eval-error` 추가

수용 기준:

- 공식 OCP v2.7 full benchmark에서 OCP P2 eval pass.
- scorecard에 OCP P2 metric 표시.
- docs/schema/test coverage 반영.

### P3. SpecAnalysisAgent Handoff Pack

목표:

- `ssd-verification-agent`의 `SpecAnalysisAgent`가 OCP 산출물을 쉽게 가져다 쓸 수 있게 한다.

작업:

1. OCP ingest recipe 추가
   - official PDF download location은 repo 밖 `/tmp` 권장
   - conversion output path
   - required sidecars
   - validator command
2. handoff metadata
   - spec family: `OCP`
   - spec title/version/date
   - expected sidecars
   - sanitized benchmark report path
3. representative analysis questions
   - requirement ID lookup
   - log page support
   - feature identifier behavior
   - telemetry statistic
   - timeout/security/form-factor compliance

수용 기준:

- agent handoff guide가 raw PDF/path 없이 sanitized summary 중심으로 작성된다.
- representative query set이 `expected_source_ids` 기반으로 평가 가능하다.

## 7. Recommended Work Order

1. P0-1: Official OCP benchmark wrapper and sanitized report model.
2. P0-2: OCP synthetic slice fixture and golden sidecars.
3. P0-3: OCP normalized requirement fields and contract validator deep shape.
4. P1-1: requirement family/topic/context enrichment.
5. P1-2: OCP contextual embedding/retrieval priority.
6. P2-1: OCP dynamic query eval and quality gate.
7. P2-2: official full PDF validation and scorecard.
8. P3: SpecAnalysisAgent handoff recipe.

## 8. Test Plan

Required local tests:

```bash
.venv311/bin/python -m pytest tests/test_rag_domain_adapters.py tests/test_rag_requirements.py -q
.venv311/bin/python -m pytest tests/test_rag_chunks.py tests/test_ssd_rag_contract.py -q
.venv311/bin/python -m pytest tests/test_quality_gate_scripts.py tests/test_golden_corpus.py -q
.venv311/bin/python -m pytest tests/test_output_schema_contract.py tests/test_docs_examples.py -q
.venv311/bin/python -m pdf2md --help
git diff --check
```

Official full validation:

```bash
.venv311/bin/python scripts/run_latest_ocp_datacenter_nvme_ssd_benchmark.py \
  --input-pdf /tmp/datacenter-nvme-ssd-specification-v2-7-final.pdf \
  --output-dir /tmp/pdf2md-latest-ocp-datacenter-nvme-ssd \
  --mode full_precision \
  --fail-on-contract-error \
  --fail-on-ocp-eval-error
```

## 9. Done Definition

OCP adapter work is complete when:

- official OCP v2.7 full PDF conversion completes locally.
- contract validator passes with zero errors.
- OCP domain units include stable requirement IDs and normalized fields.
- OCP P2 query eval passes with source coverage 1.0 for required buckets.
- benchmark report and scorecard are sanitized.
- synthetic golden fixture and tests pass.
- docs explain how `SpecAnalysisAgent` should consume the sidecars.

## 10. One-Line Rule

OCP는 requirement가 중심이다. 애매하면 원문 text는 그대로 두고, requirement ID / section / related NVMe object를 metadata로만 보강한다.
