# NVMe Base RAG Adapter Development Spec

작성일: 2026-06-14

## 문서 목적

이 문서는 PDF2MD repo에서 NVMe Base Specification을 `technical_spec_rag` 용도로
변환할 때 필요한 개발 플랜과 구현 명세를 정의한다. SSD Verification Agent의
SpecAnalysisAgent가 Requirement_ID, policy, FW/HW allocation, TC_ID, Test Script
coverage를 안정적으로 생성할 수 있도록 PDF2MD가 제공해야 하는 sidecar 품질을
고정하는 것이 목표다.

현재 기준:

- repo: `MrrMark/ConvertPdfToMarkdownWithCodex`
- branch baseline: `main`
- latest baseline commit: `5834315`
- 관련 구현:
  - `pdf2md/rag_profiles.py`
  - `pdf2md/serializers/rag_chunks.py`
  - `pdf2md/serializers/rag_requirements.py`
  - `pdf2md/serializers/rag_technical_tables.py`
  - `pdf2md/serializers/rag_domain_adapters.py`
  - `scripts/validate_ssd_rag_contract.py`

## 제품 원칙

- PDF2MD는 원문을 요약, 재서술, 교정하지 않는다.
- 기술 spec RAG sidecar는 source locator와 normalized metadata를 제공한다.
- 복잡 table은 안전하게 보존한다. 잘못된 GFM table보다 table sidecar와 HTML fallback이 낫다.
- 모든 heuristic은 deterministic해야 하며 confidence와 reason을 남긴다.
- full official PDF나 대형 raw 변환 산출물은 fixture로 그대로 커밋하지 않는다.
- NVMe Base는 Open Spec이지만 운영 contract는 Secure RAG 사용을 전제로 설계한다.

## Downstream Contract

SSD Verification Agent가 기대하는 주요 output:

- `retrieval_chunks_rag.jsonl`
- `requirements_rag.jsonl`
- `requirement_traceability_rag.jsonl`
- `technical_tables_rag.jsonl`
- `domain_units_rag.jsonl`
- `tables_rag.jsonl`
- `manifest.json`
- `report.json`
- `ssd_rag_contract_report.json`

공통 필수/권장 필드:

| field | purpose |
| --- | --- |
| `schema_version` | contract compatibility |
| `source_sha256` | source identity |
| `source_refs` | source locator |
| `page_range` | citation and review navigation |
| `section_path`, `heading_path` | section coverage and revision diff |
| `source_dedupe_key` | duplicate control and diff identity |
| `stable_source_id` | deterministic source node id |
| `stable_requirement_seed` | downstream `REQ_` business ID seed |
| `classification_confidence` | downstream ranking |
| `classification_reasons` | explainability |

NVMe 특화 권장 필드:

| field | purpose |
| --- | --- |
| `candidate_kind` | requirement/definition/note/table_parameter/review_only |
| `normative_strength` | mandatory/recommended/optional/prohibited/informative |
| `domain_unit_id` | command/log/feature/register/status rollup |
| `technical_table_unit_id` | typed table row locator |
| `table_id`, `table_row_id` | row-level coverage |
| `verification_intent` | conformance/test/review signal |
| `applicability_hint` | required/optional/vendor-specific/not-applicable hint |

## Current Gap

현재 구현은 `technical_spec_rag`, `domain_adapter=nvme`, technical table sidecar,
domain unit sidecar, requirement traceability sidecar의 기반을 갖고 있다.

남은 gap:

- NVMe Base 전용 taxonomy가 command/log/feature/register 중심으로 아직 얕다.
- `domain_unit_id`와 `trace_id`가 ordinal 기반이라 downstream ID stability가 부족하다.
- requirement traceability record가 table/domain linkage와 stable seed를 충분히 제공하지 않는다.
- front matter, note, example, definition, table parameter가 requirement 후보와 섞일 수 있다.
- NVMe Base real-spec slice 기반 golden gate가 부족하다.

## Work Tracks

### P2M-NVME-1. Stable Source ID and Requirement Seed

목표:

- 재변환 후에도 downstream Requirement_ID가 흔들리지 않도록 stable seed를 sidecar에 추가한다.

권장 seed:

```text
stable_source_id = sha1(source_sha256 + page_range + section_path + source_type + source_id + normalized_text_hash)
stable_requirement_seed = sha1(source_sha256 + section_path + table_row_id/domain_unit_id + normalized_requirement_text)
```

적용 대상:

- `retrieval_chunks_rag.jsonl`
- `requirements_rag.jsonl`
- `requirement_traceability_rag.jsonl`
- `technical_tables_rag.jsonl`
- `domain_units_rag.jsonl`

