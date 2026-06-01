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

### P0 / Q92. Active Backlog And Local Artifact Hygiene

#### 배경

현재 `tasks.md`에는 M01-M05 유지보수 백로그가 남아 있고, 이 living backlog는 Q91 완료 후 비어 있었다. 또한 local full conversion artifact가 패키지 디렉터리 아래에 생기면 `rg`, packaging, review diff, wheel contents 판단에 노이즈가 된다.

#### 목표

- `tasks.md` 유지보수 항목과 Q92-Q97 실행 계획의 관계를 명확히 한다.
- local evaluation input/output은 패키지 소스 트리와 분리한다.
- 현재 active backlog 상태를 README, Next Plan, 개발 명세, 테스트 계약에 일관되게 반영한다.

#### 구현 범위

- `tasks.md` M01-M05를 다음 Q 작업과 연결한다.
  - M01: Q93
  - M02: Q94
  - M03: Q92, Q95
  - M04: Q92
  - M05: Q95, Q96
- local output 위치 정책을 문서화하고 `.gitignore` 후보를 검토한다.
- `pdf2md/` 아래 conversion output을 새로 만들지 않는 운영 예시를 README 또는 개발 문서에 반영한다.
- 문서 계약 테스트가 active backlog 존재를 확인하도록 갱신한다.

#### 제외 범위

- 사용자 local artifact 삭제 또는 이동은 자동으로 수행하지 않는다.
- 변환 엔진 동작, public output schema, CLI option 의미는 변경하지 않는다.

#### 검증 기준

- 문서 테스트가 Q92-Q97 active backlog를 확인한다.
- `git diff --check`가 통과한다.
- `git status --short`에서 새로 추가된 의도치 않은 generated artifact가 없다.

### P0 / Q93. Pipeline Stage And Output Responsibility Split

#### 배경

`pdf2md.pipeline`은 core PDF conversion orchestration뿐 아니라 RAG sidecar build/write, manifest/report write, debug artifact, warning/report aggregation 보조 함수까지 함께 가진다. 현재 기능은 안정적이지만 변경 단위가 커져 회귀 원인을 좁히기 어렵다.

#### 목표

- conversion orchestration은 유지하면서 stage별 책임을 작게 분리한다.
- public output byte contract와 deterministic ordering을 유지한다.
- report summary와 stage duration 계산이 기존 테스트와 동일하게 동작하게 한다.

#### 구현 범위

- output writing helper를 별도 module 또는 dataclass 기반 helper로 이동한다.
- RAG sidecar build/write 단계를 pipeline에서 호출 가능한 독립 함수로 분리한다.
- report metric 계산에 필요한 intermediate result를 명시적 구조로 묶는다.
- `ConversionResult`, `ConversionProgressEvent`, CLI/GUI 호출 계약은 유지한다.
- 기존 normalized golden output과 schema output이 바뀌지 않도록 한다.

#### 제외 범위

- 새 extractor backend 추가는 하지 않는다.
- RAG record schema 변경은 하지 않는다.
- 성능 최적화는 구조 분리 후 별도 Q로 다룬다.

#### 검증 기준

- 전체 pytest
- `python -m pdf2md --help`
- `scripts/export_output_schema.py --check`
- golden corpus normalized diff 무변경

### P0 / Q94. Warning And Reason Taxonomy Contract

#### 배경

warning code 상수화는 시작되어 있지만, 일부 정책은 prefix/suffix 문자열 판정이나 reason string set에 의존한다. CLI exit code, GUI summary, report summary, release gate가 같은 의미 체계를 보려면 warning metadata 계약이 필요하다.

#### 목표

- warning code별 domain, severity, exit-code 영향, public report 노출 여부를 한 곳에서 관리한다.
- table/image/OCR/structure reason code를 안정적으로 유지한다.
- advisory fallback과 actionable failure의 차이를 테스트로 고정한다.

#### 구현 범위

