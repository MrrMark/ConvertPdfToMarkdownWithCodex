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

### P1 / Q60. GUI Practical UX And Distribution Hardening

Q53-Q59로 최소 GUI wrapper, runtime diagnostics, 결과 검토 표, batch controls, 비개발자 문서, Help 진입점, headless contract test가 들어갔다. 다음 단계는 실제 로컬 GUI 사용 흐름에서 남는 마찰을 줄이고, 비개발자 배포 방식을 보수적으로 결정할 수 있는 실행/검증 계획을 확정하는 것이다.

#### 목표

- 실제 GUI를 로컬에서 실행해 단일 PDF와 폴더 배치 변환 흐름을 점검한다.
- 사용자가 변환 완료 후 결과 파일을 더 쉽게 확인할 수 있게 한다.
- 최근 입력/출력 경로를 local-only 상태로 저장해 반복 사용성을 높인다.
- ZIP + venv script, 기존 setup script, PyInstaller/native bundle 후보를 비교하고, 현재 릴리스에 적합한 배포 경로를 문서화한다.
- GUI 편의 기능이 CLI `Config` / `run_conversion` / output schema 계약을 바꾸지 않도록 테스트로 고정한다.

#### 우선 구현 후보

1. GUI 진행 상태 개선
   - 단일 변환은 indeterminate progress와 현재 status label을 표시한다.
   - 폴더 배치 변환은 현재 문서 index/total 기반 progressbar를 표시한다.
   - core pipeline이 page-level progress를 제공하지 않는 동안 page 단위 진행률처럼 보이는 값은 만들지 않는다.
2. 결과 파일 열기 개선
   - 선택한 결과 행의 Markdown, `report.json`, `manifest.json`, assets/output folder를 열 수 있게 한다.
   - 열기 실패는 변환 실패로 바꾸지 않고 GUI warning/log로만 남긴다.
3. 최근 경로 저장
   - 최근 input file/folder와 output folder를 local-only JSON 상태로 저장한다.
   - raw PDF 내용, 원문 텍스트, 표, 이미지, warning message는 저장하지 않는다.
   - 경로 노출을 사용자가 정리할 수 있도록 clear recent 동작을 제공한다.
4. 비개발자 배포 방식 결정
   - 단기 기본 배포는 source/ZIP + venv setup script + `python -m pdf2md.gui` 경로를 우선한다.
   - PyInstaller/native bundle은 별도 feasibility smoke를 통과하기 전까지 공식 기본 경로로 승격하지 않는다.
   - macOS/Windows guide에는 선택지별 장단점과 추천 경로를 명시한다.

#### 완료 기준

- GUI local smoke checklist가 문서화되고, 가능한 범위에서 실제 로컬 실행 결과가 반영된다.
- 최근 경로 저장/복구/손상 파일 fallback/clear recent 동작이 unit test로 고정된다.
- 결과 파일 열기 target 결정과 open failure handling이 테스트 가능한 helper 또는 GUI method 수준에서 검증된다.
- GUI progress 상태가 batch progress callback과 일관되며 headless test에서 깨지지 않는다.
- README, `docs/GUI_USER_GUIDE.md`, `docs/MACOS_GUI_QUICKSTART.md`, `docs/WINDOWS_A_TO_Z_GUIDE.md`가 Q60 UX와 배포 결정을 설명한다.
- 새 public JSON output schema는 만들지 않는다.

#### 비범위

- 변환 엔진 변경
- PDF/Markdown 미리보기 또는 편집기
- 실행 중인 단일 PDF 변환의 강제 kill/cancel
- native installer, code signing, notarization, auto-update
- 외부 RAG/indexing 서비스 호출
