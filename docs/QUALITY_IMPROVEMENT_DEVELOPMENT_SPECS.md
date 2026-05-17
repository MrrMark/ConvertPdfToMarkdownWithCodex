# Quality Improvement Development Specs

이 문서는 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에 남아 있는 **active Q 작업**을 실제 구현 PR로 옮기기 위한 개발 명세다.

완료된 Q 작업의 명세와 구현 결과는 이 문서에 남기지 않고 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에서 관리한다.

## 운영 규칙

- `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에 신규 Q 항목이 추가되면, 구현 전에 이 문서에 대응 개발 명세를 작성한다.
- 구현 중 범위가 바뀌면 Next Plan 항목과 이 문서를 함께 갱신한다.
- 구현 완료, 테스트 통과, PR merge까지 끝난 Q 항목은 이 문서에서 제거하고 완료 명세 archive로 옮긴다.
- 완료 이력은 Git commit, PR, release note, changelog, 그리고 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에서 추적한다.
- 이 문서에는 앞으로 구현할 active 명세만 있어야 한다.

## 공통 원칙

- 외부 RAG/indexing 서비스 호출은 구현 범위에 포함하지 않는다.
- 모든 검증과 fixture 생성은 local-only, deterministic 동작을 기본으로 한다.
- PDF 원문 텍스트, 표, 이미지 provenance는 요약하거나 재서술하지 않는다.
- 새 public JSON 출력이 생기면 `docs/OUTPUT_SCHEMA.md`와 `docs/schema/` 계약을 함께 갱신한다.
- 실패는 가능한 한 구조화된 report로 남기고, 어느 파일/record/field/page가 문제인지 식별 가능해야 한다.
- 테스트는 작은 unit test, script smoke test, golden regression test를 우선한다.

## 현재 Active Development Specs

## P2 / Q76. CLI/GUI Performance Benchmark Report

### 배경

현재 간단한 로컬 측정에서는 GUI headless runner와 CLI 실행 시간이 거의 비슷하지만, 이를 장기적으로 추적하는 공식 local benchmark는 없다. GUI가 CLI 수준의 운영 신뢰도를 갖추려면 output parity뿐 아니라 성능 오버헤드도 수치로 확인할 수 있어야 한다.

### 목표

- CLI와 GUI headless runner의 실행 시간을 같은 synthetic fixture와 같은 옵션으로 비교한다.
- output hash equality와 성능 값을 함께 기록한다.
- report는 local-only 검증 artifact로 두고 public output schema로 취급하지 않는다.

### 구현 범위

- 새 script 예: `scripts/benchmark_gui_cli_parity.py`
  - single/batch synthetic PDF fixture 생성
  - CLI 실행과 GUI headless runner 실행
  - elapsed ms, pages/sec, output hash equality 기록
  - optional memory metric은 플랫폼 안정성이 확인될 때만 포함
- optional release/performance gate 연결
  - threshold는 기본 advisory로 시작
  - fail-on-regression은 baseline report가 명시된 경우에만 사용
- 테스트
  - report 구조, output equality, threshold/advisory policy 검증
  - raw PDF text/path가 local-only report 밖으로 노출되지 않는지 검증
- 문서
  - README/quality docs에 benchmark 사용법과 해석 기준 추가

### 검증

- `.venv311/bin/python -m pytest tests/test_quality_gate_scripts.py`
- `.venv311/bin/python scripts/benchmark_gui_cli_parity.py --output-dir /private/tmp/pdf2md-gui-cli-benchmark`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- GUI rendering/frame-rate benchmark
- OS-level click automation
- hard performance threshold를 baseline 없이 강제
- public output schema 추가

## 완료 명세 Archive

완료된 Q34-Q75 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
