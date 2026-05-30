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

### Q85. RAG Preset Status And Warning Severity Calibration

- `rag_optimized`에서 정상적인 보수적 fallback과 실제 조치 필요 warning을 더 명확히 분리한다.
- `TABLE_COMPLEXITY_HTML_FALLBACK`처럼 의도된 HTML fallback은 advisory로 유지하되 GUI summary에서 failure처럼 읽히지 않게 status/score 산정 정책을 보강한다.
- `OCR_EMPTY_RESULT`는 `force_ocr`, scan/blank/decorative page 여부, 기존 text layer 존재 여부에 따라 advisory/actionable을 분리한다.
- `table_low_quality_count`는 raw quality score만으로 partial success를 만들지 않고, RAG row recovery 가능성, artifact/index/provenance validation 결과를 함께 반영해 actionable low-quality만 partial 조건으로 삼는다.

### Q86. Full Technical Spec Table Quality Triage And Recovery

- NVMe Base 2.3 같은 장문 기술 스펙에서 low-quality table을 page/table 단위 evidence pack으로 집계한다.
- 반복되는 `Column N` header, multi-row header, byte/bit layout table, continued table, footnote row를 우선 복구 대상으로 분류한다.
- `table_low_quality_count`, `table_unresolved_count`, `table_actionable_fallback_count`가 실제 운영 risk를 나타내도록 report schema와 quality gate를 정비한다.

### Q87. Technical Spec RAG Preset Domain Profile UX

- GUI `기술 스펙 RAG` 프리셋이 `RAG 등록용(최적화)`와 동일 산출물을 내는 문제를 해소한다.
- 기술 스펙 프리셋에서는 domain adapter를 별도 locked advanced option으로 숨기지 말고 NVMe/PCIe/OCP/TCG/SPDM 같은 spec family 선택 흐름을 제공한다.
- CLI/GUI 모두 `technical_spec_rag` 목적에 맞게 domain unit, SSD contract validation, profile별 eval fixture를 자연스럽게 실행할 수 있게 한다.

### Q88. Storage And Security Domain Adapter Expansion

- 기존 `nvme`, `pcie`, `ocp`, `tcg` adapter coverage를 실제 storage/security spec table shape 기준으로 확장한다.
- SPDM 계열 문서를 위한 first-class `spdm` adapter를 추가해 message code, request/response, measurement, certificate, algorithm, key exchange, session/security state table을 typed unit으로 추출한다.
- domain unit이 `retrieval_chunks_rag.jsonl`, SSD contract validator, evidence pack, RAG eval source coverage에 연결되도록 schema와 tests를 확장한다.

### Q89. Real Corpus Preset Evaluation And Score Gate

- `rag_optimized`와 `technical_spec_rag`를 실제 NVMe/PCIe/OCP/TCG/SPDM corpus로 주기 평가한다.
- 점수 산정 기준을 artifact integrity, index contract, source-ref coverage, chunk token compliance, table-field coverage, requirement coverage, cross-ref resolved coverage, actionable warning count, conversion time으로 고정한다.
- GUI preset별 산출물 diff와 score report를 local-only artifact로 생성하는 runner를 추가한다.
