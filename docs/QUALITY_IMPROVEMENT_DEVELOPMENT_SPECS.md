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

### P1 / Q65. GUI Runtime Doctor And Packaging Compatibility Smoke

#### 배경

현재 `check_gui_runtime()`은 Python version, Tkinter import, GUI module import, console script 확인에 집중한다. GUI 배포 호환성을 높이려면 Tcl/Tk 세부 정보, display/window 가능 여부, OCR/이미지 backend, help 문서 위치까지 구조화해 점검해야 한다.

#### 목표

- GUI runtime doctor가 Python/Tkinter뿐 아니라 Tcl/Tk patchlevel, display availability, optional OCR/Tesseract, Pillow/pypdfium2 import, help document path를 구조화해 보고한다.
- `scripts/run_gui_smoke_evidence.py`가 doctor 결과를 sanitized evidence에 포함한다.
- wheel/editable/source checkout에서 다른 진단 결과가 actionable하게 표시된다.
- 새 public JSON output schema는 만들지 않는다.

#### 구현 범위

- `pdf2md/gui_runner.py` 또는 새 helper module
  - `check_gui_runtime()`를 확장하거나 `check_gui_runtime_doctor()` 추가
  - `GuiDiagnostic`에 action/hint 성격의 정보를 추가할지 검토하되 backward compatibility 유지
  - window-only check는 CI에서 실패가 아니라 advisory/skip으로 기록
- `scripts/run_gui_smoke_evidence.py`
  - doctor 항목을 evidence에 포함
  - absolute path와 raw error payload를 redaction
- 문서
  - GUI guide, macOS quickstart, Windows guide에 doctor 결과 해석 방법 추가

#### 테스트 범위

- `tests/test_gui_runner.py`
  - missing Tkinter, missing optional backend, missing help path, display unavailable advisory 검증
- `tests/test_gui_smoke_evidence.py`
  - doctor evidence redaction과 pass/fail/advisory summary 검증
- `tests/test_docs_examples.py`

#### 비범위

- native bundle 생성
- code signing/notarization
- 실제 GUI screenshot regression
- Tesseract 자동 설치

### P2 / Q66. Sanitized GUI Support Bundle

#### 배경

GUI 사용자가 문제를 보고할 때 GUI log/summary나 evidence를 공유할 수 있다. support용 artifact는 원문 PDF 텍스트, 표/이미지 내용, warning message, local absolute path를 제거해야 한다.

#### 목표

- GUI summary, smoke evidence, runtime diagnostics를 기반으로 sanitized support bundle JSON/Markdown을 생성한다.
- bundle에는 status count, warning code/count, sanitized artifact labels, environment/runtime code만 포함한다.
- 원문 텍스트, 표 내용, 이미지 내용, warning message, home/workspace absolute path는 저장하지 않는다.
- public output schema가 아닌 local support artifact로 명확히 구분한다.

#### 구현 범위

- `pdf2md/gui_support.py` 또는 equivalent helper
  - redaction helper, support bundle model, writer 추가
  - `GuiConversionSummary`에서 sanitized support payload 생성
- optional script 또는 GUI-accessible helper
  - CLI/script smoke로 support bundle 생성 검증
  - GUI 버튼 노출은 필요성이 확인되면 후속으로 분리 가능
- 문서
  - GUI guide에 support bundle 공유 정책과 포함/금지 정보 명시

#### 테스트 범위

- `tests/test_gui_support.py`
  - absolute path redaction
  - raw warning message 미저장
  - artifact labels/count/code 중심 payload
- `tests/test_docs_examples.py`

#### 비범위

- public JSON schema 추가
- 원문 PDF/Markdown 첨부
- GitHub issue 자동 생성 또는 업로드

### P2 / Q67. GUI Expert Options And Profile Import/Export

#### 배경

`GuiConversionOptions`에는 `page_workers`, `debug`, `verbose`가 있지만 실제 GUI에는 노출되지 않는다. 반복 작업자는 preset보다 세밀한 실행 profile을 저장/불러오고 싶을 수 있다.

#### 목표

- GUI에 접이식 Expert options 영역을 추가해 `page_workers`, `debug`, `verbose` 등 기존 option 필드를 노출한다.
- local-only profile export/import를 제공하되 input/output path, password, PDF 원문 내용은 기본 저장하지 않는다.
- invalid profile은 구조화된 GUI diagnostic으로 표시한다.
- imported profile은 CLI `Config` option 의미와 일치한다.

#### 구현 범위

- `pdf2md/gui.py`
  - Expert options section 추가
  - page workers numeric input guardrail
  - debug/verbose checkbox 추가
- `pdf2md/gui_profiles.py` 또는 equivalent helper
  - profile schema version, load/save, validation, redaction policy
  - password/path 저장 금지 또는 explicit opt-in 제외
- 문서
  - GUI guide에 expert options와 local profile 정책 설명

#### 테스트 범위

- `tests/test_gui_profiles.py`
  - valid/invalid profile load
  - path/password/raw content 미저장
  - options mapping과 default compatibility
- `tests/test_gui_runner.py`
  - exposed expert options가 `Config`로 전달되는지 확인
- `tests/test_docs_examples.py`

#### 비범위

- cloud profile sync
- password 저장
- profile 기반 자동 preset 추천
- OCR language 자동 감지 또는 LLM 기반 preset 추천

## 완료 명세 Archive

완료된 Q34-Q64 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
