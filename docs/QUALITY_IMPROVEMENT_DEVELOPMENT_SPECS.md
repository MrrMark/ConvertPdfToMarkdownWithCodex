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

### P2 / Q97. Modern Python Tooling And Packaging Readiness

#### 배경

프로젝트는 Python 3.11+와 pytest 중심으로 안정화되어 있으나 lint/type/package/audit 도구는 아직 최소 수준이다. 릴리스 품질을 높이려면 도구를 추가하되, conversion behavior 변경과 분리해야 한다.

#### 목표

- ruff 기반 lint/format 정책을 보수적으로 도입한다.
- type check는 warning 관측부터 시작해 점진적으로 strictness를 올린다.
- package metadata, typed package marker, release note/changelog 후보를 정리한다.

#### 구현 범위

- `pyproject.toml`에 ruff 설정 후보를 추가한다.
- lint command를 README와 CI 후보에 반영한다.
- `py.typed`, `LICENSE`, `CHANGELOG.md` 필요성을 검토하고 최소 artifact를 추가한다.
- dependency audit은 advisory release gate 후보로 문서화한다.

#### 제외 범위

- 대규모 formatting churn은 첫 PR에서 하지 않는다.
- mypy/pyright strict mode를 즉시 필수 CI로 만들지 않는다.
- dependency major upgrade는 별도 Q로 분리한다.

#### 검증 기준

- lint command smoke
- package build smoke
- wheel contract smoke
- 문서 예시와 pyproject 설정 동기화

## 완료 명세 Archive

완료된 Q34-Q96 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
