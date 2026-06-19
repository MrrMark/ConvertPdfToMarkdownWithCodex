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

### P0-P2 / Q119-Q125. PDF2MD Native Migration Plan

Docling을 runtime backend나 필수 dependency로 채택하지 않고, Docling에서 참고할 만한 설계 아이디어를 `pdf2md` 네이티브 기능으로 재구현한다.
canonical output은 계속 `pdf2md`의 `document.md`, `manifest.json`, `report.json`, RAG sidecar, provenance/index/SSD-RAG validator 계약으로 유지한다.

상세 개발 명세는 `docs/PDF2MD_NATIVE_MIGRATION_DEVELOPMENT_SPEC.md`에서 관리한다.

#### Q119. Table Confidence v2

- 우선순위: P0
- 목표: table confidence, fallback reason, header/body/stub 구조, continued table linkage를 강화한다.
- 핵심 산출물: table quality metric v2, fallback reason taxonomy 확장, technical table provenance 강화.
- 검증: table, complex table, continued table, NVMe table slice regression.

#### Q120. Native Hybrid Chunking v2

- 우선순위: P0
- 목표: section hierarchy, table atomicity, repeated header context, relationship metadata 기반 chunking을 강화한다.
- 핵심 산출물: `retrieval_chunks_rag.jsonl` metadata 확장 후보와 chunk eval 개선.
- 검증: RAG chunk/index contract/RAG eval tests.

#### Q121. Layout Sidecar and Reading Order Diagnostics

- 우선순위: P0
- 목표: multi-column, furniture, caption linkage, bbox normalization을 구조화한다.
- 핵심 산출물: `page_layout_rag.jsonl` 또는 `layout_rag.jsonl` 후보와 report summary metrics.
- 검증: text layout, header/footer, caption linkage fixtures.

#### Q122. Region OCR Evidence v2

- 우선순위: P1
- 목표: figure/table crop OCR을 원문 대체가 아닌 evidence sidecar로 강화한다.
- 핵심 산출물: OCR evidence sidecar 또는 figure sidecar 확장, accepted/rejected reason taxonomy.
- 검증: OCR, image, RAG figure tests와 no Markdown text pollution regression.

#### Q123. OCR Backend Registry Expansion

- 우선순위: P1
- 목표: `tesseract` 기본 경로를 유지하면서 optional OCR backend를 native protocol로 확장한다.
- 핵심 산출물: `tesseract-cli`, `rapidocr`, `ocrmac` adapter 후보와 structured warning/report fields.
- 검증: OCR backend probe, optional dependency 미설치 test, scanned/Korean OCR fixture.

#### Q124. Figure Semantics v2

- 우선순위: P1
- 목표: figure kind, observed text, generated description, structure evidence를 분리 강화한다.
- 핵심 산출물: figure structures/descriptions schema 확장 후보와 visual eval 보강.
- 검증: RAG figure/semantic tests, visual RAG eval, figure description eval.

#### Q125. Domain Adapter Registry Hardening

- 우선순위: P2
- 목표: NVMe/OCP/PCIe/TCG/SPDM/manual adapter를 registry/protocol 구조로 정리한다.
- 핵심 산출물: adapter protocol, adapter metadata, spec type/revision mapping, cross-spec compatibility checks.
- 검증: domain adapter, SSD-RAG contract, latest NVMe/OCP benchmark.

## 완료 명세 Archive

완료된 Q34-Q118 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
