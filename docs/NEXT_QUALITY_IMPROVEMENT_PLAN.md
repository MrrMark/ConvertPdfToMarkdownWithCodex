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

### Q115. Visual Technical Spec RAG Profile and Metrics

NVMe Base/Command와 OCP spec의 figure, diagram, waveform, register layout 검색성을 강화하기 위해
`technical_spec_rag_visual` 또는 동등한 공식 visual preset을 추가한다.

범위:

- CLI/MCP/GUI/agent skill에서 같은 visual option bundle을 선택할 수 있게 한다.
- `figure_text`, `figure_description`, `figure_structure` retrieval chunk 계약을 schema/docs/test로 고정한다.
- official NVMe/OCP benchmark report에 visual metric을 추가한다.
- 자세한 명세는 `docs/VISUAL_TECHNICAL_SPEC_RAG_DEVELOPMENT_SPEC.md`를 따른다.

### Q116. SSD Verification Agent PDF2MD Sidecar Handoff

`ssd-verification-agent`가 pdf2md 산출물을 local source-of-truth로 ingest하고 RAG server 검색 결과와 병행 운영할 수 있도록
handoff 명세를 확정한다.

범위:

- pdf2md 쪽 산출물/validator/MCP 계약을 handoff 문서로 정리한다.
- `ssd-verification-agent` 쪽 API/MCP/direct ingest/figure evidence/scoring 작업을 분리 명세로 제공한다.
- 자세한 명세는 `docs/SSD_VERIFICATION_AGENT_PDF2MD_VISUAL_RAG_HANDOFF_SPEC.md`를 따른다.
