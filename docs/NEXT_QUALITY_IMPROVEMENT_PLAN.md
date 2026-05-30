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

### P0 / Q90. Cross Reference Target Index Expansion

최신 NVMe Base Specification 2.3 전체 변환에서 `cross_ref_resolved_coverage`가 약 69.5%에 머문다. 실제 미해결 원인은 대부분 원문 추출 실패가 아니라 section/figure target index 부족과 register/capability 일반 문장 오탐이다.

구현 방향:

- PDF outline/bookmark를 section target 보조 index로 사용하되, 기존 extracted heading target을 우선한다.
- List of Figures/Table of Figures 항목을 figure target fallback으로 사용해 본문 caption 누락을 보강한다.
- `Figure 23Figure` 같은 붙은 라벨과 `sections 3.6.1 and 3.6.2` 같은 복수 section 참조를 보수적으로 정규화한다.
- register/capability 참조는 명확한 identifier shape 또는 실제 target map이 있을 때만 cross-ref로 기록하고, 일반 prose는 skip한다.
- 외부 RFC appendix와 PCI/MSI-X 용어성 table label은 local unresolved cross-ref로 남기지 않는다.

완료 기준:

- synthetic unit/golden fixture에서 outline fallback, figure-list fallback, 복수 section reference, register false-positive suppression, external appendix/table skip이 검증된다.
- 최신 NVMe Base Specification 2.3 local-only 재평가에서 `cross_ref_resolved_coverage >= 0.90`을 목표로 하고, 가능하면 오탐 억제 후 0.94 이상을 확인한다.
- `document.md` 원문 보존과 기존 table/image/RAG sidecar 계약을 깨지 않는다.
