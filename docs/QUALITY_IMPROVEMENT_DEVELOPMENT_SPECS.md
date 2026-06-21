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

### Q144. Wide Technical Table Header Semantics

#### 목표

NVMe reservation matrix, status/register bitfield table, OCP compliance matrix처럼 넓고 다층 header를 가진 표에서 RAG sidecar의 컬럼 의미 손실을 줄인다. Markdown 출력은 기존 보수 정책을 유지하며, 복잡 표는 계속 HTML fallback을 우선한다.

#### 범위

- table extraction 이후 RAG payload 생성 단계에서 parent/child header lineage를 보존한다.
- `Column N` fallback header가 생긴 경우 가능한 parent header, stub header, neighboring header, caption/heading context를 별도 metadata로 기록한다.
- `tables_rag.jsonl`, `technical_tables_rag.jsonl`, `domain_units_rag.jsonl`, `retrieval_chunks_rag.jsonl`의 context metadata가 header lineage를 사용할 수 있게 한다.
- table confidence/fallback diagnostics에 header lineage 품질 신호를 추가한다.

#### 제외 범위

- 복잡 표를 억지로 GFM으로 변환
- pdfplumber 외 신규 table engine의 기본 runtime 도입
- 셀 내용을 추정/보정하는 의미 변경 후처리

#### 구현 단계

1. `pdf2md/extractors/tables.py`의 multi-row header flattening, placeholder header, stub cell 경로를 정리한다.
2. `RagTablePayload.records[]`에 `header_lineage` 또는 `column_header_path` 후보 필드를 설계한다.
3. `pdf2md/serializers/rag_tables.py`와 `rag_technical_tables.py`가 새 header lineage를 보존하도록 확장한다.
4. NVMe overwide/multi-row matrix fixture를 추가해 `Column N`만 남는 상황을 재현한다.
5. 기존 schema/docs를 갱신한다.

#### 검증 기준

- `python -m pytest tests/test_tables.py tests/test_rag_tables.py tests/test_rag_technical_tables.py`
- overwide/multi-row table 신규 fixture에서 `Column N`만으로는 손실되던 parent/child context가 sidecar metadata에 남는다.
- Markdown body는 기존 HTML fallback 정책을 유지한다.
- `git diff --check`

#### 성공 조건

- wide table의 RAG row가 검색/검증 가능한 header path를 가진다.
- table confidence와 fallback reason이 더 구체적인 triage 정보를 제공한다.

### Q145. Security Spec Text-Derived Domain Candidate Layer

#### 목표

TCG/SPDM/Caliptra 보안 스펙에서 표로 추출되지 않는 본문/목록/heading 기반 domain signal을 보수적으로 기록한다. 기존 table-derived `domain_units_rag.jsonl` 계약은 신뢰도 높은 1차 산출물로 유지하고, 본문 기반 후보는 review 중심 계층으로 분리한다.

#### 범위

- SPDM message flow, request/response relationship, algorithm/certificate/measurement 설명 후보
- TCG method/object/authority/session/locking range 설명 후보
- Caliptra asset/threat/RoT service/mailbox/register/security state 설명 후보
- 후보 record에는 source refs, heading path, candidate kind, confidence, classification reasons, review flag를 포함한다.
- retrieval chunk에는 review-only semantic type 또는 낮은 priority를 부여한다.

#### 제외 범위

- 본문 내용을 요약/재서술한 domain unit 생성
- low-confidence 후보를 확정 domain unit으로 승격
- 생성형 분류기 또는 외부 API 호출

#### 구현 단계

1. 현재 `semantic_units_rag.jsonl`, `requirement_traceability_rag.jsonl`, `text_blocks_rag.jsonl`에서 재사용 가능한 source span 구조를 확인한다.
2. 새 sidecar를 만들지, `domain_units_rag.jsonl`에 `candidate_status=review_only`로 포함할지 결정한다. schema 안정성 관점에서는 별도 sidecar 또는 명시 status가 필요하다.
3. security adapter별 keyword/heading pattern을 `rag_domain_adapters.py`에서 table row logic과 분리해 구현한다.
4. 후보 record가 retrieval chunk에 들어갈 때 낮은 priority와 `review_only` semantic type을 갖도록 `rag_chunks.py`를 확장한다.
5. security text fixture를 추가한다.

#### 검증 기준

- `python -m pytest tests/test_rag_domain_adapters.py tests/test_rag_chunks.py`
- 신규 security text fixture에서 review-only candidate가 생성되고, 확정 table-derived unit과 구분된다.
- raw text는 source-derived span 범위만 사용하고 생성/요약 텍스트를 만들지 않는다.
- `git diff --check`

