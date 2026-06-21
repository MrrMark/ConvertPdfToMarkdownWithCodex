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

완료된 Q34-Q146 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
