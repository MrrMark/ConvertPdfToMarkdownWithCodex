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

### Q81. Structure Marker OCR Early Stop And Cache

실제 NVMe Key Value Command Set PDF에서 `image_extraction`이 여전히 전체 변환 시간의 대부분을 차지한다. Q80에서 중복 Tesseract 호출은 제거했지만 25 page 기준 `image_extraction=70.6s`, `pages/sec=0.34` 수준이므로, 구조 마커 OCR 후보 수집에 early stop, variant cache, context-aware PSM 축소를 추가해 산출물 동일성을 유지하면서 0.7 pages/sec 이상을 목표로 한다.

검증 기준:

- 실제 local `pdf/` corpus에서 `document.md`와 `retrieval_chunks_rag.jsonl` normalized diff 없음
- structure marker recovered/suppressed count 유지
- corpus gate `--corpus-min-pages-per-second 0.7` 통과 또는 명확한 하드웨어 기준 문서화

### Q82. Expected Table Fallback Severity Taxonomy

현재 실제 NVMe corpus는 표 52개 중 39개를 HTML fallback으로 안전하게 처리하고 `table_low_quality_count=0`이지만, `TABLE_COMPLEXITY_HTML_FALLBACK` warning 39건 때문에 문서 상태가 `partial_success`가 된다. 복잡 표를 HTML fallback으로 보내는 것은 의도된 보수 동작이므로, release/corpus gate에서 실제 실패와 expected fallback advisory를 더 잘 구분해야 한다.

검증 기준:

- 복잡 표 HTML fallback은 report에 보존하되 partial success 판정의 actionable failure와 분리
- low-quality table, unresolved table, extraction failure는 기존처럼 gate에서 감지
- 기존 golden table fallback diagnostics와 Markdown warning comment 계약 유지

### Q83. Real Corpus Cross Reference Precision

실제 NVMe profile 출력에서 `cross_ref_resolved_coverage=27/35=0.7714`다. 미해결 항목에는 `Table of Figures`, `section defines`, `register level interface`처럼 target label이 불명확하거나 참조가 아닌 문구가 섞여 있다. cross-ref classifier의 precision을 높여 불필요한 unresolved record를 줄이고 real technical spec 기준 coverage를 0.85 이상으로 끌어올린다.

검증 기준:

- 실제 NVMe local RAG eval에서 `min_cross_ref_resolved_coverage >= 0.85`
- 명확한 Figure/Table/Section/technical ref resolution은 유지
- false positive 억제 케이스를 synthetic fixture로 추가
