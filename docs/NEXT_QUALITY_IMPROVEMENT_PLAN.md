# Next Quality Improvement Plan

이 문서는 앞으로 작업할 항목만 관리하는 living backlog다.

## 운영 규칙

- 새로 착수할 작업이나 발견된 개선 과제는 구현 전에 이 문서에 추가한다.
- 작업이 완료되고 테스트 통과 및 PR merge까지 끝나면 해당 항목은 이 문서에서 제거한다.
- 완료 이력은 이 문서에 누적하지 않고 Git commit, PR, release note, changelog에서 추적한다.
- 이 문서에는 항상 아직 남은 다음 작업만 보여야 한다.
- 새 작업 PR에는 가능하면 다음 중 하나를 포함한다.
  - 신규 작업 추가: 이 문서에 항목 추가
  - 기존 작업 완료: 이 문서에서 해당 항목 제거
  - 범위 변경: 항목 내용을 현재 결정사항 기준으로 갱신

## 남은 작업

### Q01. 실문서 Corpus 품질 게이트 고도화

현재 `scripts/run_corpus_eval.py`는 로컬 `pdf/` 같은 비공개 corpus를 평가하고 요약 JSON을 만든다. 다음 단계에서는 릴리스 전 품질 게이트로 쓸 수 있도록 기준선 비교와 threshold 판정을 추가한다.

#### 구현 명세

- `scripts/run_corpus_eval.py`에 기준선 비교 옵션을 추가한다.
  - `--baseline-report PATH`
  - `--fail-on-regression`
  - `--max-partial-rate FLOAT`
  - `--max-low-quality-table-rate FLOAT`
  - `--min-pages-per-second FLOAT`
- 출력 `corpus_eval_report.json`에 regression summary를 추가한다.
  - `baseline_report`
  - `regressions`
  - `passed_quality_gate`
  - `thresholds`
- 비교 대상은 결정적 집계값만 사용한다.
  - success/partial/failed/skipped count
  - table fallback reason counts
  - low quality table count
  - suppressed line count
  - pages/sec
  - pdf_open_count
  - text_line_extract_count
- 저작권 있는 PDF와 평가 산출물은 repo에 커밋하지 않는다.

#### Acceptance

- 기준선이 없으면 현재처럼 단일 평가 리포트를 만든다.
- 기준선이 있으면 regression 여부를 deterministic하게 기록한다.
- `--fail-on-regression` 사용 시 threshold 실패를 non-zero exit code로 반환한다.
- README/Windows guide에 릴리스 전 품질 게이트 예시 명령이 반영된다.
- 완료 후 테스트 통과 및 PR merge까지 끝나면 이 항목은 이 문서에서 제거한다.

### Q02. Font/Geometry 기반 텍스트 블록 구조화

현재 serializer는 보수적으로 숫자형 섹션 제목과 명확한 list/code-like block만 처리한다. 다음 단계에서는 PDF raw line의 font/size/geometry 정보를 이용해 원문 손실 없이 heading/list/code/footnote 판단 정확도를 높인다.

#### 구현 명세

- text extraction 단계에서 line metadata를 확장한다.
  - dominant font size
  - font family/style hint
  - left/right indent
  - line height
  - page-relative y band
- block classifier를 추가한다.
  - 확실한 큰 제목만 heading으로 승격한다.
  - 대문자 본문이나 표 제목을 heading으로 오탐하지 않는다.
  - 연속 list item은 Markdown list block으로 안정적으로 묶는다.
  - 들여쓰기와 monospace-like 패턴이 강한 블록만 fenced code로 처리한다.
  - 하단 영역의 확실한 각주만 footnote/comment 후보로 분리한다.
- report summary에 optional 진단을 추가한다.
  - `font_heading_candidate_count`
  - `footnote_candidate_count`
  - `structure_low_confidence_count`

#### Acceptance

- 기본 정책은 계속 보수적이며 애매하면 본문으로 유지한다.
- 신규 fixture/golden을 추가한다.
  - title-only heading
  - uppercase body non-heading
  - grouped ordered/unordered list
  - multi-line code block
  - bottom footnote
