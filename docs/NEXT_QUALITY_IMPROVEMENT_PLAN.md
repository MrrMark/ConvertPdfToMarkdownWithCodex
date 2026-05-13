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

### Q16. RAG Chunk Boundary Quality

- `retrieval_chunks_rag.jsonl`의 chunk 길이, section boundary, heading carry-over, 중복 provenance를 정량 진단한다.
- chunk text는 원문 기반을 유지하고 요약/재서술은 도입하지 않는다.
- 긴 section과 짧은 requirement chunk가 검색 품질을 해치지 않도록 deterministic packing rule을 개선한다.

### Q17. RAG Evaluation Golden Set

- `scripts/run_rag_eval.py`에 사용할 스펙 질의 golden set과 expected source id fixture를 추가한다.
- hit@k, MRR, citation coverage, chunk length 분포를 release gate 후보로 승격한다.
- 초기 평가는 deterministic local retrieval로 유지하고 embedding/외부 서비스는 opt-in 후속으로 둔다.

### Q18. Incremental Corpus Ingest Diff

- `corpus_manifest.json`의 `doc_id`, `source_sha256`, output file map을 기준으로 changed/unchanged/removed 문서를 판정한다.
- 대량 PDF 스펙 운영에서 재변환과 vector DB re-index 대상을 최소화하는 diff report를 추가한다.
- 기존 batch 변환 결정성은 유지한다.

### Q19. RAG Cross-Reference Resolution Expansion

- `cross_refs_rag.jsonl`의 target을 `figures_rag.jsonl`, `tables_rag.jsonl`, `semantic_units_rag.jsonl` record id와 더 적극적으로 연결한다.
- unresolved reference는 계속 보존하되, resolved coverage를 report summary에 추가한다.
- 잘못된 resolved보다 unresolved 보존을 우선한다.

### Q20. Domain Adapter Coverage Expansion

- `--domain-adapter nvme`의 command set, opcode, register field, enum/value table fixture를 늘린다.
- adapter별 schema 예시와 golden을 추가해 도메인 heuristic 회귀를 막는다.
- 기본 변환 로직에는 특정 도메인 heuristic을 추가하지 않고 opt-in adapter 안에 격리한다.
