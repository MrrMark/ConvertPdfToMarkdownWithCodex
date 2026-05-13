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

## 기본 작업 플로우

1. 작업 시작 전 이 문서에서 해당 backlog 항목을 확인하거나 신규 항목을 추가한다.
2. 구현 PR에는 가능하면 코드 변경과 함께 이 문서의 항목 추가/삭제/범위 변경을 포함한다.
3. 구현 완료, 테스트 통과, PR merge까지 끝난 항목은 다음 작업 시작 전에 이 문서에서 제거한다.
4. 구현 중 발견한 후속 과제는 완료 항목에 남기지 않고 새 Q 항목으로 분리한다.

## 남은 작업

현재 backlog는 모두 **RAG 운영 목적**의 개선 작업이다. PDF 변환 산출물을 AI Agent/Copilot의 스펙 분석, 요구사항 추적, 테스트 스크립트 구현에 더 안정적으로 쓰기 위한 항목만 남긴다.

### P0 / Q26. Real Technical Corpus Calibration Gate

- NVMe, PCIe, OCP, TCG 공개 스펙과 sanitized customer-like fixture를 대표 corpus로 묶어 RAG sidecar 품질 threshold를 정의한다.
- requirement coverage, table-field coverage, cross-reference resolved coverage, chunk token 분포, conversion duration을 release gate 후보로 승격한다.
- 대외비 원문은 커밋하지 않고 synthetic/sanitized fixture와 로컬 전용 corpus profile만 사용한다.

### P0 / Q27. Requirement Change Impact Matrix

- 여러 버전의 스펙 PDF를 비교해 added/changed/removed requirement id와 source_refs를 별도 diff sidecar로 기록한다.
- 고객 requirement spec 변경 시 AI Agent가 영향 분석과 test script 수정 범위를 빠르게 찾을 수 있도록 `requirement_traceability_rag.jsonl`과 연결한다.
- 문장 요약/재서술 없이 원문 diff provenance만 제공한다.

### P1 / Q28. Domain Adapter Deep Fixtures

- NVMe command/log page/feature/status, PCIe capability/register/ECN, OCP requirement table, TCG method/object/security table synthetic fixtures를 더 촘촘히 추가한다.
- `technical_tables_rag.jsonl`과 `domain_units_rag.jsonl`의 unit_type별 golden을 늘려 도메인 heuristic 회귀를 막는다.
- customer requirement spec은 synthetic/sanitized sample만 사용한다.

### P1 / Q29. RAG Indexer Integration Recipes

- OpenAI/Azure AI Search/LangChain/LlamaIndex 등에 넣기 위한 field mapping 예시와 ingestion checklist를 문서화한다.
- 기본 구현은 외부 서비스를 호출하지 않고, JSONL field contract와 chunk 선택 기준만 제공한다.
- confidential safe mode와 함께 사용할 때 공유 가능한 metadata 범위를 명확히 한다.

### P2 / Q30. Diagram OCR And Label Recovery Calibration

- state machine, sequence diagram, register layout figure의 label/OCR 후보 품질을 정량 진단한다.
- 기본 설명 생성은 계속 하지 않고, caption/OCR label/bbox/heading provenance 중심으로 개선한다.
- 낮은 확신 diagram label은 record로 승격하지 않고 diagnostics에만 남긴다.
