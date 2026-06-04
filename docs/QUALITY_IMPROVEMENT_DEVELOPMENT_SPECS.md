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

### 공통 결정 사항

Q105는 Docling 벤치마킹 결과 기반 확장 설계를 다룬다.
상충되는 요구는 아래 기준으로 정리한다.

- 기본 `image_mode=referenced`와 기존 public output contract는 유지한다.
- OCR 비활성화는 성능 개선책으로 사용하지 않는다. OCR 호출 수를 줄이더라도 evidence/context로 결정 가능한 경우에만 줄인다.
- Docling식 picture description 또는 VLM 경로는 설계 대상이지만 기본 변환에는 넣지 않는다.
- Q104 benchmark evidence는 `/tmp` 또는 local `pdf/` 아래에 두고 raw PDF, image, Markdown 원문, 고객 식별 경로는 커밋하지 않는다.
- 새 CLI 옵션, public JSON field, summary count가 생기면 README, `docs/OUTPUT_SCHEMA.md`, schema export, docs tests를 함께 갱신한다.

### P2 / Q105. Docling-Informed OCR And Layout Extension Design

#### 목표

Q104 벤치마크 결과를 바탕으로 실제 도입할 확장 기능을 정한다.
후보는 다중 OCR backend, 도표/표 영역별 OCR, 선택적 picture description, layout-aware table/figure 인식이다.

#### 설계 후보

- OCR backend adapter
  - `TesseractOcrBackend` 기존 구현 유지
  - `RapidOcrBackend`, `EasyOcrBackend`, `OcrMacBackend`는 optional dependency로 분리
  - backend별 language code mapping과 confidence normalization을 명시
- Region OCR
  - full page OCR보다 image/table/figure crop OCR을 먼저 시도
  - crop bbox, source figure/table id, confidence, rejected reason을 report에 기록
- Picture description
  - 기본 비활성화
  - local-only model 또는 explicit remote opt-in만 허용
  - output field는 `generated_description` 계열로 원문 `text`와 분리
- Layout-aware table/figure adapter
  - Docling adapter는 P2 experimental backend로 둔다.
  - current extractor 결과와 adapter 결과를 바로 섞지 않고 comparison/evidence pack을 먼저 만든다.

#### 완료 조건

- Q104 metric으로 실제 개선 가능성이 확인된 후보만 구현 backlog로 승격한다.
- 새 기능은 adapter/opt-in 구조와 schema contract를 갖는다.
- 원문 텍스트와 table row source-of-truth를 생성형 출력으로 대체하지 않는다.

## 완료 명세 Archive

완료된 Q34-Q104 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
