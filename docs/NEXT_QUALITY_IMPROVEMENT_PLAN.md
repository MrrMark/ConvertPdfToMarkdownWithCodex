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

### P1 / Q61. GUI Localization, Presets, And Progress Percent

Q60으로 GUI 실행 흐름, 결과 파일 열기, 최근 경로 저장, 진행 상태 표시가 보강된 뒤 실제 사용 중 추가 UX 요구가 확인됐다. 다음 단계는 GUI를 비개발자 친화적인 기본 한글 UI로 전환할 수 있게 하고, 처음부터 세부 옵션을 모두 고르게 하지 않도록 변환 목적별 preset을 제공하며, 신뢰 가능한 범위에서 진행률을 숫자 percent로 함께 표시하는 것이다.

#### 목표

- GUI 표시 언어를 기본 `한국어`, 선택 `English`로 지원한다.
- 변환 옵션을 처음부터 개별 flag 중심으로 노출하지 않고 `기본 모드(원본 유지)`, `RAG 등록용(최적화)`, `Optimize Options(유저 선택)` preset으로 안내한다.
- 폴더 배치 변환 진행률은 progressbar와 함께 `current/total`, percent를 표시한다.
- 단일 PDF 변환은 page-level progress callback이 생기기 전까지 가짜 percent를 만들지 않고 indeterminate 상태와 완료 `100%`만 표시한다.
- 언어/preset/progress UI는 CLI `Config`, core `run_conversion`, output schema 계약을 변경하지 않는다.

#### 우선 구현 후보

1. GUI localization helper
   - `ko`, `en` 문자열 catalog를 둔다.
   - GUI label/button/status/messagebox/log 중 UI 안내 문구를 catalog로 치환한다.
   - warning code, report/manifest key, 원문 PDF 텍스트, table/image content는 번역하지 않는다.
   - 선택 언어는 local-only GUI state에 저장하고 시작 시 복구한다.
2. Preset selector
   - 기본값은 `기본 모드(원본 유지)`다.
   - `RAG 등록용(최적화)`는 RAG sidecar/provenance 중심 옵션을 켜되 원문을 요약/재서술하지 않는다.
   - `Optimize Options(유저 선택)`을 선택했을 때만 세부 flag 영역을 직접 편집 가능하게 한다.
   - `pages`, `password`, `input/output`, `OCR lang`은 preset과 별개로 항상 접근 가능하게 둔다.
3. Progress percent display
   - batch progress는 `2/10 (20%)`처럼 표시한다.
   - skipped/cancelled/failed도 document-level event 기준으로 percent를 갱신한다.
   - single conversion은 `처리 중...` 또는 `Converting...`과 indeterminate bar를 유지하고 완료 시 `100%`로 바꾼다.

#### 완료 기준

- localization catalog와 fallback 동작이 unit test로 고정된다.
- preset이 `GuiConversionOptions`로 변환되는 mapping이 headless test로 고정된다.
- 기본 모드가 보수적 원본 유지 정책을 깨지 않는다는 test가 있다.
- RAG 등록용 preset이 RAG sidecar/provenance 옵션을 켜되 `force_ocr` 같은 공격적 옵션을 기본 강제하지 않는다.
- batch progress percent text가 deterministic helper test로 검증된다.
- README, `docs/GUI_USER_GUIDE.md`, `docs/MACOS_GUI_QUICKSTART.md`, `docs/WINDOWS_A_TO_Z_GUIDE.md`가 언어 선택, preset 의미, percent 표시 한계를 설명한다.
- 새 public JSON output schema는 만들지 않는다.

#### 비범위

- PDF 원문 텍스트, 표, 이미지 내용 번역
- report/manifest schema key 또는 warning code localization
- core pipeline page-level progress callback 구현
- OCR 언어 자동 감지
- LLM 기반 preset 추천
- native app packaging 또는 installer
