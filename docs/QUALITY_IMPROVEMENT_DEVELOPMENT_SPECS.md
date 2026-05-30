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

### P0 / Q90. Cross Reference Target Index Expansion

#### 배경

최신 NVMe Base Specification 2.3 전체 PDF를 `rag_optimized`와 `technical_spec_rag --domain-adapter nvme`로 재평가한 결과, 두 프리셋 모두 변환/validator/preset gate는 통과했지만 `cross_ref_resolved_coverage`가 약 69.5%에 머물렀다.

관찰한 미해결 1,160건의 주된 분포는 다음과 같다.

| 유형 | 미해결 건수 | 판단 |
|---|---:|---|
| section | 866 | PDF outline에는 target이 있으나 `text_blocks_rag.jsonl` heading target index에 누락된 경우가 대부분 |
| register | 198 | `register`/`capability`가 일반 prose로 쓰인 문장을 technical cross-ref로 과대 기록 |
| figure | 94 | List of Figures에는 target이 있으나 본문 caption target이 누락되거나 라벨이 붙어서 추출됨 |
| appendix/table | 2 | 외부 RFC appendix 또는 PCI/MSI-X 용어성 table label로 local target이 아님 |

#### 목표

`cross_refs_rag.jsonl`의 resolved coverage를 높이되, 원문 텍스트를 바꾸거나 환각성 target을 만들지 않는다. target source와 confidence/reason을 명시해 downstream RAG/indexer가 outline/list fallback과 본문 heading/caption target을 구분할 수 있게 한다.

#### 구현 범위

1. PDF outline/bookmark section fallback
   - PDF outline에서 numeric section label, title, page를 추출해 deterministic target map을 만든다.
   - 기존 extracted heading target을 우선하고, 누락된 label에만 outline fallback을 병합한다.
   - fallback target은 `target_source` 또는 classification reason으로 `pdf_outline`임을 드러낸다.

2. Figure/Table list fallback
   - `Figure N: ... .... page` 형태의 List of Figures 항목을 figure target fallback으로 인식한다.
   - 필요하면 Table list도 같은 구조로 확장하되, 실제 table number label과 용어성 `Table BIR` 같은 문구를 구분한다.
   - 본문 caption target이 있으면 기존 target을 유지한다.

3. Reference label normalization
   - `Figure 23Figure 23`처럼 PDF text extraction에서 붙은 라벨을 `Figure 23`으로 정규화한다.
   - `sections 3.6.1 and 3.6.2` 같은 복수 section reference를 개별 target으로 분리한다.
   - label boundary를 강화해 `Figure 551determines` 같은 붙은 prose를 unresolved record로 남기지 않는다.

4. Register/capability false-positive suppression
   - `register shall be cleared`, `Register command`, `Register is supported`처럼 일반 단어로 쓰인 문장은 cross-ref 후보에서 제외한다.
   - `CAP.NSSRS`, `CC.EN`, `CSTS.RDY`, `CMD.PEE`처럼 명확한 identifier shape가 있거나 실제 register target map이 있을 때만 record를 만든다.
   - suppression은 warning이 아니라 quality-preserving filtering으로 처리한다.

5. External/local target guard
   - `RFC 9562 Appendix B`처럼 외부 문서 참조는 local unresolved cross-ref로 남기지 않는다.
   - PCI/MSI-X `Table BIR`처럼 table 번호가 아닌 약어/용어 label은 local table target 후보에서 제외한다.

#### 비범위

- 외부 RAG/indexing service 호출은 하지 않는다.
- PDF 원문 문장, Markdown 본문, 표/이미지 추출 정책은 바꾸지 않는다.
- outline/list fallback을 이용해 원문에 없는 section/figure 설명을 생성하지 않는다.
- 모든 unresolved를 0으로 만드는 것이 목표가 아니다. 애매한 참조는 skip하거나 unresolved reason을 보존한다.

#### 코드 변경 후보

- `pdf2md/serializers/rag_semantics.py`
  - reference target map builder 확장
  - reference pattern/normalization/skip guard 보강
  - cross-ref reason/source metadata 보강
- `pdf2md/pipeline.py` 또는 인접 모델/serializer 경계
  - PDF outline metadata를 semantic layer builder에 전달하는 최소 계약 추가
- `pdf2md/models.py` 또는 report/manifest schema
  - 새 public field가 생기는 경우에만 schema/docs 갱신
- `tests/test_rag_semantics.py`
  - unit-level resolver/guardrail tests
- `tests/fixtures/pdf_builder.py`, `tests/test_golden_corpus.py`
  - 필요한 경우 synthetic outline/figure-list fixture 추가

#### 검증 계획

- `python3 -m pytest tests/test_rag_semantics.py`
- `python3 -m pytest tests/test_golden_corpus.py`
- `python3 -m pytest tests/test_docs_examples.py`
- `python3 -m pytest`
- `python3 scripts/export_output_schema.py --check`
- `git diff --check`
- `git diff --cached --check`

실제 corpus 검증은 로컬 전용으로 수행한다.

```bash
.venv311/bin/python scripts/run_preset_eval.py \
  --input-pdf /private/tmp/NVM-Express-Base-Specification-Revision-2.3-2025.08.01-Ratified.pdf \
  --output-root /private/tmp/pdf2md-q90-nvme-base-preset-eval \
  --presets rag_optimized,technical_spec_rag \
  --domain-adapter nvme
```

#### 성공 기준

- 최신 NVMe Base Specification 2.3 기준 `cross_ref_resolved_coverage >= 0.90`을 통과한다.
- outline/list fallback과 오탐 suppression을 함께 적용한 경우 0.94 이상을 목표로 한다.
- `actionable_warning_count=0`, validator error/warning 0 상태를 유지한다.
- `document.md`는 두 프리셋 간 동일성을 유지하고, 본문 원문 보존 정책을 깨지 않는다.

## 완료 명세 Archive

완료된 Q34-Q89 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
