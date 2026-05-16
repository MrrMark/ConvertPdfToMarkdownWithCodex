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

### P1 / Q62. GUI Smoke Evidence And Layout Guardrails

Q61로 기본 한글 UI, English 선택, 목적 기반 preset, batch percent 표시가 들어갔다. 다음 단계는 이 GUI 변화가 실제 로컬 환경에서 반복 확인 가능하도록 smoke evidence 절차를 만들고, 긴 한글/영문 label과 preset 상태가 화면에서 깨지지 않도록 레이아웃/상태 guardrail을 보강하는 것이다.

#### 목표

- Q61 GUI 기능을 로컬에서 재현 가능한 smoke checklist와 evidence 파일로 검증한다.
- smoke evidence에는 Python/Tkinter runtime, GUI help smoke, preset별 runner smoke, manual GUI 확인 항목을 기록하되 PDF 원문/표/이미지 내용은 저장하지 않는다.
- 한글/영문 label, preset selector, option lock/unlock 상태가 누락 없이 UI에 연결되는지 headless guardrail로 고정한다.
- 실제 Tk window 또는 OS UI automation이 없는 CI에서도 의미 있는 검증을 유지하고, 수동 GUI smoke는 로컬 전용 절차로 분리한다.
- core `run_conversion`, CLI option 의미, output schema 계약은 변경하지 않는다.

#### 우선 구현 후보

1. Local GUI smoke evidence runner
   - `scripts/run_gui_smoke_evidence.py` 또는 동등한 local-only script를 추가한다.
   - `check_gui_runtime()`, `python -m pdf2md.gui --help`, single/batch `run_gui_conversion()` smoke를 한 번에 수행한다.
   - evidence JSON에는 pass/fail, runtime diagnostics, command 결과, preset/language 상태, 산출물 존재 여부만 남긴다.
   - workspace/home 경로와 원문 PDF 내용은 redaction 또는 상대 label로 처리한다.
2. GUI layout/state guardrails
   - i18n catalog key coverage와 English fallback을 강화한다.
   - GUI에서 text tracking 대상 label/button/heading이 누락되지 않도록 headless test 가능한 helper를 둔다.
   - preset별 option lock/unlock 상태와 `pages/password/OCR lang` 보존 정책을 GUI state 수준에서 검증한다.
   - 실제 Tk window 검증이 가능한 환경에서는 optional manual smoke를 실행하고, 불가능하면 명시적으로 skip 사유를 남긴다.
3. Manual smoke checklist refinement
   - macOS/Windows/GUI guide에 Q61 이후 확인 항목을 통합한다.
   - 한국어 기본 UI, English 전환, preset lock/unlock, batch percent, single 완료 `100%`, local-only state 복구/clear를 체크리스트로 고정한다.
   - evidence 파일을 공유할 때 포함하면 안 되는 정보와 포함해도 되는 정보를 구분한다.

#### 완료 기준

- local smoke evidence runner가 CI/headless friendly mode에서 테스트된다.
- evidence JSON이 원문 텍스트, 표, 이미지 내용, warning message를 저장하지 않는다는 test가 있다.
- language/preset/progress/status UI guardrail test가 Q61 regression을 방어한다.
- README, `docs/GUI_USER_GUIDE.md`, `docs/MACOS_GUI_QUICKSTART.md`, `docs/WINDOWS_A_TO_Z_GUIDE.md`가 smoke evidence 생성과 수동 확인 절차를 설명한다.
- 실패 시 조치 가능한 메시지와 exit code를 제공한다.
- 새 public JSON output schema는 만들지 않는다.

#### 비범위

- OS-level 자동 클릭, screenshot visual regression, Computer Use 기반 CI 자동화
- native installer, code signing, notarization, auto-update
- core pipeline page-level progress callback 구현
- PDF/Markdown preview 또는 editor
- OCR 언어 자동 감지 또는 LLM 기반 preset 추천
- public output schema 추가
