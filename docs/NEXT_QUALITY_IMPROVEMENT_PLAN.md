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

### P1 / Q96. Korean, OCR, And Image-Only Golden Promotion

목표: PRD fixture 우선순위에 맞춰 한글, image-only/OCR, 스캔성 문서 케이스를 단순 builder 존재 여부가 아니라 golden regression 대상으로 승격한다.

범위:

- `korean`, `image_only`, OCR warning/actionable fixture를 golden comparison에 포함할지 평가한다.
- OCR runtime 의존 테스트와 deterministic mock-based golden을 분리한다.
- 한글 원문 보존, OCR 무교정, image-only partial success/report warning 정책을 고정한다.
- 필요 시 fixture 이름과 golden output 구조를 public schema와 맞춘다.

검증:

- golden corpus tests
- OCR unit tests
- Markdown/report/manifest normalized diff
- `scripts/check_ocr_runtime.py --ocr-lang kor+eng`는 runtime smoke로만 분리

### P2 / Q97. Modern Python Tooling And Packaging Readiness

목표: Python 3.11+ 프로젝트 표준에 맞춰 lint/type/package/audit 기반을 단계적으로 도입하되, core conversion 품질 변경과 분리한다.

범위:

- `ruff` check/format 정책을 pyproject에 추가한다.
- type check 도입 범위와 strictness를 단계적으로 정의한다.
- `py.typed`, license/changelog/release note, wheel/sdist smoke 후보를 정리한다.
- dependency audit은 advisory gate로 시작한다.

검증:

- lint command smoke
- package build smoke
- wheel contract smoke
- 문서 예시와 CI command 동기화

새 개선 과제가 발견되면 이 섹션에 신규 Q 항목을 추가하고, 구현 전 `docs/QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md`에 대응 active 개발 명세를 작성한다.
