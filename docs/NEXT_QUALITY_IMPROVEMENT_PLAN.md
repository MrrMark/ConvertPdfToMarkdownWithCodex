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

### P1 / Q34. Offline Index Contract Validator

- OpenAI/Azure AI Search/LangChain/LlamaIndex mapping recipe가 요구하는 필드와 타입을 로컬에서 검증하는 validator script를 추가한다.
- 외부 서비스 호출 없이 JSONL field contract, metadata 크기, source_refs 보존 여부, confidential-safe 공유 가능 범위를 점검한다.
- 실패 시 어느 chunk/sidecar/field가 문제인지 deterministic report로 출력한다.

### P2 / Q35. Rendered Diagram Fixture Suite

- state machine, sequence diagram, register layout synthetic PDF를 렌더링 기반 fixture로 추가한다.
- `figures_rag.jsonl`의 `diagram_label_diagnostics`와 bbox/caption/heading provenance를 golden으로 고정한다.
- OCR runtime이 없을 때와 있을 때의 기대 diagnostics를 분리해 CI 안정성을 유지한다.

### P2 / Q36. Page-Level Parallel Extractor

- 문서 단위 증분 캐시 이후, page extraction/read-order/table 후보 생성을 page worker 단위로 병렬화할 수 있는 executor를 추가한다.
- 출력 순서, warning/report ordering, asset naming은 기존 deterministic contract를 유지한다.
- 기본값은 single-worker로 두고, `--page-workers` opt-in에서 benchmark gate로 속도 향상과 결과 동일성을 함께 검증한다.
