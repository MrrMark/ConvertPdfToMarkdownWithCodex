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

상세 개발 명세는 `docs/QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md`에서 관리한다.

### P2 / Q42. Full Page Worker Table Candidate Parallelization

- Q36에서 안전하게 도입한 `--page-workers` text/read-order 병렬 경로를 table candidate extraction까지 확장한다.
- page-local table 후보 생성은 worker에서 수행하되 continuation grouping, warning ordering, asset/table index 재확정은 parent merge에서 deterministic하게 처리한다.
- benchmark gate에 `--page-workers 1`과 `--page-workers > 1` 결과 동일성 및 최소 성능 신호를 함께 고정한다.
