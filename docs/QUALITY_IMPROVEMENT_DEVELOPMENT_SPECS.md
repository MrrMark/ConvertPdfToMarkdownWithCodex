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

## P1 / Q73. GUI Incremental Corpus Options

### 배경

CLI batch는 `--previous-corpus-manifest`와 `--reuse-unchanged`로 incremental corpus diff, requirement impact, unchanged output reuse를 지원한다. GUI는 아직 이 운영 기능을 노출하지 않아 CLI 수준의 corpus 관리에는 부족하다.

### 목표

- GUI에서도 previous corpus manifest를 선택하고 unchanged PDF 산출물을 재사용할 수 있게 한다.
- GUI batch 결과에서 `corpus_diff_report.json`, `requirement_change_impact_report.json` artifact를 확인할 수 있게 한다.
- profile에는 previous manifest path를 저장하지 않는다.

### 구현 범위

- `pdf2md/gui_runner.py`
  - `GuiConversionOptions` 또는 request 계층에 previous corpus manifest / reuse unchanged 입력 추가
  - 공용 batch runner 옵션으로 전달
  - GUI summary에 corpus-level artifact path 포함
- `pdf2md/gui.py`
  - previous corpus manifest file picker 추가
  - reuse unchanged toggle 추가
  - corpus-level artifact open actions 추가
- `pdf2md/gui_profiles.py`
  - previous corpus manifest path, input/output path, password를 profile forbidden/local-only 정책에 명시
- 테스트
  - GUI incremental batch가 CLI와 같은 `corpus_diff_report.json`, `requirement_change_impact_report.json`을 생성하는지 검증
  - reuse unchanged가 `skipped` 상태와 기존 산출물 재사용 계약을 지키는지 검증
  - profile export에 manifest path가 저장되지 않는지 검증

### 검증

- `.venv311/bin/python -m pytest tests/test_gui_runner.py tests/test_gui_profiles.py`
- `.venv311/bin/python -m pytest tests/test_cli.py`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- cloud corpus sync
- manifest path profile 저장
- real corpus 네트워크 검증
- public output schema 추가

## P1 / Q74. CLI/GUI Golden Parity Gate

### 배경

현재 GUI는 CLI와 같은 core pipeline을 호출하지만, 향후 UI option 추가나 batch runner refactor 중 CLI/GUI 출력 차이가 생길 수 있다. 이를 release 전에 자동으로 잡는 parity gate가 필요하다.

### 목표

- 같은 입력 PDF와 같은 옵션에서 CLI와 GUI headless runner가 같은 산출물을 생성하는지 검증한다.
- Markdown, manifest, report, RAG sidecar의 normalized hash equality를 확인한다.
- optional release gate로 실행 가능하게 한다.

### 구현 범위

- 새 script 예: `scripts/run_gui_cli_parity.py`
  - synthetic single PDF fixture 생성 또는 기존 fixture 사용
  - CLI command 실행
  - GUI headless runner 실행
  - normalized artifact hash 비교
  - deterministic JSON report 작성
- `scripts/run_release_gates.py`
  - optional `gui-parity` gate 추가 또는 `gui` gate 하위 command로 연결
- `tests/test_quality_gate_scripts.py`
  - command 구성, success/failure summary, mismatch failure 검증
- `tests/test_gui_runner.py`
  - parity normalize helper와 path/timing field 제외 계약 검증

### 검증

- `.venv311/bin/python -m pytest tests/test_quality_gate_scripts.py tests/test_gui_runner.py`
- `.venv311/bin/python scripts/run_gui_cli_parity.py --output-dir /private/tmp/pdf2md-gui-cli-parity`
- `.venv311/bin/python scripts/run_release_gates.py --output-dir /private/tmp/pdf2md-q74-gates --gates gui-parity`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- real private corpus parity gate
- visual GUI automation
- 성능 pass/fail threshold
- public output schema 추가

## P2 / Q75. GUI Metrics And Page Progress Contract

### 배경

CLI output/report에는 stage duration, pages/sec, status count 같은 운영 판단 정보가 있다. GUI는 사용자 친화 summary는 제공하지만, CLI 운영자가 보는 수준의 성능/진행 정보를 모두 보여주지는 않는다. 또한 단일 PDF percent는 page-level callback이 없어서 완료 시점에만 `100%`로 표시한다.

### 목표

- GUI에서 elapsed time, pages/sec, status count, retry candidate count를 명확히 표시한다.
- pipeline page progress callback contract를 설계하고, 실제 page progress가 있을 때만 단일 PDF percent를 표시한다.
- batch document-level progress와 page-level progress를 UI에서 혼동하지 않게 분리한다.

### 구현 범위

- `pdf2md/pipeline.py` 또는 runner callback contract
  - page start/page finish 또는 total pages 기반 progress event 설계
  - core extraction logic의 결정성/출력에는 영향이 없도록 callback은 observer로 유지
- `pdf2md/gui_runner.py`
  - elapsed time, page count, pages/sec, retry candidate count 계산
  - GUI summary에 metrics 추가
- `pdf2md/gui.py`
  - metrics display 추가
  - 단일 PDF page-level progress 표시
  - batch document progress와 page progress label 분리
- 테스트
  - callback 없이 임의 percent를 표시하지 않는 계약 유지
  - callback 제공 시 progress event와 final `100%` 검증
  - metrics가 raw PDF text/path를 저장하지 않는지 검증

### 검증

- `.venv311/bin/python -m pytest tests/test_gui_runner.py tests/test_gui_layout.py tests/test_gui_i18n.py`
- `.venv311/bin/python -m pytest tests/test_pipeline_smoke.py`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- page 내부 fine-grained extractor progress
- 성능 최적화 자체
- native GUI visual screenshot automation
- public output schema 추가

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

완료된 Q34-Q72 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