#### 성공 조건

- 표가 없는 security spec section에서도 검색 가능한 후보 provenance가 남는다.
- SSD/RAG contract validator가 확정 unit과 review candidate를 혼동하지 않는다.

### Q146. Large Spec Plan Apply Workflow

#### 목표

대형 NVMe/OCP/TCG/SPDM/Caliptra 스펙 변환 전에 생성한 preflight 권고를 사용자가 안전하게 적용할 수 있는 workflow를 제공한다. 현재 preflight는 권고를 잘 반환하지만, 실제 CLI/MCP 변환 옵션 적용은 별도 수동 단계라 실수가 발생할 수 있다.

#### 범위

- CLI 또는 MCP에 plan file을 받아 conversion config로 변환하는 opt-in 경로를 추가한다.
- 적용 가능한 옵션은 `rag_profile`, `domain_adapter`, `image_mode`, `rag_sidecar_scope`, `page_workers`, timeout, window size로 제한한다.
- 적용 전/후 option matrix를 raw-content-free report에 기록한다.
- low/ambiguous domain adapter recommendation은 자동 적용하지 않는다.
- 기존 직접 옵션이 plan과 충돌하면 직접 옵션 우선 또는 fail-fast 중 하나로 명시 정책을 정한다.

#### 제외 범위

- 사용자의 명시적 동의 없는 자동 옵션 변경
- raw sample text 저장
- 외부 job scheduler나 cloud execution

#### 구현 단계

1. `pdf2md/preflight.py`의 `recommended_options`를 `Config`/MCP option으로 매핑하는 helper를 추가한다.
2. CLI에 `--apply-plan path` 또는 별도 script를 추가할지 결정한다.
3. MCP `pdf2md_convert_pdf`/windowed 경로에 plan 적용 option을 추가한다.
4. option conflict policy와 audit record를 report/manifest에 남긴다.
5. small/large/table-dense/security-domain recommendation fixture를 추가한다.

#### 검증 기준

- `python -m pytest tests/test_preflight.py tests/test_cli.py tests/test_mcp_server.py`
- ambiguous recommendation은 적용되지 않는다.
- explicit CLI option과 plan option 충돌 정책이 테스트로 고정된다.
- `git diff --check`

#### 성공 조건

- 사용자가 `plan -> apply` 경로로 대형 spec 변환을 재현 가능하게 실행할 수 있다.
- 적용된 권고와 생략된 권고가 report에서 식별 가능하다.

### Q147. Security Visual Sidecar Fixture Coverage

#### 목표

`technical_spec_rag_visual`의 visual sidecar 품질을 security spec 관점에서 검증한다. SPDM sequence diagram, TCG architecture diagram, Caliptra RoT/block diagram처럼 그림 자체가 검색/검증 단서인 문서에서 figure text/region OCR/description/structure sidecar 계약을 방어한다.

#### 범위

- security diagram fixture를 추가한다.
- `figures_rag.jsonl`, `figure_ocr_evidence_rag.jsonl`, `figure_descriptions_rag.jsonl`, `figure_structures_rag.jsonl`, `retrieval_chunks_rag.jsonl` linkage를 검증한다.
- generated description은 opt-in이고 sidecar-only라는 계약을 재검증한다.
- Markdown 본문에는 생성 설명을 넣지 않는다.

#### 제외 범위

- 외부 VLM/API 호출
- 생성 설명을 authoritative text로 취급
- 이미지 자체를 repo에 대량 추가

#### 구현 단계

1. 기존 figure semantics/visual sidecar tests와 schema validator를 확인한다.
2. `tests/fixtures/pdf_builder.py` 또는 작은 deterministic image fixture로 security diagram page를 만든다.
3. `technical_spec_rag_visual + domain_adapter=spdm|tcg|caliptra` smoke 변환 테스트를 추가한다.
4. visual sidecar validator가 security diagram fixture의 source linkage와 generated-text flags를 확인하도록 보강한다.
5. docs/OUTPUT_SCHEMA.md와 RAG recipe에 security visual fixture coverage를 기록한다.

#### 검증 기준

- `python -m pytest tests/test_rag_figures.py tests/test_visual_sidecar_contract.py tests/test_rag_chunks.py`
- generated figure description이 Markdown body에 들어가지 않는다.
- visual sidecar source refs와 retrieval chunk refs가 validator를 통과한다.
- `git diff --check`

#### 성공 조건

- security spec diagram이 text/table-only path보다 더 검색 가능한 visual evidence를 제공한다.
- generated/derived visual text와 observed/source text가 명확히 구분된다.

## 완료 명세 Archive

완료된 Q34-Q143 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
