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

Q53 Minimal Desktop GUI Wrapper 이후 후속 작업은 GUI가 기존 CLI 변환 계약을 바꾸지 않으면서 비개발자/간편 실행 사용자에게 안정적으로 동작하도록 만드는 범위로 제한한다. 우선순위는 운영 리스크, 사용자 영향, 결정성 회귀 가능성 순서로 둔다.

| Q | 우선순위 | 작업 | 목표 |
|---|---|---|---|
| Q54 | P1 | GUI Runtime And Install Diagnostics | Tkinter/runtime/entry point/경로 권한 문제를 변환 실패와 구분해 사용자가 조치 가능한 메시지로 확인하게 한다. |
| Q55 | P1 | GUI Conversion Result Review UX | GUI 완료 화면에서 `report.json`, `manifest.json`, partial success warning, 산출물 경로를 요약해 품질 확인 진입 비용을 낮춘다. |
| Q56 | P1 | GUI Batch Operation Controls | 폴더 배치 변환에서 취소, 진행률, 실패 문서 재시도 후보, skip summary를 deterministic local summary로 남긴다. |
| Q57 | P2 | Non-Developer GUI Distribution Guide | 비개발자가 설치/실행/샘플 변환/문제 진단까지 따라갈 수 있는 GUI 중심 배포 문서를 정리한다. |
| Q58 | P2 | GUI Smoke And Contract Test Expansion | GUI wrapper가 CLI `Config`/산출물 계약을 계속 따르는지 headless smoke와 문서 계약 테스트로 고정한다. |

### Q54. GUI Runtime And Install Diagnostics

- Tkinter import/launch 실패, Python 버전 불일치, entry point 누락, output path 권한 문제를 변환 실패와 분리해 진단한다.
- GUI 실행 전 사전 점검 결과를 structured diagnostic object 또는 log summary로 제공한다.
- CLI 자동화 경로에는 영향을 주지 않고, `python -m pdf2md.gui --help`는 계속 창을 띄우지 않아야 한다.

### Q55. GUI Conversion Result Review UX

- 단일/배치 변환 완료 후 success, partial_success, failed, skipped counts와 핵심 warning을 화면에서 확인할 수 있게 한다.
- `report.json`/`manifest.json` 위치, output folder, 생성된 Markdown 경로를 명확히 보여준다.
- 원문 텍스트, 표, 이미지 산출물 자체를 요약/재서술하지 않고 report에 기록된 구조화 정보만 표시한다.

### Q56. GUI Batch Operation Controls

- 폴더 배치 변환 중 취소 요청을 안전하게 처리하고, 완료/취소/실패 상태를 문서 단위로 구분한다.
- skip-existing 결과와 실패 문서 재시도 후보를 local-only summary로 남긴다.
- 같은 입력과 옵션에서는 동일한 summary ordering과 상태 값이 나오도록 한다.

### Q57. Non-Developer GUI Distribution Guide

- Windows/macOS 사용자가 CLI 지식 없이 GUI를 실행하는 절차를 문서화한다.
- 설치형 배포가 아니라도 venv, editable install, `pdf2md-gui`, `python -m pdf2md.gui` 흐름을 명확히 안내한다.
- OCR runtime, Python/Tkinter, 파일 권한, output folder 문제의 초기 점검 절차를 포함한다.

### Q58. GUI Smoke And Contract Test Expansion

- GUI runner 옵션 매핑, batch naming, skip-existing, diagnostics, result summary를 headless 테스트로 고정한다.
- 새 public JSON 출력이 생기는 경우 `docs/OUTPUT_SCHEMA.md`와 `docs/schema/`를 함께 갱신한다.
- GUI 테스트는 실제 창 의존도를 최소화하고 CI Python 3.11/3.14에서 deterministic하게 통과해야 한다.
