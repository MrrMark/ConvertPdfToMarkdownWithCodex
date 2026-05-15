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

### P2 / Q58. GUI Smoke And Contract Test Expansion

#### 문제 정의

GUI는 얇은 wrapper여야 하며 CLI와 별도의 변환 계약을 만들면 안 된다. 향후 Q54-Q57에서 GUI 상태/summary/문서가 늘어나면 CLI `Config` 매핑, batch naming, skip-existing, diagnostics, docs contract 회귀를 더 촘촘하게 막아야 한다.

#### 구현 범위

- GUI runner 옵션 매핑 test matrix를 확장한다.
- single/batch output naming이 CLI 규칙과 일치하는지 고정한다.
- diagnostic/result summary가 원문 내용을 요약하지 않는지 구조적으로 검증한다.
- GUI module import와 `--help` smoke는 창을 띄우지 않는 방식으로 유지한다.
- 가능한 경우 Tk root 생성이 필요한 테스트는 opt-in 또는 monkeypatch로 격리한다.

#### 테스트/검증

- `tests/test_gui_runner.py` 확장.
- `tests/test_docs_examples.py`에서 active backlog/spec 계약 확인.
- `env PYTHONPATH=. pytest tests/test_gui_runner.py tests/test_docs_examples.py -vv`
- 전체 `env PYTHONPATH=. pytest`
- schema check와 `git diff --check`.

#### 완료 기준

- GUI wrapper가 CLI 변환 계약을 벗어나면 테스트가 실패한다.
- headless CI에서 GUI 관련 테스트가 안정적으로 통과한다.
- Q54-Q57 구현 후에도 public schema와 문서 계약 변경 여부가 명확히 드러난다.

## 구현 우선순위

1. Q58: 앞선 GUI 후속 작업의 계약 회귀를 headless smoke와 문서 테스트로 고정한다.

## 완료 명세 Archive

완료된 Q34-Q57 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
