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

### P0 / Q119. Table Confidence v2

기술 스펙 표의 confidence, fallback reason, header/body/stub column, continued table linkage를 강화한다.
복잡 표는 계속 HTML fallback을 우선하며, GFM 승격 기준을 완화하지 않는다.

상세 명세: `docs/PDF2MD_NATIVE_MIGRATION_DEVELOPMENT_SPEC.md`

### P0 / Q120. Native Hybrid Chunking v2

Docling식 document-native/hybrid chunking 개념을 `pdf2md`의 `retrieval_chunks_rag.jsonl` 계약에 맞게 네이티브로 구현한다.
section hierarchy, table atomicity, repeated header context, chunk relationship metadata를 강화한다.

상세 명세: `docs/PDF2MD_NATIVE_MIGRATION_DEVELOPMENT_SPEC.md`

### P0 / Q121. Layout Sidecar and Reading Order Diagnostics

multi-column, page furniture, caption linkage, bbox normalization을 구조화해 technical spec reading order와 layout provenance를 강화한다.
raw full text 없이 source_ref와 layout summary 중심으로 sidecar/report metric을 제공한다.

상세 명세: `docs/PDF2MD_NATIVE_MIGRATION_DEVELOPMENT_SPEC.md`

### P1 / Q122. Region OCR Evidence v2

figure/table bbox crop OCR을 원문 대체가 아닌 evidence sidecar로 강화한다.
accepted/rejected reason, confidence, backend, bbox, source_ref를 분리 기록하고 Markdown 본문 오염을 방지한다.

상세 명세: `docs/PDF2MD_NATIVE_MIGRATION_DEVELOPMENT_SPEC.md`

### P1 / Q123. OCR Backend Registry Expansion

현재 `tesseract` 기본 경로를 유지하면서 `tesseract-cli`, `rapidocr`, `ocrmac` 등 optional OCR backend를 `pdf2md` 네이티브 protocol로 확장한다.
optional dependency 미설치는 fatal이 아니라 structured warning/report로 처리한다.

상세 명세: `docs/PDF2MD_NATIVE_MIGRATION_DEVELOPMENT_SPEC.md`

### P1 / Q124. Figure Semantics v2

figure kind, observed text, generated description, structure evidence를 명확히 분리해 visual technical spec RAG 품질을 높인다.
generated content는 기본 비활성, sidecar-only, review flag 포함 원칙을 유지한다.

상세 명세: `docs/PDF2MD_NATIVE_MIGRATION_DEVELOPMENT_SPEC.md`

### P2 / Q125. Domain Adapter Registry Hardening

NVMe/OCP/PCIe/TCG/SPDM/manual domain adapter를 registry/protocol 구조로 정리해 cross-spec 재처리와 고객별 adapter 확장을 안정화한다.
schema contract와 validator는 core에서 통제한다.

상세 명세: `docs/PDF2MD_NATIVE_MIGRATION_DEVELOPMENT_SPEC.md`
