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

### P1 / Q60. GUI Practical UX And Distribution Hardening

#### 배경

Q53-Q59까지의 GUI 작업은 최소 Tkinter wrapper, runtime/install diagnostics, 완료 결과 표, batch cancel/retry summary, 비개발자 가이드, Help 버튼, headless contract test를 제공했다. 현재 GUI는 core 변환 품질과 output schema를 바꾸지 않는 얇은 wrapper라는 원칙을 잘 지키고 있다.

다음 고도화는 변환 엔진 확장이 아니라 실사용 마찰 제거다. 실제 로컬 GUI 실행에서 반복될 가능성이 높은 문제는 진행 상태 가시성, 변환 결과 파일 접근, 반복 사용 시 경로 재입력, 그리고 비개발자 배포 경로 선택이다.

#### 목표

- 실제 GUI local smoke 흐름을 점검하고 문서화한다.
- 진행률/상태 표시를 현재 runner callback 수준에 맞게 개선한다.
- 완료 결과 행에서 Markdown, report, manifest, assets/output folder를 바로 열 수 있게 한다.
- 최근 입력/출력 경로를 local-only 상태로 저장/복구한다.
- ZIP + venv script, setup script, PyInstaller/native bundle 후보를 비교해 현재 권장 배포 방식을 명확히 한다.
- GUI 편의 기능이 CLI 산출물 계약과 public schema를 변경하지 않도록 테스트를 추가한다.

#### 구현 범위

- `pdf2md/gui_state.py` 또는 동등한 순수 helper
  - 최근 input file, input folder, output folder를 저장하는 local-only state helper를 추가한다.
  - 기본 저장 위치는 사용자 홈 아래의 앱 전용 경로를 사용하고, 테스트에서는 path injection으로 임시 디렉터리를 사용한다.
  - 저장 항목은 경로와 timestamp/order 정도로 제한한다.
  - 손상된 JSON, 누락된 파일, 이전 schema version은 GUI 시작 실패가 아니라 empty state fallback으로 처리한다.
  - clear recent 동작을 제공한다.
- `pdf2md/gui.py`
  - status label과 progressbar를 추가한다.
  - 단일 변환은 indeterminate progress로 표시한다.
  - 폴더 배치 변환은 `GuiBatchProgress.current / total`을 기준으로 determinate progress를 표시한다.
  - 결과 표 선택 행 기준으로 Markdown, report, manifest, assets/output folder 열기 버튼 또는 메뉴를 제공한다.
  - 파일 열기 실패는 messagebox/log warning으로만 표시하고 conversion summary/status는 변경하지 않는다.
  - GUI 시작 시 최근 경로를 input/output field에 보수적으로 복구하고, Browse/Start 성공 시 최근 경로를 갱신한다.
- `pdf2md/gui_runner.py`
  - 가능한 한 기존 `GuiBatchProgress`, `GuiConversionSummary`, `GuiDocumentSummary` 계약을 유지한다.
  - 새 GUI 표시가 필요하면 source text나 table/image content가 아닌 path/status 중심 metadata만 추가한다.
  - page-level progress callback이 없는 상태에서 임의 page progress를 만들지 않는다.
- 배포/문서
  - `docs/GUI_USER_GUIDE.md`: 최근 경로, 결과 파일 열기, progress 의미, clear recent, troubleshooting을 추가한다.
  - `docs/MACOS_GUI_QUICKSTART.md`: source/ZIP + venv 실행을 기본 추천 경로로 유지하고, macOS GUI 실행 smoke checklist를 추가한다.
  - `docs/WINDOWS_A_TO_Z_GUIDE.md`: 기존 setup script 기반 GUI 실행 흐름과 ZIP 배포 기준을 보강한다.
  - `README.md`: GUI 고도화 요약과 배포 방식 결정 기준을 짧게 반영한다.
  - PyInstaller/native bundle은 feasibility note와 수동 smoke 체크리스트까지 포함하되, 실제 공식 배포 산출물 생성은 Q60의 필수 완료 조건으로 두지 않는다.

#### 테스트 범위

- `tests/test_gui_runner.py` 또는 신규 `tests/test_gui_state.py`
  - recent state 저장/로드가 deterministic하게 동작한다.
  - 최대 recent 개수 제한, 중복 경로 갱신, missing/corrupt JSON fallback, clear recent를 검증한다.
  - recent state에는 원문 텍스트, 표/이미지 내용, warning message가 저장되지 않는다.
- GUI helper tests
  - 선택된 result row에서 Markdown/report/manifest/assets open target을 올바르게 결정한다.
  - open failure가 conversion status를 바꾸지 않는 warning 경로인지 검증한다.
  - batch progress event가 progress state current/total/status에 반영되는지 검증한다.
- 문서 테스트
  - README, macOS guide, Windows guide, GUI user guide가 Q60 UX와 배포 정책 문구를 포함하는지 고정한다.
- 기존 회귀
  - `python -m pytest tests/test_gui_runner.py`
  - `python -m pytest tests/test_docs_examples.py`
  - 가능하면 전체 `python -m pytest`
  - `python -m pdf2md.gui --help`

#### 로컬 GUI smoke checklist

1. `python -m pdf2md.gui --help`가 창 없이 종료되는지 확인한다.
2. `python -m pdf2md.gui`로 실제 창을 연다.
3. 단일 PDF fixture를 선택하고 기본 output folder로 변환한다.
4. Results 표에서 Markdown/report/manifest 경로가 표시되는지 확인한다.
5. 선택 행 기준 Markdown/report/manifest/assets 또는 output folder 열기가 동작하는지 확인한다.
6. 폴더 배치 변환에서 progressbar가 문서 index/total 기준으로 움직이는지 확인한다.
7. Cancel은 현재 문서 완료 후 남은 문서를 `cancelled`로 표시하는지 확인한다.
8. 앱을 닫고 다시 열었을 때 최근 입력/출력 경로가 복구되는지 확인한다.
9. Clear recent 후 재실행하면 경로가 복구되지 않는지 확인한다.

#### 배포 판단

- Q60 기준 기본 추천 경로는 ZIP/source checkout + venv setup + `python -m pdf2md.gui`다.
- Windows는 기존 `scripts/setup_windows_env.ps1` / `.bat` 흐름을 우선한다.
- macOS는 Homebrew 또는 python.org Python 3.11+ + venv 흐름을 우선한다.
- PyInstaller/native bundle은 다음 조건을 만족할 때만 별도 Q로 승격한다.
  - PyMuPDF/Tkinter/Tesseract 의존성 포함 또는 외부 설치 진단이 명확하다.
  - macOS/Windows 각각에서 GUI launch와 sample conversion smoke가 통과한다.
  - code signing/notarization/보안 경고 대응 범위가 문서화된다.

#### 비범위

- core `run_conversion` 내부 구조 변경
- PDF preview, Markdown preview, report editor
- page-level progress를 가장한 임의 진행률
- native installer, code signing, notarization, auto-update
- PyInstaller 산출물을 공식 릴리스 artifact로 만드는 작업
- 새 public JSON output schema

## 완료 명세 Archive

완료된 Q34-Q59 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
