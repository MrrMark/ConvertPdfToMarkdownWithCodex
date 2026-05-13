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

### Q03. Figure Crop Fallback 시각 검증 및 보정

현재 `--figure-crop-fallback`은 확실한 caption이 있고 embedded image가 없는 page에서만 보수적으로 crop 후보를 만든다. 다음 단계에서는 crop 결과가 빈 이미지이거나 잘못된 영역이 되지 않도록 시각적/픽셀 기반 검증을 추가한다.

#### 구현 명세

- crop 후보 생성 후 간단한 픽셀 진단을 수행한다.
  - blank/near-blank ratio
  - content bbox estimate
  - crop area ratio
- blank에 가까운 crop은 저장하지 않고 report warning으로 기록한다.
- debug mode에서 crop 후보 bbox와 rejected reason을 JSON으로 남긴다.
- manifest image metadata를 확장한다.
  - `crop_content_ratio`
  - `crop_rejected_reason`
- fixture를 추가한다.
  - caption 아래 figure
  - caption 위 figure
  - caption만 있고 figure가 없는 page
  - embedded image와 crop fallback이 동시에 가능한 page

#### Acceptance

- 기본 동작은 변하지 않고 `--figure-crop-fallback` opt-in을 유지한다.
- caption만 있는 page에서 빈 crop asset을 만들지 않는다.
- crop fallback 결과가 manifest/report/debug artifact에 결정적으로 기록된다.
- 완료 후 테스트 통과 및 PR merge까지 끝나면 이 항목은 이 문서에서 제거한다.

### Q04. Multi-page Table Continuation 보정

현재 table continuation은 인접 page의 같은 header와 caption 부재를 중심으로 보수적으로 연결한다. 다음 단계에서는 실문서 반복 템플릿을 continuation으로 오탐하지 않도록 confidence와 negative fixture를 강화한다.

#### 구현 명세

- continuation 판단 feature를 명시적으로 기록한다.
  - normalized header similarity
  - bbox alignment similarity
  - caption distance
  - page adjacency
  - repeated template penalty
- table diagnostics/report에 continuation reason을 추가한다.
  - `continuation_reasons`
  - `continuation_rejected_reasons`
- RAG sidecar JSONL에도 continuation group과 confidence를 유지한다.
- calibration fixture를 확장한다.
  - multi-page continued table
  - 다음 page에만 caption이 있는 table
  - footnote가 table 하단에 붙은 table
  - wide table
  - 반복 header를 가진 서로 다른 table

#### Acceptance

- 복잡 표는 계속 HTML fallback을 기본 유지한다.
- confidence가 낮으면 continuation으로 연결하지 않는다.
- 반복 header가 있는 독립 표를 잘못 연결하지 않는다.
- 완료 후 테스트 통과 및 PR merge까지 끝나면 이 항목은 이 문서에서 제거한다.

### Q08. Release Gate Runner 통합

현재 corpus 품질 게이트, benchmark 성능 게이트, OCR preflight, 패키징 smoke 절차가 각각 존재한다. 다음 단계에서는 릴리스 전에 한 명령으로 필요한 게이트를 실행하고 결과를 하나의 summary로 남기는 runner를 추가한다.

#### 구현 명세

- `scripts/run_release_gates.py`를 추가한다.
- 실행 항목을 옵션으로 제어한다.
  - OCR runtime/language preflight
  - corpus quality gate
  - benchmark performance gate
  - packaging smoke
- baseline/report 경로를 명시적으로 받는다.
  - `--corpus-input-dir`
  - `--corpus-baseline-report`
  - `--benchmark-baseline-report`
  - `--output-dir`
- 출력 `release_gate_report.json`을 생성한다.
  - 실행한 gate 목록
  - 각 gate command/exit code/status
  - 생성된 report path
  - 전체 `passed_release_gate`
- 저작권 있는 PDF, baseline report, release 산출물은 repo에 커밋하지 않는다.
- README/Windows guide에 릴리스 전 단일 runner 예시를 추가한다.

#### Acceptance

- 선택한 gate 중 하나라도 실패하면 runner가 non-zero exit code를 반환한다.
- 기본 CI job에는 무거운 corpus/benchmark를 넣지 않고 수동/릴리스 전 실행으로 유지한다.
- subprocess를 monkeypatch한 unit test로 성공/실패 summary와 exit code를 검증한다.
- 완료 후 테스트 통과 및 PR merge까지 끝나면 이 항목은 이 문서에서 제거한다.

### Q09. Machine-readable Output Schema Export

현재 출력 계약은 `docs/OUTPUT_SCHEMA.md`와 Pydantic model/contract test로 보호된다. 다음 단계에서는 외부 시스템이 자동 검증에 사용할 수 있도록 machine-readable JSON Schema export를 추가한다.

#### 구현 명세

- `scripts/export_output_schema.py`를 추가한다.
- Pydantic model에서 JSON Schema를 생성한다.
  - `Manifest`
  - `Report`
  - `BatchReport`
- schema 산출물을 `docs/schema/` 아래에 저장한다.
  - `manifest.schema.json`
  - `report.schema.json`
  - `batch_report.schema.json`
- `docs/OUTPUT_SCHEMA.md`에서 machine-readable schema 위치를 연결한다.
- schema export가 deterministic한지 테스트한다.

#### Acceptance

- JSON Schema 파일이 stable key order와 LF로 생성된다.
- 생성된 schema 파일을 current model로 재생성했을 때 diff가 없어야 한다.
- README/Windows guide 또는 `docs/OUTPUT_SCHEMA.md`에서 schema 파일 경로를 찾을 수 있다.
- 완료 후 테스트 통과 및 PR merge까지 끝나면 이 항목은 이 문서에서 제거한다.
