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

## P1 / Q69. Wheel Contents And GUI Help Resource Contract

### 배경

GUI Help는 source checkout의 `docs/GUI_USER_GUIDE.md`를 기준으로 동작한다. wheel/sdist 배포에서는 docs 파일 포함 여부와 console script metadata가 깨질 수 있으므로 package artifact 수준의 검증이 필요하다.

### 목표

- wheel build 결과에 GUI 관련 module/script metadata가 포함되는지 검사한다.
- wheel 또는 package resource 경로에서도 GUI help document availability가 명확히 진단되도록 한다.
- packaging gate가 CLI뿐 아니라 GUI entry point와 support/profile helper 포함 여부를 검증한다.

### 구현 범위

- 필요 시 `pdf2md/resources/` 또는 package data 정책 추가
- `gui_user_guide_path()` 또는 help path helper fallback 개선
- wheel zip content inspection helper/script 추가 또는 packaging gate 확장
- tests에서 wheel content, console script metadata, GUI help resource contract 검증

### 검증

- `.venv311/bin/python -m pytest tests/test_gui_runner.py tests/test_quality_gate_scripts.py`
- `.venv311/bin/python scripts/run_release_gates.py --output-dir /private/tmp/pdf2md-q69-packaging --gates packaging`
- `python3 -m pdf2md.gui --doctor --doctor-format json`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- PyPI upload
- code signing/notarization
- 외부 네트워크 dependency download 전제

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

완료된 Q34-Q68 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
