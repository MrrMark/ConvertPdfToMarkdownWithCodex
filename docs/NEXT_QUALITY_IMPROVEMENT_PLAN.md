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

Q53 Minimal Desktop GUI Wrapper 이후 후속 작업은 GUI가 기존 CLI 변환 계약을 바꾸지 않으면서 비개발자/간편 실행 사용자에게 안정적으로 동작하도록 만드는 범위로 제한한다. 우선순위는 운영 리스크, 사용자 영향, 결정성 회귀 가능성 순서로 둔다.

| Q | 우선순위 | 작업 | 목표 |
|---|---|---|---|
| Q58 | P2 | GUI Smoke And Contract Test Expansion | GUI wrapper가 CLI `Config`/산출물 계약을 계속 따르는지 headless smoke와 문서 계약 테스트로 고정한다. |

### Q58. GUI Smoke And Contract Test Expansion

- GUI runner 옵션 매핑, batch naming, skip-existing, diagnostics, result summary를 headless 테스트로 고정한다.
- 새 public JSON 출력이 생기는 경우 `docs/OUTPUT_SCHEMA.md`와 `docs/schema/`를 함께 갱신한다.
- GUI 테스트는 실제 창 의존도를 최소화하고 CI Python 3.11/3.14에서 deterministic하게 통과해야 한다.
