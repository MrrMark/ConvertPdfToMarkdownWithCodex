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

### P1 / Q100. OCR Page Parallelization

스캔 PDF 또는 `--force-ocr` 경로에서 OCR target page를 bounded worker로 병렬 처리한다.
warning/report/page ordering은 selected page 순서로 deterministic하게 유지한다.

### P1 / Q101. Table Strategy Adaptive Mode

표 추출에서 기본 전략 품질이 충분한 경우 추가 fallback 전략을 생략하는 adaptive mode를 도입한다.
복잡 표를 억지로 GFM으로 내보내지 않는 기존 안전 정책과 table quality diagnostics는 유지한다.

### P1 / Q102. Fast Output Profile And Sidecar Scope

`document.md`, `manifest.json`, `report.json` 중심의 opt-in fast profile과 RAG sidecar 생성 범위 `minimal|full`을 검토한다.
기본 output contract와 기본 profile 동작은 변경하지 않는다.

### P0 / Q103. Assetless Technical RAG Figure Text Chunks

이미지 파일 업로드가 불가능한 팀 RAG 환경을 위해 `placeholder + figure_text chunk` 경로를 구현한다.
이미지 파일을 생성하거나 업로드하지 않아도 caption, heading, bbox, detected labels, nearby text를 근거로 검색 가능한 figure provenance chunk를 만든다.
생성형 이미지 설명은 기본 비활성화로 유지한다.

### P1 / Q104. Docling Benchmark Harness And Comparison Pack

Docling의 OCR, table/figure layout, image export, picture enrichment 경로를 로컬 벤치마크로 비교할 수 있는 harness를 만든다.
외부 서비스 호출 없이 local-only 실행을 기본으로 하고, raw PDF/이미지/본문을 커밋하지 않는 sanitized comparison pack만 남긴다.

### P2 / Q105. Docling-Informed OCR And Layout Extension Design

Q104 결과를 바탕으로 다중 OCR backend, 도표/표 영역별 OCR, 선택적 picture description, layout-aware table/figure 인식 중 실제 도입할 항목을 설계한다.
도입 기능은 adapter/opt-in 구조로 분리하고 원문 보존, deterministic output, partial success/report 원칙을 유지한다.