수용 기준:

- 동일 입력과 동일 옵션에서 stable ID가 재현된다.
- 기존 ordinal id는 유지하되 downstream은 stable seed를 우선 사용할 수 있다.
- locator가 부족하면 warning/reason을 남긴다.

검증:

```bash
python -m pytest tests/test_rag_chunks.py tests/test_rag_requirements.py tests/test_rag_domain_adapters.py
```

### P2M-NVME-2. NVMe Technical Table Typing

목표:

- NVMe Base table row를 downstream traceability에 필요한 typed unit으로 더 정밀하게 분류한다.

추가 unit type:

- `command_opcode`
- `log_page`
- `feature_identifier`
- `register_field`
- `status_code`
- `queue_field`
- `namespace_field`
- `controller_field`
- `support_requirement`
- `data_structure_field`
- `enum_value`
- `technical_parameter`

header alias:

- `Command`, `Command Name`, `Opcode`, `Command Opcode`
- `Log Identifier`, `LID`, `Log Page Identifier`
- `Feature Identifier`, `FID`
- `Register`, `Property`, `Offset`, `Bits`, `Bit`
- `Status Code`, `SCT`, `SC`, `Code`
- `Controller Support`, `Controller Support Requirements`
- `Namespace Support`, `NVM Subsystem`, `Scope`
- `Reset`, `Reset Default`, `Access`, `Attributes`

수용 기준:

- multi-line/merged header가 있어도 normalized field가 최대한 채워진다.
- 모호한 row는 과확정하지 않고 `technical_parameter` 또는 warning으로 남긴다.
- table row source provenance가 유지된다.

검증:

```bash
python -m pytest tests/test_rag_technical_tables.py tests/test_rag_domain_adapters.py
```

### P2M-NVME-3. NVMe Domain Unit Normalized Fields

목표:

- `domain_units_rag.jsonl`이 SSD agent의 feature coverage rollup에 바로 쓰일 수 있도록
  NVMe normalized schema를 확장한다.

권장 `normalized_fields`:

| field | example |
| --- | --- |
| `unit_type` | `command`, `log_page`, `feature`, `register_field`, `status_code` |
| `canonical_name` | `Identify`, `Get Log Page` |
| `opcode` | `0x06` |
| `log_identifier` | `0x02` |
| `feature_identifier` | `0x0C` |
| `register_name` | `CAP`, `CC`, `CSTS` |
| `offset` | `0x0000` |
| `bit_range` | `15:0` |
| `field_name` | `MQES` |
| `status_code_type` | `generic`, `command_specific` |
| `status_code_value` | `0x00` |
| `controller_support` | `mandatory`, `optional`, `reserved` |
| `namespace_support` | `mandatory`, `optional`, `not_applicable` |
| `scope` | `controller`, `namespace`, `subsystem`, `queue` |
| `access` | `RO`, `RW`, `RW1C` |
| `reset_default` | source value |
| `requirement_ref` | explicit requirement id if present |

수용 기준:

- 기존 TCG/SPDM/PCIe/customer adapter behavior가 깨지지 않는다.
- NVMe fields는 빈 값이면 생략한다.
- classification reasons에 어떤 header/field로 판정했는지 남긴다.

검증:

```bash
python -m pytest tests/test_rag_domain_adapters.py tests/test_ssd_rag_contract.py
```

### P2M-NVME-4. Requirement Traceability Expansion

목표:

- `requirement_traceability_rag.jsonl`이 SSD agent의 Requirement_ID 후보 생성에 충분한
  정보를 제공하도록 확장한다.

추가 필드:

- `stable_requirement_seed`
- `stable_source_id`
- `source_dedupe_key`
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
- `dependency_refs`
- `applicability_hint`

candidate kind:

- `normative_requirement`
- `structured_requirement`
- `technical_parameter`
- `definition`
- `note`
- `example`
- `front_matter`
- `review_only`

수용 기준:

- 기존 `requirement_id`, `trace_id`, `text`, `source_refs`는 유지된다.
- explicit requirement ID가 없는 NVMe Base 문단도 stable seed를 갖는다.
- definition/note/example은 downstream에서 Requirement_ID 자동 승격을 피할 수 있게 표시된다.

검증:

```bash
python -m pytest tests/test_rag_requirements.py tests/test_appendix_clause_requirements.py
```

### P2M-NVME-5. Requirement Precision Filters

목표:

- NVMe Base에서 requirement 후보가 과추출되지 않도록 front matter, legal, introduction,
  note, example, definition을 구분한다.

필터 신호:

