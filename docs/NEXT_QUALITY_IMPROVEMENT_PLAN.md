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

### P1 / Q73. GUI Incremental Corpus Options

CLI의 `--previous-corpus-manifest`, `--reuse-unchanged` 기능을 GUI에서도 사용할 수 있게 한다.

핵심 범위:

- GUI에 previous corpus manifest 선택과 reuse unchanged toggle 추가
- profile에는 manifest path를 저장하지 않고 현재 세션/local-only state 정책만 유지
- GUI batch 결과에 `corpus_diff_report.json`, `requirement_change_impact_report.json` 생성 경로 표시
- CLI와 동일한 reuse/skip 상태 계약을 테스트로 고정

### P1 / Q74. CLI/GUI Golden Parity Gate

같은 입력 PDF와 같은 옵션에서 CLI와 GUI headless runner가 동일 산출물을 생성하는지 자동 검증하는 parity gate를 추가한다.

핵심 범위:

- CLI/GUI 동일 옵션 실행 후 Markdown, manifest, report, RAG sidecar normalized hash 비교
- optional release gate 또는 별도 script로 `gui-parity` 검증 추가
- nondeterministic path/timing field는 기존 normalize helper로 비교
- GUI가 CLI와 같은 core pipeline을 쓰는 계약을 회귀 방어

### P2 / Q75. GUI Metrics And Page Progress Contract

GUI에서 CLI 운영자가 보는 수준의 성능/진행 판단 정보를 확인할 수 있게 한다.

핵심 범위:

- GUI summary/log에 elapsed time, pages/sec, document count, status count, retry candidate count 표시
- pipeline page progress callback contract 설계
- 단일 PDF는 실제 page progress가 있을 때만 percent 표시
- batch progress는 기존 document-level percent와 page-level detail을 혼동하지 않도록 분리

### P2 / Q76. CLI/GUI Performance Benchmark Report

CLI와 GUI headless runner의 성능 차이를 수치로 추적하는 local-only benchmark report를 추가한다.

핵심 범위:

- synthetic fixture 기반 CLI vs GUI headless benchmark script 추가
- elapsed ms, pages/sec, output hash equality, optional memory metric 기록
- `scripts/run_release_gates.py`에 optional performance/parity check로 연결 가능하게 설계
- report는 local-only 검증 artifact로 두고 public output schema로 취급하지 않음
