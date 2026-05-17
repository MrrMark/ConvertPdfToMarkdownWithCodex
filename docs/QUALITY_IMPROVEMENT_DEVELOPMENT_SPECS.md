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

## P2 / Q70. GUI Profile And Support Bundle Failure Fixture

### 배경

Q66/Q67은 정상/구조 검증 중심이다. 실제 실패/partial success 상황에서 support bundle과 profile이 raw message/path를 누출하지 않는지 더 강한 regression fixture가 필요하다.

### 목표

- 실패/partial GUI summary fixture를 추가한다.
- support bundle이 retry candidate, warning code/count, status count만 저장하고 raw exception/warning message를 저장하지 않는지 검증한다.
- invalid profile import가 구조화된 diagnostic만 표시하는지 headless contract를 강화한다.

### 구현 범위

- `tests/test_gui_support.py`
- `tests/test_gui_profiles.py`
- 필요 시 `pdf2md/gui_support.py`, `pdf2md/gui_profiles.py` 소폭 보강

### 검증

- `.venv311/bin/python -m pytest tests/test_gui_support.py tests/test_gui_profiles.py`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- GUI modal click automation
- GitHub issue 자동 생성

## P2 / Q71. Quality Scorecard Refresh And Next Backlog Reassessment

### 배경

Q53-Q67까지 GUI 사용성/호환성 작업이 누적되었고 현재 점수는 97/100으로 유지된다. 다음 개선이 실제 변환 품질인지, 릴리스/배포 신뢰도인지 다시 분리할 필요가 있다.

### 목표

- Q68-Q70 결과를 반영해 scorecard를 보수적으로 재평가한다.
- 97/100 유지 또는 점수 변화 근거를 명확히 기록한다.
- 다음 active backlog를 비워둘지, 변환 품질 중심 Q72+를 새로 열지 결정한다.

### 구현 범위

- `docs/QUALITY_SCORECARD.md`
- `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`
- `docs/QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md`
- `tests/test_docs_examples.py`

### 검증

- `.venv311/bin/python -m pytest tests/test_docs_examples.py`
- `.venv311/bin/python -m pytest`
- `git diff --check`

## 완료 명세 Archive

완료된 Q34-Q69 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
