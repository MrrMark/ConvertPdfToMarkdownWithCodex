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

### P1 / Q61. GUI Localization, Presets, And Progress Percent

#### 배경

Q60 구현 후 실제 GUI 확인에서 세 가지 사용성 요구가 추가로 확인됐다.

첫째, GUI 기본 사용자는 한국어 사용자가 많으므로 기본 UI는 한글이어야 하고, 필요한 경우 English로 전환할 수 있어야 한다. 둘째, 현재 GUI는 세부 옵션을 처음부터 노출해 비개발자가 어떤 조합을 골라야 하는지 부담이 크다. 셋째, Q60의 progressbar는 시각적 상태를 보여주지만 batch 변환에서는 숫자 percent도 함께 보여주는 편이 진행 상황 파악에 유리하다.

이 작업도 core 변환 엔진 개선이 아니라 GUI orchestration과 표시 계층 개선이다. PDF 원문, report/manifest schema, warning code, RAG sidecar 계약은 그대로 유지한다.

#### 목표

- GUI 언어를 기본 `한국어`, 선택 `English`로 제공한다.
- 목적 기반 preset을 추가해 첫 화면에서 `기본 모드(원본 유지)`, `RAG 등록용(최적화)`, `Optimize Options(유저 선택)` 중 고르게 한다.
- preset은 내부적으로 기존 `GuiConversionOptions`로만 매핑하며 CLI option 의미를 새로 만들지 않는다.
- batch 변환 진행 상태에 `current/total`과 percent text를 함께 표시한다.
- single conversion은 실제 page-level progress가 없으므로 indeterminate 표시를 유지하고, 완료 시에만 `100%`로 표시한다.

#### 구현 범위

- `pdf2md/gui_i18n.py` 또는 동등한 순수 helper
  - `GuiLanguage` literal: `ko`, `en`
  - `GuiTextKey` 또는 string key 기반 catalog
  - `translate(language, key, **values)` helper
  - 누락 key는 English fallback 또는 key fallback으로 GUI 시작 실패를 막는다.
  - Korean catalog를 기본으로 유지한다.
- `pdf2md/gui_presets.py` 또는 동등한 순수 helper
  - `GuiOptionPreset`: `preserve`, `rag_optimized`, `custom`
  - `preset_display_name(language, preset)`
  - `options_for_preset(preset, current_options)` 또는 `apply_preset_to_options()`
  - `preserve`는 원본 보존 우선:
    - `image_mode=referenced`
    - `table_mode=auto`
    - `rag_table_output=none`
    - `domain_adapter=none`
    - `force_ocr=False`
    - header/footer removal, hyphenation repair, figure crop fallback 같은 heuristic flag는 기본 off
  - `rag_optimized`는 RAG sidecar/provenance 중심:
    - `rag_table_output=both`
    - `keep_page_markers=True`
    - `repair_hyphenation=True`
    - `remove_header_footer=True`
    - `image_mode=referenced`
    - `table_mode=auto`
    - `force_ocr=False`
    - `confidential_safe_mode`는 사용자가 켜는 opt-in으로 유지
  - `custom`은 현재 UI 값을 보존하고 flag 영역을 직접 편집 가능하게 한다.
  - `pages`, `password`, `ocr_lang`, `input/output`은 preset 적용으로 덮어쓰지 않는다.
- `pdf2md/gui_state.py`
  - 최근 경로 state에 selected language와 selected preset을 추가한다.
  - 이전 Q60 state 파일도 깨지지 않게 schema migration 또는 tolerant load를 제공한다.
  - 저장 state에는 여전히 원문 텍스트, table/image content, warning message를 넣지 않는다.
- `pdf2md/gui.py`
  - language selector 추가
  - preset selector 추가
  - 기본 시작 언어는 `ko`, 기본 preset은 `preserve`
  - `custom`이 아닌 preset에서는 세부 flag 영역을 비활성화하거나 읽기 전용으로 표시한다.
  - preset 변경 시 UI 변수와 `GuiConversionOptions`가 동기화된다.
  - progress label은 batch에서 `2/10 (20%)` 형식으로 표시한다.
  - single conversion은 `처리 중...` / `Converting...`과 indeterminate bar를 유지하고 완료 시 `100%`로 표시한다.

#### 테스트 범위

- `tests/test_gui_i18n.py`
  - 한국어 기본 catalog 주요 key 존재
  - English catalog 주요 key 존재
  - format placeholder 치환
  - missing key fallback
- `tests/test_gui_presets.py`
  - `preserve` preset mapping이 보수적 원본 유지 정책과 일치
  - `rag_optimized` preset mapping이 RAG sidecar/provenance 옵션을 켬
  - `rag_optimized`가 `force_ocr`를 강제로 켜지 않음
  - `custom`은 현재 options를 보존
  - `pages`, `password`, `ocr_lang`이 preset 적용으로 바뀌지 않음
- `tests/test_gui_state.py`
  - language/preset 저장과 복구
  - Q60 schema 또는 누락 field fallback
  - corrupt JSON fallback 유지
- `tests/test_gui_runner.py` 또는 GUI helper test
  - batch progress percent text
  - single conversion 완료 시 100% 표시 helper
- `tests/test_docs_examples.py`
  - GUI guide/README/macOS/Windows 문서가 language selector, preset, percent 표시 정책을 설명하는지 고정

#### UX 정책

- `기본 모드(원본 유지)`는 가장 보수적인 기본값이다.
- `RAG 등록용(최적화)`은 Markdown 원문을 바꾸는 기능이 아니라 sidecar/provenance와 RAG 친화 옵션을 켜는 preset이다.
- `Optimize Options(유저 선택)`은 기존 advanced mode에 가깝다.
- 사용자가 preset을 바꿔도 input/output, pages, password는 유지한다.
- language 전환은 GUI 표시 문구만 바꾸며 변환 output에는 영향을 주지 않는다.
- percent는 실제 document-level progress만 표현한다. page-level progress가 없으면 단일 PDF 처리 중 percent를 추정하지 않는다.

#### 로컬 GUI smoke checklist

1. GUI를 실행하면 기본 한글 UI로 표시되는지 확인한다.
2. language selector를 English로 바꾸면 주요 label/button/status가 English로 바뀌는지 확인한다.
3. `기본 모드(원본 유지)`에서 advanced flags가 보수적 기본값인지 확인한다.
4. `RAG 등록용(최적화)`을 선택하면 RAG tables/page marker/hyphenation/header-footer 관련 UI가 preset에 맞게 바뀌는지 확인한다.
5. `Optimize Options(유저 선택)`에서 세부 옵션을 직접 바꿀 수 있는지 확인한다.
6. 폴더 배치 변환에서 `current/total (percent%)` 표시가 progressbar와 일치하는지 확인한다.
7. 단일 PDF 변환 중에는 indeterminate 상태이고 완료 후 `100%`가 되는지 확인한다.
8. GUI를 재시작했을 때 language/preset 선택이 local-only state에서 복구되는지 확인한다.

#### 비범위

- PDF 원문 내용 번역 또는 localization
- schema key, warning code, report/manifest field명 번역
- core pipeline page-level progress callback
- OCR language 자동 선택 또는 문서 언어 감지
- user behavior analytics
- native installer/package 생성

## 완료 명세 Archive

완료된 Q34-Q60 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
