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

### P1 / Q107. Assetless Figure Visual Semantics Layer

이미지 파일 업로드가 불가능한 RAG 환경에서 회로도, 파형, 블록다이어그램처럼 의미가 이미지 자체에 있는 figure의 검색성을 개선한다.
기존 `이미지 업로드 불가 RAG 대응` preset의 기본 보수 동작은 유지하고, region OCR, generated figure description, figure structure extraction을 모두 opt-in 시각 의미 보강 계층으로 설계한다.

핵심 원칙:

- `figure_text`는 계속 관측 텍스트 기반 chunk로 유지한다.
- 생성 설명은 원문 텍스트와 분리해 별도 sidecar와 `chunk_type`으로 표시한다.
- 이미지 파일, base64 image payload, 외부 RAG/indexing service 호출은 산출물에 포함하지 않는다.
- backend 미설치/저신뢰 결과는 partial success보다 advisory warning/report로 우선 기록한다.