- section title/path
- `normative_strength`
- modal verb presence
- table row type
- note/example prefix
- legal/front matter page or heading
- references/index/appendix context

수용 기준:

- 제외 후보도 필요하면 `review_only` record로 추적 가능하다.
- false negative를 줄이기 위해 hard drop보다 candidate kind와 exclusion reason을 우선한다.
- 기존 generic requirement extraction test가 깨지지 않는다.

검증:

```bash
python -m pytest tests/test_rag_semantics.py tests/test_rag_requirements.py
```

### P2M-NVME-6. SSD Contract Validator Deep Checks

목표:

- `validate_ssd_rag_contract.py`가 `domain_adapter=nvme`일 때 NVMe-specific shape를 검증한다.

추가 검사:

- domain unit에 command/log_page/feature/register_field 중 하나 이상 존재.
- technical table unit에 table provenance 존재.
- source_sha256가 모든 primary sidecar에 존재.
- stable ID field 존재.
- unit type별 NVMe normalized fields 최소 조건 만족.
- `technical_spec_rag`에서 `domain_adapter=none`이면 failure 또는 명확한 warning.

수용 기준:

- validator report가 deterministic error/warning code를 반환한다.
- SSD agent가 실패 owner를 `pdf2md_output`, `secure_rag_ingest`, `ssd_agent`로 분리할 수 있다.

검증:

```bash
python -m pytest tests/test_ssd_rag_contract.py tests/test_quality_gate_scripts.py
```

### P2M-NVME-7. NVMe Base Golden Slice Pack

목표:

- latest NVMe Base full PDF를 repo에 넣지 않고, sanitized/minimal fixture로 adapter quality를 잠근다.

fixture slice:

- command opcode table
- log page identifier table
- feature identifier table
- register bitfield table
- normative requirement paragraph
- note/example paragraph

수용 기준:

- fixture는 raw official spec 전문을 길게 포함하지 않는다.
- expected sidecar는 stable ID, candidate kind, domain unit, table row provenance를 검증한다.
- golden update는 의도적 schema 변경일 때만 수행한다.

검증:

```bash
python -m pytest tests/test_rag_domain_adapters.py tests/test_rag_technical_tables.py tests/test_golden_corpus.py
```

### P2M-NVME-8. Latest NVMe Base Benchmark

목표:

- real latest NVMe Base conversion의 성능과 산출물 품질을 정량화한다.

측정 항목:

- page count
- conversion duration
- sidecar file size
- retrieval chunk count
- requirement count
- traceability record count
- technical table unit count
- domain unit count
- contract validation status
- warning/error count

수용 기준:

- benchmark report에는 raw spec 전문을 포함하지 않는다.
- source URL, source_sha256, option matrix, summary counts만 포함한다.
- full precision mode와 fast smoke mode를 구분한다.

검증:

```bash
python -m pytest tests/test_quality_gate_scripts.py
```

### P2M-NVME-9. Output Schema and Docs Update

목표:

- 새 NVMe fields와 stable ID contract를 문서화한다.

수정 대상:

- `docs/OUTPUT_SCHEMA.md`
- `docs/RAG_INDEXER_INTEGRATION_RECIPES.md`
- `docs/AGENT_SKILL_USAGE_GUIDE.md`
- `scripts/export_output_schema.py`

수용 기준:

- schema docs와 실제 JSONL key가 일치한다.
- backward compatibility field가 명시된다.
- SSD Verification Agent handoff command가 포함된다.

검증:

```bash
python -m pytest tests/test_output_schema_contract.py tests/test_docs_examples.py
```

## Recommended PR Sequence

1. P2M-NVME-1: stable source ID and requirement seed.
2. P2M-NVME-2 + P2M-NVME-3: technical table and domain unit precision.
3. P2M-NVME-4 + P2M-NVME-5: requirement traceability expansion and precision filters.
4. P2M-NVME-6: SSD contract validator deep checks.
5. P2M-NVME-7: NVMe Base golden slice pack.
6. P2M-NVME-8: latest NVMe Base benchmark.
7. P2M-NVME-9: output schema and docs finalization.

## Definition of Done

- `technical_spec_rag + domain_adapter=nvme` output contains stable seeds and NVMe normalized fields.
- SSD Verification Agent can generate deterministic `REQ_`, `PR_`, `FW_`, `HW_`, `TC_` IDs from sidecars.
- table row and domain unit provenance survive conversion and validation.
- NVMe Base golden slices pass tests.
- contract validator can fail fast on missing NVMe-critical metadata.
- docs explain how SSD Verification Agent should consume the sidecars.