- `WarningCode` 주변에 registry 또는 enum metadata 구조를 추가한다.
- `is_advisory_warning`, `is_actionable_warning`, `determine_conversion_status`가 metadata를 우선 사용하게 한다.
- table fallback/coercion, OCR empty result, image extraction/crop rejection 정책을 명시적으로 테스트한다.
- README와 `docs/OUTPUT_SCHEMA.md`에서 warning severity 정책을 필요한 만큼 보강한다.

#### 제외 범위

- 기존 warning code 문자열 rename은 하지 않는다.
- JSON schema breaking change는 하지 않는다.
- GUI 표시 문구 대규모 개편은 하지 않는다.

#### 검증 기준

- `tests/test_pipeline_reporting.py`
- `tests/test_output_schema_contract.py`
- warning severity 관련 GUI runner tests
- `scripts/export_output_schema.py --check`

### P1 / Q95. Lightweight CI And Release Gate Coverage

#### 배경

현재 CI는 Python 3.11/3.14에서 pytest와 CLI smoke를 수행한다. 별도로 release gate script가 있지만 모든 gate를 PR마다 돌리기에는 무겁다. 빠른 PR feedback과 release-only 검증을 분리해야 한다.

#### 목표

- PR마다 실행할 lightweight gate와 release/manual gate를 구분한다.
- schema/docs/package smoke 회귀를 CI에서 더 빨리 잡는다.
- real corpus/RAG/benchmark 검증은 로컬 또는 release workflow로 유지한다.

#### 구현 범위

- CI에 추가 가능한 command 후보를 runtime 기준으로 분류한다.
- `scripts/run_release_gates.py`의 targeted gate 실행 예시를 문서화한다.
- 필요 시 별도 workflow 또는 manual dispatch 설계를 추가한다.
- package smoke와 wheel contract를 lightweight하게 돌릴 수 있는지 검토한다.

#### 제외 범위

- private/large corpus를 CI에 올리지 않는다.
- OCR language pack 설치가 필요한 무거운 runtime test는 기본 PR CI에 넣지 않는다.
- benchmark threshold를 PR 필수 gate로 만들지 않는다.

#### 검증 기준

- workflow syntax 확인
- local equivalent command smoke
- `tests/test_quality_gate_scripts.py`
- 문서 계약 테스트

### P1 / Q96. Korean, OCR, And Image-Only Golden Promotion

#### 배경

fixture builder에는 한글, image-only, OCR 성격의 PDF 생성기가 존재한다. 그러나 모든 우선순위 fixture가 golden comparison 대상으로 승격되어 있지는 않다. PRD는 한글 문서와 스캔 PDF를 중요한 fixture로 본다.

#### 목표

- 한글 원문 보존과 OCR 무교정 정책을 regression test로 더 강하게 고정한다.
- image-only/OCR page의 partial success, warning, report summary 정책을 golden 또는 targeted test로 검증한다.
- runtime OCR 의존성과 deterministic unit/golden test를 분리한다.

#### 구현 범위

- `korean` fixture를 golden corpus comparison 대상으로 추가하는 방안을 우선 검토한다.
- `image_only` fixture는 runtime OCR 없이 안정적으로 비교 가능한 output만 golden으로 올릴지 판단한다.
- OCR low/empty/confidence warning은 mock 기반 targeted tests로 보강한다.
- `kor+eng` runtime check는 release/smoke 문서에 남기고 기본 golden과 분리한다.

#### 제외 범위

- 실제 Tesseract 결과를 golden으로 고정하지 않는다.
- OCR 텍스트를 사람이 보기 좋게 교정하지 않는다.
- 새 외부 OCR engine adapter는 추가하지 않는다.

#### 검증 기준

- `tests/test_golden_corpus.py`
- `tests/test_ocr.py`
- `tests/test_pipeline_reporting.py`
- Markdown/report/manifest normalized diff 확인

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

완료된 Q34-Q91 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
