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

## P2 / Q53. Minimal Desktop GUI Wrapper

### 목표

CLI에 익숙하지 않은 비개발자와 간단한 설치/실행만 원하는 개발자가 PDF 파일 또는 폴더를 선택해 변환할 수 있도록 최소 desktop GUI를 추가한다.

Q53의 핵심은 새 변환 엔진을 만드는 것이 아니라, 기존 `Config`와 `run_conversion` 경로를 그대로 사용하는 얇은 GUI wrapper를 제공하는 것이다. GUI는 사용 편의성을 높이되, CLI와 다른 산출물 계약을 만들면 안 된다.

### 사용자 가치

- 사용자는 터미널 명령어를 외우지 않고 PDF 파일 또는 폴더를 선택해 변환할 수 있다.
- 개발자는 빠른 수동 테스트나 데모에서 GUI로 입력/출력/옵션을 지정할 수 있다.
- Windows/macOS 사용자는 설치 후 `python -m pdf2md.gui` 또는 packaging entry point로 더 쉽게 시작할 수 있다.
- 실패/partial success 상태를 로그 창에서 확인하고 결과 폴더를 바로 찾을 수 있다.

### 구현 원칙

- GUI는 CLI를 대체하지 않는다. CLI는 계속 primary automation interface로 유지한다.
- GUI는 변환 로직을 재구현하지 않고 `pdf2md.config.Config`와 `pdf2md.pipeline.run_conversion`을 호출한다.
- Tkinter 기반으로 시작해 새 runtime dependency를 추가하지 않는다.
- GUI 모듈 import만으로 창이 뜨거나 변환이 실행되면 안 된다.
- 긴 변환 중 UI가 멈추지 않도록 worker thread 또는 background task로 실행한다.
- 원문 보존, 표 안전성, 이미지 referenced mode, partial success, deterministic output 원칙은 CLI와 동일하다.
- GUI는 옵션을 친절하게 선택하게 도와주는 shell이며, 산출물 schema나 sidecar 형식은 바꾸지 않는다.

### 범위

새 모듈 후보:

- `pdf2md/gui.py`
  - Tkinter app entry
  - 파일 선택 / 폴더 선택 / 출력 폴더 선택
  - 옵션 form 구성
  - 실행 버튼, 취소 또는 실행 중 비활성화 상태
  - 진행 로그와 summary 표시
- `pdf2md/gui_runner.py` 또는 `pdf2md/conversion_runner.py`
  - GUI와 테스트가 함께 쓰는 순수 orchestration helper
  - 단일 파일 변환과 폴더 batch 변환 요청을 `Config`로 변환
  - GUI 상태 업데이트에 필요한 deterministic result summary 생성

초기 GUI control:

- 입력 모드: 단일 PDF 파일 / PDF 폴더
- 입력 경로: file dialog / directory dialog
- 출력 폴더
- page range
- password
- `skip_existing`
- `image_mode`: `referenced`, `embedded`, `placeholder`
- `table_mode`: `auto`, `html`, `markdown`
- `rag_table_output`: `none`, `markdown`, `jsonl`, `both`
- `domain_adapter`: `none`, `nvme`, `pcie`, `ocp`, `tcg`, `customer-requirements`
- `confidential_safe_mode`
- `force_ocr`
- `ocr_lang`
- `remove_header_footer`
- `dedupe_images`
- `repair_hyphenation`
- `figure_crop_fallback`
- `keep_page_markers`

초기 UX:

- 선택한 입력/출력 경로와 주요 옵션을 한 화면에 둔다.
- 변환 중에는 실행 버튼을 비활성화하고 현재 처리 상태를 로그에 표시한다.
- 완료 후 success / partial_success / failed / skipped counts를 표시한다.
- 결과 폴더 경로를 표시한다.
- GUI 안에서 source text를 수정하거나 미리보기 편집 기능은 제공하지 않는다.

### 테스트 계획

- headless CI에서 Tk mainloop를 띄우지 않는 pure helper test를 우선한다.
- GUI request model 또는 helper가 CLI option과 동일한 `Config` 값을 만드는지 검증한다.
- 단일 PDF GUI request가 `run_conversion`과 동일 산출물을 만드는 smoke test를 추가한다.
- 폴더 batch GUI request가 CLI batch와 동일한 skip-existing 정책을 쓰는지 검증한다.
- `python -m pdf2md.gui --help` 또는 import smoke가 창 실행 없이 통과하도록 entry를 분리한다.
- docs test에 GUI 실행 문서와 Q53 active backlog 계약을 반영한다.

### 문서 갱신

- `README.md`
  - CLI가 기본 자동화 경로이고 GUI는 간편 실행 wrapper임을 명시한다.
  - `python -m pdf2md.gui` 실행 예시를 추가한다.
- `docs/WINDOWS_A_TO_Z_GUIDE.md`
  - Windows 사용자의 GUI 실행 경로와 여전히 CLI/batch script가 자동화용이라는 차이를 설명한다.
- `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`
  - Q53 active backlog 유지.
- `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`
  - 구현 완료 후 Q53 archive로 이동.

### 완료 조건

- GUI에서 단일 PDF와 폴더 batch 변환을 실행할 수 있다.
- 동일 입력/옵션에서 GUI와 CLI의 core 산출물 계약이 동일하다.
- GUI import/smoke와 runner unit test가 CI에서 통과한다.
- 새 dependency 없이 macOS/Windows 기본 Python 환경에서 실행 가능하다.
- README/Windows guide가 GUI와 CLI의 역할 차이를 명확히 설명한다.

### 비범위

- 대형 GUI application framework 도입
- Electron, Qt, web server 기반 UI
- PDF 미리보기/페이지 썸네일/본문 편집기
- 변환 산출물 수동 편집 기능
- 외부 RAG/indexing 서비스 호출
- GUI 전용 output schema 또는 CLI와 다른 변환 옵션 의미

## 완료 명세 Archive

완료된 Q34-Q52 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
