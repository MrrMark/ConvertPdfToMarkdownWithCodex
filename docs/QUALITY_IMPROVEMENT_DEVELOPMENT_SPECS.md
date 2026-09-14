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

### 실행 조건

- 로컬 CPU를 기준으로 Mac과 Windows를 지원한다. GPU·클라우드 업로드는 필수 조건이 아니다.
- 검증된 수정은 기존 기본 동작에 반영한다. 파일명·기존 필드를 유지하고 메타데이터는 추가 방식으로 확장한다.
- 비교 도구는 별도 실험 환경에서 사용하며 제품 런타임 의존성으로 추가하지 않는다.
- 각 Q 작업의 회귀 검사를 먼저 작성하고, 변경 후 unit/integration/CLI/golden 검사를 실행한다.
- 기존 무결성 검사 통과를 원문 품질 통과로 해석하지 않는다.


### Q158. 한글 검색 평가 및 회귀 마감

기존 lexical smoke를 유지하고 Unicode 단어·기술 식별자·한글 문자 bigram 기반 로컬 BM25 기준선을 추가한다.

- 사람이 검토한 한글 15개·영어 15개 질문에 requirement/table/figure 원문 참조를 부여한다.
- Recall@5, MRR@5, citation 및 중요 토큰 보존을 평가한다. embedding/reranker/LLM 평가는 범위 밖이다.
- 로컬 Mac, Windows CPU CI, 기존 Linux CI를 검증한다.
- 전체 회귀와 release gate를 실행하고 원문 품질과 내부 무결성 결과를 각각 보고한다.

2026-09-14 BM25 및 별도 한·영 평가 CLI 구현. 질문 30개는 로컬 검토 초안이며 사람 검토 대기다.
2026-09-15 원문 렌더링 대조와 중요 토큰 검사 보완 완료. Mac Python 3.11/3.14 각 592개,
PR #142의 Windows Python 3.11 및 Linux Python 3.11/3.14 CI가 모두 통과했다.
2026-09-15 PR #142, merge commit `9e004e5`로 구현을 main에 반영했다.
사람 검토 승인과 승인된 정답 세트의 확정 기준선 재실행만 대기 중이다.
진행 결과와 잠정 지표는 [Q158 보고서](Q158_BILINGUAL_RETRIEVAL_EVALUATION.md)에 기록한다.

### Q159. Visual sidecar 참조 계약 검증

Q153 실측 중 이전 버전부터 존재하던 visual 계약 오류를 발견했다. front matter 462건, controller 22건이며 수정 전후 finding 목록은 동일하다.

- 실제 source reference의 `figure`/`excluded_figure` 타입과 ID를 확인하고 생산자·검증기 중 어느 계약이 잘못됐는지 재현 fixture로 구분한다.
- description/OCR evidence/structure의 정당한 참조를 수용하되 실제 누락·잘못된 target ID 검출은 유지한다.
- 실제 레코드 삭제나 검사 생략으로 오류를 숨기지 않는다.
- 합성 정상/실패 회귀 검사와 기존 실제 두 사례의 오류 해소를 완료 기준으로 삼는다. Q153에서는 수정하지 않는다.

## 완료 명세 Archive

완료된 Q34-Q157 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
