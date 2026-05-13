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

### Q11. RAG Retrieval Chunk Pack

- `retrieval_chunks_rag.jsonl`을 추가해 vector DB에 바로 넣기 좋은 chunk 단위를 생성한다.
- chunk는 `text_blocks_rag`, `semantic_units`, `requirements`, `tables_rag` provenance를 포함한다.
- Q10 semantic layer가 안정화된 뒤 진행한다.

### Q12. RAG Evaluation Harness

- 스펙 질의 golden set, expected source ids, hit@k, MRR, citation coverage, chunk length 분포를 검증한다.
- 초기 버전은 외부 embedding 없이 deterministic local retrieval 평가부터 시작한다.

### Q13. Multi-PDF Corpus Manifest

- 여러 PDF 스펙을 함께 운영하기 위한 `doc_id`, source hash, schema version, output file map, selected pages manifest를 추가한다.
- stable id와 incremental ingest/diff 운영의 기반으로 사용한다.

### Q14. Figure/Diagram RAG Sidecar

- 이미지/도표 캡션, OCR 후보, figure bbox, nearby heading을 `figures_rag.jsonl`로 분리한다.
- 기본 설명 생성은 하지 않고 추출 가능한 원문/캡션 중심으로 유지한다.

### Q15. Domain Adapter

- NVMe 같은 기술 스펙에서 command, opcode, register field, enum/value table을 더 잘 뽑는 opt-in adapter를 추가한다.
- 기본 변환 로직에는 특정 도메인 heuristic을 과하게 넣지 않는다.
