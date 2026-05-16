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

### P1 / Q62. GUI Smoke Evidence And Layout Guardrails

#### 배경

Q61로 GUI 기본 한글 UI, English 선택, 목적 기반 preset, progress percent 표시가 구현됐다. 이 변화는 사용자 눈에 바로 보이는 기능이므로 다음 단계에서는 실제 로컬 실행 흐름을 반복 가능한 smoke evidence로 남기고, 긴 한글/영문 label과 preset 상태가 화면/상태 계층에서 누락되지 않도록 guardrail을 세운다.

이 작업은 GUI 배포 전 confidence를 높이는 운영성 개선이다. core 변환 엔진, Markdown/manifest/report 산출물, public schema, warning code는 그대로 유지한다.

#### 목표

- Q61 GUI 기능을 검증하는 local-only smoke evidence runner를 제공한다.
- GUI runtime, module help, preset별 runner smoke, manual 확인 항목을 하나의 evidence JSON으로 기록한다.
- evidence에는 원문 PDF 텍스트, 표 내용, 이미지 내용, warning message를 저장하지 않는다.
- 한글/영문 label catalog와 GUI text tracking, preset lock/unlock 상태를 headless test로 방어한다.
- 실제 Tk window 검증은 로컬 수동 smoke로 유지하고, CI에서는 창 없이 실행 가능한 검증만 수행한다.

#### 구현 범위

- `scripts/run_gui_smoke_evidence.py` 또는 동등한 script
  - `--output-dir`, `--state-path`, `--json-only` 같은 local smoke 실행 옵션을 제공한다.
  - `check_gui_runtime()` 결과를 포함한다.
  - `python -m pdf2md.gui --help`가 창 없이 성공하는지 확인한다.
  - synthetic/sample fixture를 이용해 single conversion과 folder batch conversion을 runner 경로로 실행한다.
  - `preserve`, `rag_optimized`, `custom` preset을 최소 한 번 이상 `GuiConversionOptions`로 적용해 runner smoke에 반영한다.
  - evidence JSON에는 absolute path 대신 redacted label 또는 relative label을 저장한다.
  - 실패 시 non-zero exit code와 조치 가능한 summary를 출력한다.
- GUI guardrail helper/test
  - `pdf2md/gui_i18n.py` catalog key coverage를 검증한다.
  - GUI에서 추적해야 하는 label/button/heading key 목록을 helper로 노출하거나 테스트 가능하게 정리한다.
  - preset 선택 시 editable/readonly 대상이 기대와 일치하는지 headless 수준에서 검증한다.
  - Q61 state schema v2가 smoke 전용 isolated state path에서 오염 없이 작동하는지 확인한다.
- 문서
  - README, GUI user guide, macOS quickstart, Windows guide에 smoke evidence runner와 수동 확인 절차를 추가한다.
  - evidence에 포함 가능한 정보와 포함 금지 정보를 명확히 한다.
  - 실제 GUI window 수동 smoke와 CI/headless smoke의 차이를 설명한다.

#### 테스트 범위

- `tests/test_gui_smoke_evidence.py`
  - evidence writer가 원문 텍스트/표/이미지/warning message를 저장하지 않음
  - redaction helper가 workspace/home absolute path를 제거
  - success/failure summary와 exit code contract
- `tests/test_gui_i18n.py`, `tests/test_gui_presets.py`, `tests/test_gui_state.py`
  - catalog key coverage 확장
  - preset lock/unlock 및 state isolation contract
- `tests/test_gui_runner.py`
  - smoke runner가 사용하는 single/batch conversion path가 CLI `Config` 계약과 일치
- `tests/test_docs_examples.py`
  - smoke evidence runner, 수동 GUI checklist, redaction policy 문서 고정

#### Smoke 정책

- smoke evidence는 local-only artifact다. repository에 fixture raw output이나 사용자 PDF 내용을 커밋하지 않는다.
- evidence에는 command 결과, runtime availability, sanitized artifact labels, status counts만 남긴다.
- 실제 GUI window 확인은 사람이 수행하는 checklist로 남긴다. CI에서 OS-level click automation을 요구하지 않는다.
- runner smoke는 GUI orchestration이 CLI conversion contract를 깨지 않는지 확인하는 보조 검증이다.

#### 로컬 GUI smoke checklist

1. smoke evidence runner를 isolated output/state path로 실행한다.
2. `python -m pdf2md.gui --help` 결과가 evidence에 기록됐는지 확인한다.
3. GUI를 실제로 실행해 기본 한국어 UI를 확인한다.
4. language selector를 English로 바꿨을 때 주요 label/button/status가 바뀌는지 확인한다.
5. `기본 모드(원본 유지)`, `RAG 등록용(최적화)`, `Optimize Options(유저 선택)`에서 세부 옵션 잠금/해제가 맞는지 확인한다.
6. 단일 PDF 변환 완료 시 `100%`가 표시되는지 확인한다.
7. 폴더 배치 변환에서 `current/total (percent%)` 표시가 progressbar와 일치하는지 확인한다.
8. GUI 재시작 후 language/preset/recent path가 복구되고, `Clear recent` 후 경로가 사라지는지 확인한다.
9. evidence JSON에 raw PDF text/table/image/warning message가 없는지 확인한다.

#### 비범위

- OS-level 자동 클릭 또는 screenshot visual regression을 CI 필수로 만드는 것
- Computer Use 기반 자동 GUI 클릭을 release gate로 편입
- native installer/package 생성
- core pipeline page-level progress callback
- PDF/Markdown preview/editor
- OCR language 자동 선택 또는 LLM 기반 preset 추천

## 완료 명세 Archive

완료된 Q34-Q61 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
