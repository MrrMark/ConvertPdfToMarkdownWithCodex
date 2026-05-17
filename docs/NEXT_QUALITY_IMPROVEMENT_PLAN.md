# Next Quality Improvement Plan

이 문서는 앞으로 작업할 항목만 관리하는 living backlog다.

## 운영 규칙

- 새로 착수할 작업이나 발견된 개선 과제는 구현 전에 이 문서에 추가한다.
- 작업이 완료되고 테스트 통과 및 PR merge까지 끝나면 해당 항목은 이 문서에서 제거한다.
- 완료 이력은 이 문서에 누적하지 않고 Git commit, PR, release note, changelog에서 추적한다.
- 이 문서에는 항상 아직 남은 다음 작업만 보여야 한다.
- active 개발 명세는 `docs/QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md`에 작성하고, 완료된 명세는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`로 이동한다.
- 새 작업 PR에는 가능하면 다음 중 하나를 포함한다.
  - 신규 작업 추가: 이 문서에 항목 추가
  - 기존 작업 완료: 이 문서에서 해당 항목 제거
  - 범위 변경: 항목 내용을 현재 결정사항 기준으로 갱신

## 기본 작업 플로우

1. 작업 시작 전 이 문서에서 해당 backlog 항목을 확인하거나 신규 항목을 추가한다.
2. 구현 PR에는 가능하면 코드 변경과 함께 이 문서의 항목 추가/삭제/범위 변경을 포함한다.
3. 구현 완료, 테스트 통과, PR merge까지 끝난 항목은 다음 작업 시작 전에 이 문서와 active 개발 명세에서 제거한다.
4. 구현 중 발견한 후속 과제는 완료 항목에 남기지 않고 새 Q 항목으로 분리한다.

## 남은 작업

### P1 / Q69. Wheel Contents And GUI Help Resource Contract

wheel/sdist 배포에서 GUI module, console script metadata, help document availability가 깨지지 않도록 package artifact 수준의 검증을 강화한다.

핵심 범위:

- 필요 시 `pdf2md/resources/` 또는 package data 정책 추가
- `gui_user_guide_path()` 또는 help path helper fallback 개선
- packaging gate가 CLI뿐 아니라 GUI entry point와 support/profile helper 포함 여부를 검증
- wheel content, console script metadata, GUI help resource contract test 추가

비범위는 PyPI upload, code signing/notarization, 외부 네트워크 dependency download 전제다.

### P2 / Q70. GUI Profile And Support Bundle Failure Fixture

실패/partial success 상황에서 support bundle과 profile import가 raw exception/warning/path를 누출하지 않는지 regression fixture를 강화한다.

핵심 범위:

- 실패/partial GUI summary fixture 추가
- support bundle이 retry candidate, warning code/count, status count만 저장하고 raw exception/warning message를 저장하지 않는지 검증
- invalid profile import가 구조화된 diagnostic만 표시하는지 headless contract 강화

비범위는 GUI modal click automation과 GitHub issue 자동 생성이다.

### P2 / Q71. Quality Scorecard Refresh And Next Backlog Reassessment

Q68-Q70 결과를 반영해 scorecard를 보수적으로 재평가하고, 다음 backlog를 비워둘지 변환 품질 중심 Q72+를 새로 열지 결정한다.

핵심 범위:

- `docs/QUALITY_SCORECARD.md` 보수적 재평가
- `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`와 `docs/QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md` 갱신
- `tests/test_docs_examples.py` 문서 계약 갱신
