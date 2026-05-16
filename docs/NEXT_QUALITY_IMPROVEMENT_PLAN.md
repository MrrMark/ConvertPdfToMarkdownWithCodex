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

### P1 / Q64. Responsive GUI Layout And Accessibility Guardrails

Q62로 headless smoke evidence는 확보됐다. 다음 단계는 실제 Tk window가 작은 화면, Windows display scaling, 긴 한국어/영문 label에서도 깨지지 않도록 레이아웃을 더 유연하게 만들고 접근성 기본값을 보강하는 것이다.

#### 목표

- GUI main area를 scrollable/responsive 구조로 바꿔 작은 화면에서도 주요 control에 접근할 수 있게 한다.
- preset, action button, result action 영역이 긴 label에서 잘리지 않도록 wrapping 또는 grid 재배치를 적용한다.
- headless 수준에서 layout metadata, text tracking, minimum size contract를 검증한다.
- core conversion, output schema, warning code는 변경하지 않는다.

#### 완료 기준

- 한국어/영문 label과 주요 button/action key가 layout metadata에 연결된다.
- 작은 window height에서도 scrollable container로 options/results/log 영역에 접근 가능하다.
- `tests/test_gui_layout.py` 또는 동등한 headless guardrail이 추가된다.
- README, GUI guide, macOS/Windows guide에 responsive layout 확인 항목이 반영된다.

### P1 / Q65. GUI Runtime Doctor And Packaging Compatibility Smoke

현재 runtime check는 Python/Tkinter/module/entry point 중심이다. 배포 호환성을 높이려면 GUI 실행 전후에 필요한 runtime과 packaging 환경을 더 구체적으로 진단해야 한다.

#### 목표

- `check_gui_runtime()` 또는 별도 doctor helper가 Tcl/Tk patchlevel, display/window availability, optional OCR/Tesseract, Pillow/pypdfium2 import, help document path를 구조화해 보고한다.
- `scripts/run_gui_smoke_evidence.py`가 doctor 결과를 sanitized evidence에 포함한다.
- packaging smoke checklist에 wheel/editable/source checkout 차이를 기록한다.
- 새 public output schema는 만들지 않는다.

#### 완료 기준

- runtime doctor 결과가 code/severity/message/action 형태로 테스트된다.
- Tk window를 띄울 수 없는 CI에서도 headless 가능한 항목은 검증하고 window-only 항목은 명시적으로 advisory 처리한다.
- macOS/Windows guide에 doctor 명령과 해석 방법이 추가된다.

### P2 / Q66. Sanitized GUI Support Bundle

GUI 사용자가 문제를 보고할 때 현재 GUI log/summary에는 local path가 들어갈 수 있다. 지원용 공유 artifact는 원문 PDF 내용, 표/이미지 내용, warning message, absolute path를 제거한 sanitized bundle이어야 한다.

#### 목표

- GUI summary, smoke evidence, runtime diagnostics를 기반으로 support bundle JSON/Markdown을 생성하는 helper 또는 script를 추가한다.
- bundle에는 status count, warning code/count, sanitized artifact labels, environment/runtime code만 포함한다.
- 원문 텍스트, 표 내용, 이미지 내용, warning message, home/workspace absolute path는 저장하지 않는다.

#### 완료 기준

- redaction helper와 support bundle writer 테스트가 추가된다.
- GUI guide에 support bundle 공유 정책이 문서화된다.
- public output schema가 아닌 local support artifact로 명확히 구분된다.

### P2 / Q67. GUI Expert Options And Profile Import/Export

GUI에는 아직 `page_workers`, `debug`, `verbose` 같은 expert option 입력이 없다. 반복 작업자는 preset을 넘어서 실행 profile을 저장/불러오고 싶어 한다.

#### 목표

- GUI에 접이식 Expert options 영역을 추가해 `page_workers`, `debug`, `verbose` 등 기존 `GuiConversionOptions` 필드를 노출한다.
- local-only profile export/import를 제공하되 input/output path, password, PDF 원문 내용은 기본 저장하지 않는다.
- imported profile은 `Config` 계약과 동일한 option 의미를 유지한다.

#### 완료 기준

- profile JSON은 local-only artifact이며 public output schema로 취급하지 않는다.
- invalid profile은 구조화된 GUI diagnostic으로 표시된다.
- tests가 option mapping, redaction, backward-compatible default를 검증한다.