- 기존 document.md golden에서 의도치 않은 heading/list/code 변경이 없어야 한다.
- 완료 후 테스트 통과 및 PR merge까지 끝나면 이 항목은 이 문서에서 제거한다.

### Q03. Figure Crop Fallback 시각 검증 및 보정

현재 `--figure-crop-fallback`은 확실한 caption이 있고 embedded image가 없는 page에서만 보수적으로 crop 후보를 만든다. 다음 단계에서는 crop 결과가 빈 이미지이거나 잘못된 영역이 되지 않도록 시각적/픽셀 기반 검증을 추가한다.

#### 구현 명세

- crop 후보 생성 후 간단한 픽셀 진단을 수행한다.
  - blank/near-blank ratio
  - content bbox estimate
  - crop area ratio
- blank에 가까운 crop은 저장하지 않고 report warning으로 기록한다.
- debug mode에서 crop 후보 bbox와 rejected reason을 JSON으로 남긴다.
- manifest image metadata를 확장한다.
  - `crop_content_ratio`
  - `crop_rejected_reason`
- fixture를 추가한다.
  - caption 아래 figure
  - caption 위 figure
  - caption만 있고 figure가 없는 page
  - embedded image와 crop fallback이 동시에 가능한 page

#### Acceptance

- 기본 동작은 변하지 않고 `--figure-crop-fallback` opt-in을 유지한다.
- caption만 있는 page에서 빈 crop asset을 만들지 않는다.
- crop fallback 결과가 manifest/report/debug artifact에 결정적으로 기록된다.
- 완료 후 테스트 통과 및 PR merge까지 끝나면 이 항목은 이 문서에서 제거한다.

### Q04. Multi-page Table Continuation 보정

현재 table continuation은 인접 page의 같은 header와 caption 부재를 중심으로 보수적으로 연결한다. 다음 단계에서는 실문서 반복 템플릿을 continuation으로 오탐하지 않도록 confidence와 negative fixture를 강화한다.

#### 구현 명세

- continuation 판단 feature를 명시적으로 기록한다.
  - normalized header similarity
  - bbox alignment similarity
  - caption distance
  - page adjacency
  - repeated template penalty
- table diagnostics/report에 continuation reason을 추가한다.
  - `continuation_reasons`
  - `continuation_rejected_reasons`
- RAG sidecar JSONL에도 continuation group과 confidence를 유지한다.
- calibration fixture를 확장한다.
  - multi-page continued table
  - 다음 page에만 caption이 있는 table
  - footnote가 table 하단에 붙은 table
  - wide table
  - 반복 header를 가진 서로 다른 table

#### Acceptance

- 복잡 표는 계속 HTML fallback을 기본 유지한다.
- confidence가 낮으면 continuation으로 연결하지 않는다.
- 반복 header가 있는 독립 표를 잘못 연결하지 않는다.
- 완료 후 테스트 통과 및 PR merge까지 끝나면 이 항목은 이 문서에서 제거한다.

### Q05. OCR Runtime/Language 사전 점검

현재 `--ocr-lang`은 CLI/API에서 OCR runtime으로 전달되며, runtime 부재는 partial success/report warning으로 처리한다. 다음 단계에서는 사용자가 변환 전에 OCR 언어팩과 runtime 상태를 쉽게 확인할 수 있는 사전 점검을 추가한다.

#### 구현 명세

- 새 스크립트를 추가한다.
  - `scripts/check_ocr_runtime.py`
- 점검 항목을 JSON과 사람이 읽는 텍스트로 출력한다.
  - Tesseract executable 발견 여부
  - pytesseract import 여부
  - pypdfium2 import 여부
  - 요청한 language data 발견 여부
  - 권장 설치 힌트
- CLI 또는 README 예시에서 `kor+eng` 점검 흐름을 문서화한다.

#### Acceptance

- Tesseract가 없는 환경에서도 deterministic하게 실패 이유를 출력한다.
- `kor+eng` 같은 복합 language 값에서 누락된 언어팩을 식별한다.
- 실제 변환 명령은 계속 partial success 정책을 유지한다.
- 완료 후 테스트 통과 및 PR merge까지 끝나면 이 항목은 이 문서에서 제거한다.
