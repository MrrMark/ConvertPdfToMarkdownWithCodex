# Quality Improvement Implemented Specs

이 문서는 완료된 quality improvement Q 작업의 개발 명세와 구현 결과를 보관하는 archive다.

Active backlog는 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`, active 개발 명세는 `docs/QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md`에서 관리한다.
구현 완료, 테스트 통과, PR merge까지 끝난 명세만 이 문서로 옮긴다.

## Archive 범위

- Q34-Q42: 2026-05-14 기준 97/100 평가를 만든 RAG 운영/검증/병렬화 개선
- Q43: Q31-Q42 이후 scorecard refresh와 다음 backlog 축소
- Q46: RAG expected source coverage gate
- Q44: domain technical table typed coverage 확장
- Q47: local technical corpus evidence pack
- Q48-Q52: evidence pack analysis/trend, appendix fixture, captionless diagnostics, docs/schema contract
- Q53: minimal desktop GUI wrapper
- Q54: GUI runtime and install diagnostics
- Q55: GUI conversion result review UX
- Q56: GUI batch operation controls
- Q57: non-developer GUI distribution guide
- Q58: GUI smoke and contract test expansion
- Q59: GUI user guide and help entry
- Q60: GUI practical UX and distribution hardening
- Q61: GUI localization, presets, and progress percent
- Q62: GUI smoke evidence and layout guardrails
- Q63: GUI backlog rollover and forward specs
- Q64: responsive GUI layout and accessibility guardrails
- Q65: GUI runtime doctor and packaging compatibility smoke
- Q66: sanitized GUI support bundle
- Q67: GUI expert options and profile import/export
- Q68: GUI release gate integration
- Q69: wheel contents and GUI help resource contract
- Q70: GUI profile and support bundle failure fixture
- Q71: quality scorecard refresh and next backlog reassessment
- Q72: shared batch runner and GUI batch artifact parity
- Q73: GUI incremental corpus options
- Q74: CLI/GUI golden parity gate
- Q75: GUI metrics and page progress contract
- Q76: CLI/GUI performance benchmark report
- Q77-Q79: RAG chunk/profile optimization
- Q80-Q81: real corpus structure marker OCR/provenance and cache hardening
- Q82: expected table fallback severity taxonomy
- Q83: real corpus cross reference precision
- Q84: release readiness sweep
- Q85-Q91: RAG preset warning calibration, technical table triage, technical domain profile UX, storage/security adapter expansion, preset evaluation score gate, cross-reference target index expansion, output schema contract alignment
- Q92-Q93: active backlog/local artifact hygiene and pipeline responsibility split
- Q94: warning and reason taxonomy contract
- Q95: lightweight CI and release gate coverage
- Q96: Korean, OCR, and image-only golden promotion

## 공통 원칙

- 외부 RAG/indexing 서비스 호출은 구현 범위에 포함하지 않는다.
- 모든 검증과 fixture 생성은 local-only, deterministic 동작을 기본으로 한다.
- PDF 원문 텍스트, 표, 이미지 provenance는 요약하거나 재서술하지 않는다.
- 새 public JSON 출력이 생기면 `docs/OUTPUT_SCHEMA.md`와 `docs/schema/` 계약을 함께 갱신한다.
- 실패는 가능한 한 구조화된 report로 남기고, 어느 파일/record/field/page가 문제인지 식별 가능해야 한다.
- 테스트는 작은 unit test, script smoke test, golden regression test를 우선한다.

## P1 / Q96. Korean, OCR, And Image-Only Golden Promotion

### 목표

PRD fixture 우선순위에 맞춰 한글 문서를 golden regression 대상으로 승격하고, OCR/image-only 경로는 runtime OCR 결과를 golden으로 고정하지 않으면서 mock 기반 정책 테스트를 강화한다.

### 구현 결과

- synthetic PDF builder에 ToUnicode CMap이 있는 fixture unicode font resource를 추가해 한글 텍스트가 원문 그대로 추출되도록 했다.
- `korean` fixture를 golden corpus comparison 대상에 추가하고 `document.md`, `manifest.json`, `report.json`, RAG sidecar golden outputs를 커밋했다.
- image-only scanned PDF mock OCR 테스트에 actionable/advisory warning count와 OCR warning count 검증을 추가했다.
- Tesseract runtime 결과는 golden으로 고정하지 않고 기존 runtime smoke/check 경로와 분리했다.
- Q96을 active backlog/development specs에서 제거하고 archive로 이동했으며, README의 active backlog 상태를 Q97로 갱신했다.

### 검증

- `.venv311/bin/python -m pytest tests/test_golden_corpus.py -q`
- `.venv311/bin/python -m pytest tests/test_pipeline_reporting.py tests/test_ocr.py tests/test_docs_examples.py -q`
- `git diff --check`
- `.venv311/bin/python -m pytest`

## P1 / Q95. Lightweight CI And Release Gate Coverage

### 목표

PR마다 실행할 수 있는 schema/docs/CLI 중심의 lightweight gate를 명확히 분리하고, real corpus/RAG/benchmark 같은 무거운 검증은 release/manual gate로 유지한다.

### 구현 결과

- GitHub Actions CI에 `Schema contract`와 `Docs/output contract` 단계를 추가해 전체 pytest 전에 public schema와 문서 계약을 빠르게 확인한다.
- `scripts/run_release_gates.py`에 optional `ci-lightweight` gate를 추가했다.
- `ci-lightweight` gate는 schema check, docs/output contract pytest, CLI smoke를 순서대로 실행하고 `release_gate_report.json`에 각 command status를 남긴다.
- README에 `--gates ci-lightweight` 실행 예시와 GitHub Actions CI의 lightweight 검증 구성을 문서화했다.
- Q95를 active backlog/development specs에서 제거하고 archive로 이동했으며, README의 active backlog 상태를 Q96-Q97로 갱신했다.

### 검증

- `.venv311/bin/python -m pytest tests/test_quality_gate_scripts.py tests/test_docs_examples.py -q`
- `.venv311/bin/python scripts/run_release_gates.py --output-dir /tmp/pdf2md-ci-lightweight --gates ci-lightweight`
- `git diff --check`
- `.venv311/bin/python -m pytest`

## P0 / Q94. Warning And Reason Taxonomy Contract

### 목표

warning code별 domain, default severity, exit-code 영향 정책을 한 곳에서 관리해 CLI, GUI summary, report summary, release gate가 같은 warning 의미 체계를 사용하게 한다. 기존 warning code 문자열과 public JSON schema는 backward-compatible하게 유지한다.

### 구현 결과

- `WarningDomain`, `WarningSeverity`, `WarningCodeSpec`, `WARNING_CODE_REGISTRY`를 추가해 known warning code의 domain/severity/exit-code metadata를 고정했다.
- `reporting.is_advisory_warning`, OCR warning count, conversion status 결정이 warning taxonomy metadata를 우선 사용하게 했다.
- blank-page `OCR_EMPTY_RESULT`처럼 context-sensitive advisory 판정은 기존 보수 정책을 유지했다.
- unknown warning은 actionable로 분류될 수 있지만 exit code에는 직접 영향을 주지 않도록 기존 prefix 기반 partial-success 동작을 보존했다.
- README와 `docs/OUTPUT_SCHEMA.md`에 warning taxonomy/exit-code 정책을 문서화했다.
- Q94를 active backlog/development specs에서 제거하고 archive로 이동했으며, README의 active backlog 상태를 Q95-Q97로 갱신했다.

### 검증

- `.venv311/bin/python -m pytest tests/test_pipeline_reporting.py tests/test_output_schema_contract.py tests/test_gui_runner.py -q`
- `.venv311/bin/python scripts/export_output_schema.py --check`
- `.venv311/bin/python -m pdf2md --help`
- `git diff --check`
- `.venv311/bin/python -m pytest`

## P0 / Q93. Pipeline Stage And Output Responsibility Split

### 목표

`pdf2md.pipeline`에 집중된 debug/RAG sidecar writing과 table-quality report helper 책임을 별도 모듈로 분리해, 이후 warning taxonomy와 CI gate 변경의 회귀 범위를 줄인다. public output schema와 deterministic output은 유지한다.

### 구현 결과

- `pdf2md.output_writers`를 추가해 debug artifact, RAG table/text/semantic/figure/domain/requirement/technical sidecar writing을 pipeline에서 분리했다.
- `pdf2md.table_quality`를 추가해 table fallback reason count, low-quality/actionable table 계산, debug table-quality review pack 생성을 독립 helper로 이동했다.
- `pdf2md.pipeline`은 기존 orchestration과 stage duration 기록을 유지하면서 새 helper를 호출하도록 정리했다.
- Q92와 Q93을 active backlog/development specs에서 제거하고 archive로 이동했으며, README의 active backlog 상태를 Q94-Q97로 갱신했다.

### 검증

- `.venv311/bin/python -m pytest tests/test_pipeline_reporting.py tests/test_golden_corpus.py -q`
- `.venv311/bin/python -m pytest`
- `git diff --check`

## P0 / Q92. Active Backlog And Local Artifact Hygiene

### 목표

Q91 완료 후 비어 있던 active backlog를 Q92-Q97 실행 계획으로 다시 열고, `tasks.md`의 M01-M05 유지보수 항목과 새 Q 작업의 관계를 명확히 한다. 또한 local conversion artifact가 패키지 소스 트리 아래에서 리뷰/검색/패키징 노이즈가 되지 않도록 정책을 고정한다.

### 구현 결과

- `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에 Q92-Q97 active backlog를 추가했다.
- `docs/QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md`에 Q92-Q97 개발 명세를 작성했다.
- `tasks.md`에서 M01-M05와 Q92-Q97의 대응 관계를 명시했다.
- README에 local conversion artifact 위치 정책을 추가하고, `.gitignore`에 `output/`, `<pdf_stem>_output/`, `pdf2md/nvme_cmds/` ignore 규칙을 추가했다.
- 문서 계약 테스트가 active backlog와 local artifact hygiene 정책을 확인하도록 갱신했다.

### 검증

- `.venv311/bin/python -m pytest tests/test_docs_examples.py -q`
- `git diff --check`
- `.venv311/bin/python -m pytest`

## P0 / Q91. Q90 Output Schema Contract Alignment

### 목표

Q90 구현 후 실제 `cross_refs_rag.jsonl` 산출물 계약과 사용자 문서가 서로 어긋나는 부분이 없는지 점검한다. 특히 fallback target id와 classification reason 계약을 public output schema에 명시한다.

### 구현 결과

- `docs/OUTPUT_SCHEMA.md`의 `cross_refs_rag.jsonl` 정책에 `pdf-outline-`/`pdf-list-` fallback `target_ref` 계약을 추가했다.
- `target_source_pdf_outline`, `target_source_pdf_list` classification reason이 provenance hint이며 Markdown 본문에 생성 텍스트를 추가하지 않는다는 점을 명시했다.
- 외부 문서 참조와 local target이 아닌 용어성 label은 unresolved local cross-ref로 내보내지 않고 skip될 수 있음을 문서화했다.
- README의 RAG sidecar 설명과 문서 계약 테스트를 Q90 구현 결과에 맞게 갱신했다.

### 검증

- `python3 -m pytest tests/test_docs_examples.py`
- `python3 scripts/export_output_schema.py --check`
- `git diff --check`
- `git diff --cached --check`

## P0 / Q90. Cross Reference Target Index Expansion

### 목표

최신 NVMe Base Specification 2.3 전체 변환에서 약 69.5%에 머문 `cross_ref_resolved_coverage`를 높인다. 원문 텍스트나 Markdown 본문은 바꾸지 않고, PDF outline/list fallback과 보수적 reference filtering만으로 local RAG sidecar의 target 해석 정확도를 개선한다.

### 구현 결과

- PDF outline/bookmark에서 numeric section과 appendix label을 추출해 semantic layer target map에 fallback으로 병합했다.
- 기존 extracted heading/caption/table target을 우선하고, outline/list fallback target은 `target_source_pdf_outline`, `target_source_pdf_list` classification reason으로 구분했다.
- List of Figures/Table entries를 figure/table target fallback으로 인식해 본문 caption target 누락을 보강했다.
- `sections 3.6.1 and 3.6.2` 같은 복수 section reference를 개별 cross-ref로 분리하고, `Figure 23Figure` 같은 붙은 label은 보수적으로 정규화했다.
- `Register command`, `register shall ...` 같은 일반 prose는 register cross-ref에서 제외하고, 실제 register identifier/target이 있는 경우만 보존했다.
- `RFC ... Appendix`, `section ... of RFC ...`, `MSI-X Table BIR`처럼 외부 문서 또는 용어성 table label은 local unresolved cross-ref로 남기지 않는다.
- reference key normalization에 bounded LRU cache를 추가해 outline target 확장 후에도 대형 semantic pass를 빠르게 유지했다.

### 검증

- `python3 -m pytest tests/test_rag_semantics.py`
- 최신 NVMe Base Specification 2.3 기존 full conversion artifact를 current Q90 semantic layer로 local-only replay:
  - outline targets: 940
  - semantic replay time: 0.691s
  - `cross_ref_record_count=2341`
  - `unresolved_cross_ref_count=18`
  - `cross_ref_resolved_coverage=0.9923`
- 대형 full preset runner는 같은 PDF에서 장시간 실행되어 중단했으며, raw PDF/text artifact는 커밋하지 않는다.

## P0 / Q89. Real Corpus Preset Evaluation And Score Gate

### 목표

GUI에서 수행하던 `rag_optimized`와 `technical_spec_rag` 비교를 반복 가능한 local-only runner로 고정한다. 실제 corpus 원문을 커밋하지 않고 preset별 score, gate condition, artifact 차이만 sanitized evidence로 남긴다.

### 구현 결과

- `scripts/run_preset_eval.py`를 추가해 preset별 변환, artifact/index/provenance validation, 선택적 SSD contract/RAG eval, 100점 score 산정을 수행한다.
- 출력은 `preset_eval_report.json`, `preset_artifact_comparison.json`, `preset_scorecard.md`로 고정했다.
- `rag_optimized`와 `technical_spec_rag`는 서로 다른 score model과 gate를 사용한다.
- `preset_artifact_comparison.json`은 artifact 존재/크기/record count와 주요 metric delta만 저장하고 raw PDF text, table body, image content를 복사하지 않는다.
- `scripts/run_release_gates.py --gates preset-eval` optional gate를 추가하고 RAG threshold와 min score를 전달할 수 있게 했다.
- RAG indexer/GUI 문서에 preset scorecard 사용법과 release gate 예시를 추가했다.

### 검증

- `python3 -m pytest`
- `python3 scripts/export_output_schema.py --check`
- `git diff --check`
- `git diff --cached --check`
- `python3 scripts/run_preset_eval.py --help`
- `python3 scripts/run_preset_eval.py --input-pdf pdf/NVM-Express-Key-Value-Command-Set-Specification-1.0d-2024.01.03-Ratified.pdf --output-root /private/tmp/pdf2md-preset-eval-smoke2 --presets rag_optimized,technical_spec_rag --domain-adapter nvme --pages 1`
- `python3 scripts/run_release_gates.py --output-dir /private/tmp/pdf2md-release-preset-smoke2 --gates preset-eval --preset-eval-input-pdf pdf/NVM-Express-Key-Value-Command-Set-Specification-1.0d-2024.01.03-Ratified.pdf --preset-eval-output-root /private/tmp/pdf2md-release-preset-smoke2/eval --preset-eval-presets rag_optimized --preset-eval-pages 1 --preset-eval-min-score 80`
- GitHub CI: `test (3.11)`, `test (3.14)`

## P0 / Q88. Storage And Security Domain Adapter Expansion

### 목표

Storage/security spec corpus에서 NVMe/PCIe/OCP/TCG/SPDM 계열 table shape를 더 명확히 domain unit으로 분리하고, SPDM을 first-class adapter로 지원한다.

### 구현 결과

- `DomainAdapterMode.SPDM = "spdm"`을 추가하고 CLI/GUI/domain combo/docs/schema 계약에 반영했다.
- SPDM unit type으로 `spdm_message`, `spdm_request_response`, `spdm_measurement`, `spdm_certificate`, `spdm_algorithm`, `spdm_key_exchange`, `spdm_session`을 추가했다.
- TCG unit type을 `security_provider`, `locking_range`, `key_management`, `session_state`까지 확장했다.
- `domain_unit` retrieval priority를 높여 기술/security 질의에서 source_refs가 더 잘 노출되게 했다.
- SSD contract validator에 `spdm -> HIL/SPDM` mapping과 SPDM first-class validation을 추가했다.
- RAG domain adapter, chunk, SSD contract tests와 user docs를 갱신했다.

### 검증

- `python3 -m pytest`
- `python3 -m pytest tests/test_rag_domain_adapters.py tests/test_ssd_rag_contract.py tests/test_rag_chunks.py`
- `python3 scripts/export_output_schema.py --check`
- `git diff --check`
- `git diff --cached --check`
- `python3 -m pdf2md --help`
- GitHub CI: `test (3.11)`, `test (3.14)`

## P0 / Q87. Technical Spec RAG Preset Domain Profile UX

### 목표

`technical_spec_rag`가 `rag_optimized`와 동일 산출물만 만드는 상태를 해소하고, CLI/GUI에서 storage/security domain adapter 선택을 명확히 연결한다.

### 구현 결과

- `Config`, CLI, batch, GUI options, manifest/report 경로에 `rag_profile` 계약을 명시적으로 전달했다.
- `technical_spec_rag`에서 `domain_adapter=none`이면 advisory warning `TECHNICAL_PROFILE_DOMAIN_ADAPTER_MISSING`을 남긴다.
- strict CLI guard `--require-domain-adapter-for-technical-profile`을 추가했다.
- GUI `기술 스펙 RAG` preset에서는 domain adapter를 editable로 유지하고, `rag_optimized`는 adapter를 `none`으로 되돌리도록 했다.
- report summary에 `technical_profile_domain_adapter_missing`을 추가하고, docs/schema/tests를 갱신했다.

### 검증

- `python3 -m pytest`
- `python3 scripts/export_output_schema.py --check`
- `git diff --check`
- `git diff --cached --check`
- `python3 -m pdf2md --help`
- GitHub CI: `test (3.11)`, `test (3.14)`

## P0 / Q86. Full Technical Spec Table Quality Triage And Recovery

### 목표

기술 스펙의 복잡 표 HTML fallback과 실제 조치 필요 low-quality table을 분리하고, page/table 단위 triage evidence를 local-only로 남긴다.

### 구현 결과

- debug table quality review pack을 추가해 page/table, fallback reason, header strategy/confidence, row diagnostics, technical/domain unit count, sample row hash/preview를 기록한다.
- low-quality table을 advisory/actionable로 분리하고, source_refs/sidecar/provenance가 유지되는 표는 운영 risk로 과대 분류하지 않게 했다.
- technical table shape fixture와 RAG table/header recovery tests를 보강했다.
- raw table body 전체를 새 공유 artifact로 복사하지 않고, local debug artifact에 제한된 preview/hash만 남긴다.

### 검증

- `python3 -m pytest`
- `python3 scripts/export_output_schema.py --check`
- `git diff --check`
- `git diff --cached --check`
- GitHub CI: `test (3.11)`, `test (3.14)`

## P0 / Q85. RAG Preset Status And Warning Severity Calibration

### 목표

`rag_optimized`에서 정상적인 보수적 fallback을 failure처럼 보지 않고, 실제 운영자가 조치해야 할 warning만 actionable로 분류한다.

### 구현 결과

- warning severity taxonomy를 확장해 advisory/actionable count를 report summary에 분리했다.
- `TABLE_COMPLEXITY_HTML_FALLBACK`은 warning에는 남기되 advisory/expected fallback으로 분류했다.
- `OCR_EMPTY_RESULT`와 table low-quality 판정을 context와 actionable risk 기준으로 나누었다.
- conversion status 판정은 raw warning 수보다 actionable warning, failed page, actionable table quality를 우선 보게 했다.
- GUI summary와 docs/schema/tests를 새 warning taxonomy에 맞춰 갱신했다.

### 검증

- `python3 -m pytest`
- `python3 scripts/export_output_schema.py --check`
- `git diff --check`
- `git diff --cached --check`
- GitHub CI: `test (3.11)`, `test (3.14)`

## P0 / Q84. Release Readiness Sweep

### 목표

Q83 이후 100/100 상태의 릴리스 후보를 대상으로 local-only release readiness를 재검증한다. 새 기능 개발은 하지 않고, 현재 산출물/schema/report/RAG/index/provenance/artifact/packaging 계약이 반복 실행 가능한지 확인한다.

### 구현 결과

- 현재 로컬 상태는 Q83 merge commit `4a1033b` 기반 `main...origin/main`에서 시작했다.
- 미추적 `pdf2md/nvme_cmds/`는 사용자 산출물로 보고 건드리지 않았다.
- Q84 범위는 release gate 재현성, schema/report 계약 안정성, RAG/index/provenance/artifact local-only 검증, packaging/wheel smoke, pages/sec/stage duration 회귀 관찰로 확정했다.
- 코드 결함은 발견하지 못했고, 새 기능은 추가하지 않았다.
- 실제 NVMe `technical_spec_rag --domain-adapter nvme` 변환은 `status=success`, `warning_count=39`, `actionable_warning_count=0`, `advisory_warning_count=39`, `table_expected_fallback_count=39`, `table_low_quality_count=0`, `pages_per_second=0.9166`, `image_extraction=24417ms`, `retrieval_chunk_record_count=655`, `cross_ref_record_count=27`, `unresolved_cross_ref_count=0`을 기록했다.
- corpus release gate는 `partial_success_rate=0.0`, `low_quality_table_rate=0.0`, `pages_per_second_min=0.903`, `table_total=52`, `table_low_quality_count=0`으로 통과했다.
- RAG release gate는 hit@k/MRR/source/requirement/table-field/cross-ref/relationship coverage 1.0, `chunk_token_p95=140`, `chunk_token_max=510`, `conversion_duration_ms=27273`, duplicate source ratio 0.0으로 통과했다.
- index contract validator는 `checked_records=1599`, `warning_count=0`, `error_count=0`으로 통과했다.
- provenance integrity validator는 `checked_records=1597`, `checked_source_refs=1558`, `unresolved_source_refs=0`, `warning_count=0`, `error_count=0`으로 통과했다.
- artifact integrity validator는 `checked_assets=12`, `checked_links=6`, `missing_assets=0`, `orphan_assets=0`, `sidecar_count_mismatches=0`, `warning_count=0`, `error_count=0`으로 통과했다.
- packaging gate는 wheel build, wheel contract, CLI module help, GUI module help 4개 command가 모두 통과했고, `wheel_contract_report.json`은 `check_count=9`, `failed_count=0`을 기록했다.
- wheel smoke는 dependency가 없는 완전 격리 venv에서는 `pydantic` 미설치로 실패했다. 이는 코드 결함이 아니라 offline dependency wheelhouse가 없는 환경 한계로 분류했고, 기존 `.venv311` 의존성을 복사한 `/private/tmp` venv에 built wheel을 재설치한 뒤 `python -m pdf2md --help`, `pdf2md --help`, `pdf2md-gui --help`가 모두 통과함을 확인했다.
- benchmark gate는 synthetic 10/50/100 page에서 각각 `pages_per_second=49.0158/49.4252/47.7763`, `pdf_open_count=2`, regression 없음으로 통과했다.

### 검증

- `.venv311/bin/python -m pytest` 초기 실행: 301 passed, 1 failed
  - 실패 원인: Q84를 active backlog/spec에 올린 중간 상태에서 `tests/test_docs_examples.py::test_ci_and_next_plan_contracts_are_present`가 기존 "active backlog 없음" 계약을 기대했다.
  - 분류: 문서/test contract 중간 상태 문제. Q84 완료 archive 반영 후 active backlog/spec를 비우고 재실행 대상으로 정리했다.
- `.venv311/bin/python -m pytest tests/test_docs_examples.py`: 6 passed
- `.venv311/bin/python -m pytest`: 302 passed
- `.venv311/bin/python -m pdf2md --help`
- `.venv311/bin/python scripts/export_output_schema.py --check`
- `.venv311/bin/python -m pdf2md pdf/NVM-Express-Key-Value-Command-Set-Specification-1.0d-2024.01.03-Ratified.pdf -o /private/tmp/pdf2md-q84-release-real-out --rag-profile technical_spec_rag --domain-adapter nvme`
- `.venv311/bin/python scripts/run_rag_eval.py --output-dir /private/tmp/pdf2md-q84-release-real-out --eval-set /private/tmp/pdf2md-quality-20260521/nvme_rag_eval_queries.json --top-k 5 --report-path /private/tmp/pdf2md-q84-rag-eval-report.json --min-hit-at-k 1.0 --min-mrr 0.8 --min-expected-source-coverage 0.9 --min-requirement-coverage 1.0 --min-table-field-coverage 0.85 --min-cross-ref-resolved-coverage 0.85 --min-chunk-size-compliance 0.95 --min-source-ref-presence-coverage 1.0 --max-chunk-token-p95 512 --max-chunk-token-max 768 --max-duplicate-source-ratio 0 --max-conversion-duration-ms 80000 --fail-on-threshold`
- `.venv311/bin/python scripts/run_release_gates.py --output-dir /private/tmp/pdf2md-q84-release-rag-integrity --gates rag,index-contract,provenance-integrity,artifact-integrity --rag-output-dir /private/tmp/pdf2md-q84-release-real-out --rag-eval-set /private/tmp/pdf2md-quality-20260521/nvme_rag_eval_queries.json --rag-top-k 5 --rag-min-hit-at-k 1.0 --rag-min-mrr 0.8 --rag-min-expected-source-coverage 0.9 --rag-min-requirement-coverage 1.0 --rag-min-table-field-coverage 0.85 --rag-min-cross-ref-resolved-coverage 0.85 --rag-min-relationship-target-coverage 1.0 --rag-max-chunk-token-p95 512 --rag-max-chunk-token-max 768 --rag-max-conversion-duration-ms 80000 --index-contract-output-dir /private/tmp/pdf2md-q84-release-real-out --provenance-integrity-output-dir /private/tmp/pdf2md-q84-release-real-out --provenance-integrity-fail-on-warning --artifact-integrity-output-dir /private/tmp/pdf2md-q84-release-real-out --artifact-integrity-fail-on-warning`
- `.venv311/bin/python scripts/run_release_gates.py --output-dir /private/tmp/pdf2md-q84-release-core --gates ocr,corpus,benchmark,schema,packaging --corpus-input-dir pdf --max-partial-rate 0.0 --max-low-quality-table-rate 0.0 --corpus-min-pages-per-second 0.7 --benchmark-page-counts 10,50,100 --benchmark-page-workers 1`
- `/private/tmp/pdf2md-q84-wheel-venv-full/bin/python -m pdf2md --help`
- `/private/tmp/pdf2md-q84-wheel-venv-full/bin/pdf2md --help`
- `/private/tmp/pdf2md-q84-wheel-venv-full/bin/pdf2md-gui --help`

### 비범위

- 변환 heuristic, RAG ranking, schema field, threshold 정책 신규 추가
- 외부 RAG/indexing service 호출
- 원문 텍스트/표/이미지/OCR 결과 보정
- dependency wheelhouse 없는 완전 오프라인 fresh venv 구성

### 후속 후보

현재 즉시 열 코드 결함은 없다. 완전 오프라인 wheel 설치 검증이 릴리스 절차에 필요해지면 dependency wheelhouse 준비와 fresh venv install smoke를 별도 packaging backlog로 분리한다.

## P0 / Q83. Real Corpus Cross Reference Precision

### 목표

NVMe real corpus에서 unresolved cross-ref false positive를 줄이고 RAG citation/source coverage gate의 안정성을 높인다. `Table of Figures`, `section defines`, generic `register level interface`처럼 target label이 부족한 문구는 cross-ref record로 만들지 않고, 명확한 Figure/Table/Section/technical ref resolution은 유지한다.

### 구현 결과

- unresolved `Section|Clause|Table|Figure` 후보가 숫자 또는 명확한 짧은 대문자 식별자 형태가 아니면 cross-ref record에서 제외한다.
- `of`, `in`, `defines`, `specifies`처럼 일반 문장 연결어가 target label로 잡히는 경우를 차단했다.
- generic `register level interface`류 register 후보를 technical cross-ref에서 제외한다.
- resolved target은 기존처럼 유지하므로 실제 target이 있는 `Section 1`, `Table 1` 등은 영향을 받지 않는다.
- `tests/test_rag_semantics.py`에 false positive 억제 synthetic fixture를 추가했다.

### 검증

- `.venv311/bin/python -m pytest tests/test_rag_semantics.py`
- 실제 NVMe `technical_spec_rag --domain-adapter nvme` 기준 `cross_ref_record_count=27`, `unresolved_cross_ref_count=0`, `cross_ref_resolved_coverage=1.0`
- 같은 실제 출력에서 `document.md` SHA-256은 Q82 출력과 동일
- `.venv311/bin/python scripts/run_rag_eval.py --output-dir /private/tmp/pdf2md-q83-real-out --eval-set /private/tmp/pdf2md-quality-20260521/nvme_rag_eval_queries.json --top-k 5 --min-hit-at-k 1.0 --min-mrr 0.8 --min-expected-source-coverage 0.9 --min-requirement-coverage 1.0 --min-table-field-coverage 0.85 --min-cross-ref-resolved-coverage 0.85 --min-chunk-size-compliance 0.95 --min-source-ref-presence-coverage 1.0 --max-chunk-token-p95 512 --max-chunk-token-max 768 --max-duplicate-source-ratio 0 --max-conversion-duration-ms 80000 --fail-on-threshold`
- `.venv311/bin/python scripts/run_release_gates.py --output-dir /private/tmp/pdf2md-q83-release-rag --gates rag --rag-output-dir /private/tmp/pdf2md-q83-real-out --rag-eval-set /private/tmp/pdf2md-quality-20260521/nvme_rag_eval_queries.json --rag-top-k 5 --rag-min-hit-at-k 1.0 --rag-min-mrr 0.8 --rag-min-expected-source-coverage 0.9 --rag-min-requirement-coverage 1.0 --rag-min-table-field-coverage 0.85 --rag-min-cross-ref-resolved-coverage 0.85 --rag-min-relationship-target-coverage 1.0 --rag-max-chunk-token-p95 512 --rag-max-chunk-token-max 768 --rag-max-conversion-duration-ms 80000`
- `.venv311/bin/python scripts/validate_index_contract.py --output-dir /private/tmp/pdf2md-q83-real-out --target all --fail-on-error`

### 비범위

- 외부 RAG/indexer service 호출은 수행하지 않았다.
- 번호가 없는 외부 문서의 prose reference를 임의 target으로 보정하지 않는다.

## P0 / Q82. Expected Table Fallback Severity Taxonomy

### 목표

의도된 HTML fallback warning과 실제 변환 실패를 분리해 real corpus gate의 partial success 신호를 더 유용하게 만든다. 복잡 표를 HTML fallback으로 보내는 보수 동작은 report에 계속 남기되, 그것만으로 actionable failure나 `partial_success`가 되지 않게 한다.

### 구현 결과

- `TABLE_COMPLEXITY_HTML_FALLBACK`을 advisory warning으로 분류했다.
- `report.summary.actionable_warning_count`, `advisory_warning_count`, `table_expected_fallback_count`, `table_expected_fallback_reason_counts`, `table_actionable_fallback_count`를 추가했다.
- page/document status 판정은 advisory warning을 제외하고, `TABLE_EXTRACTION_FAILED`, OCR/image failure, 저품질 표는 기존처럼 partial success로 남긴다.
- Markdown warning comment와 `report.warnings[]`, `table_fallbacks`, `table_fallback_reason_counts`는 보존한다.
- report public schema와 README/Windows/GUI 문서를 새 taxonomy에 맞춰 갱신했다.

### 검증

- `.venv311/bin/python -m pytest tests/test_pipeline_reporting.py tests/test_rag_tables.py tests/test_page_workers.py`
- `.venv311/bin/python -m pytest tests/test_golden_corpus.py`
- `.venv311/bin/python scripts/export_output_schema.py --check`
- 실제 NVMe `technical_spec_rag --domain-adapter nvme` 기준 `status=success`, `partial_success=false`, `warning_count=39`, `advisory_warning_count=39`, `actionable_warning_count=0`, `table_expected_fallback_count=39`, `table_low_quality_count=0`
- 같은 실제 출력에서 `document.md`와 `retrieval_chunks_rag.jsonl` SHA-256은 Q81 출력과 동일
- `.venv311/bin/python scripts/run_release_gates.py --output-dir /private/tmp/pdf2md-q82-release-corpus --gates corpus --corpus-input-dir pdf --max-partial-rate 0.0 --max-low-quality-table-rate 0.0 --corpus-min-pages-per-second 0.7`
- `.venv311/bin/python scripts/validate_index_contract.py --output-dir /private/tmp/pdf2md-q82-real-out --target all --fail-on-error`

### 비범위

- cross-reference false positive/coverage 개선은 Q83에서 후속 처리했다.

## P0 / Q81. Structure Marker OCR Early Stop And Cache

### 목표

Q80 이후에도 실제 NVMe Key Value Command Set PDF에서 `image_extraction`이 70초 이상으로 남아 있었다. 구조 마커 OCR의 정확도와 deterministic output을 유지하면서 OCR 후보 수집 호출 수를 더 줄인다.

### 구현 결과

- child heading context로 기대 가능한 section marker가 있는 경우 high-confidence OCR 후보에서 즉시 early stop한다.
- 동일 원본 image SHA-256, variant key, PSM 조합의 `image_to_data` 결과를 변환 실행 내 cache로 재사용한다.
- child context가 없더라도 일정 관측 수 이후 단일 exact/context-normalized marker가 충분한 vote/confidence margin으로 안정화되면 나머지 scale/PSM 조합을 생략한다.
- ambiguous 후보는 끝까지 수집하도록 vote margin guardrail을 둔다.
- 새 public JSON schema는 추가하지 않고 기존 `summary.stage_durations_ms.image_extraction`과 `summary.pages_per_second`로 성능을 측정한다.

### 검증

- `.venv311/bin/python -m pytest tests/test_images.py`
- `.venv311/bin/python -m pytest tests/test_pipeline_reporting.py tests/test_cli.py`
- `main` baseline worktree와 현재 브랜치에서 같은 실제 NVMe command를 실행해 `document.md` SHA-256 동일 확인
- 같은 비교에서 `retrieval_chunks_rag.jsonl` SHA-256 동일 확인
- 실제 NVMe `technical_spec_rag --domain-adapter nvme` 기준:
  - baseline: `pages_per_second=0.3166`, `image_extraction=75989ms`, structure marker recovered `20`, suppressed `0`, retrieval chunks `662`
  - Q81: `pages_per_second=0.8951`, `image_extraction=24922ms`, structure marker recovered `20`, suppressed `0`, retrieval chunks `662`

### 비범위

- expected HTML fallback warning과 partial success 정책 정리는 Q81 당시 비범위였고 Q82에서 후속 처리했다.
- cross-reference false positive/coverage 개선은 Q83으로 남긴다.

## P0 / Q80. Real Corpus Structure Marker OCR And Provenance Hardening

### 목표

RAG chunk/profile 개선 후 실제 local NVMe Key Value Command Set PDF를 기준으로 corpus/RAG/release gate를 수행하고, 98/100에서 99점으로 가기 위한 명확한 병목을 작게 개선한다. 원문 텍스트, Markdown, retrieval chunk 계약은 유지하면서 구조 마커 OCR의 중복 Tesseract 호출과 excluded figure provenance warning을 줄인다.

### 구현 결과

- 구조 마커 OCR 후보 수집에서 `image_to_string`과 `image_to_data`를 중복 호출하던 경로를 `image_to_data` 단일 호출로 정리했다.
- OCR scale/PSM 조합을 상수화하고, `image_to_data`의 text/confidence payload로 기존 vote/confidence aggregation을 유지했다.
- 실제 NVMe profile 변환에서 `document.md`와 `retrieval_chunks_rag.jsonl` byte-level diff 없이 `image_extraction`이 145.2s에서 70.6s로 감소했다.
- `figures_rag.jsonl`의 `excluded_figure` self-reference를 provenance validator가 같은 `figure_id` index로 해석하도록 보강했다.
- 실제 NVMe output 기준 provenance validator `--fail-on-warning`이 warnings 0으로 통과한다.

### 검증

- `.venv311/bin/python -m pytest tests/test_images.py tests/test_provenance_integrity_validator.py -q`
- `.venv311/bin/python -m pytest`
- `.venv311/bin/python -m pdf2md --help`
- `git diff --check`
- `.venv311/bin/python scripts/run_rag_eval.py --output-dir /private/tmp/pdf2md-quality-20260521/nvme_technical_profile_after --eval-set /private/tmp/pdf2md-quality-20260521/nvme_rag_eval_queries.json --top-k 5 --min-hit-at-k 1.0 --min-mrr 0.8 --min-expected-source-coverage 0.9 --min-requirement-coverage 1.0 --min-table-field-coverage 0.85 --min-cross-ref-resolved-coverage 0.75 --min-chunk-size-compliance 0.95 --min-source-ref-presence-coverage 1.0 --max-chunk-token-p95 512 --max-chunk-token-max 768 --max-duplicate-source-ratio 0 --max-conversion-duration-ms 80000 --fail-on-threshold`
- `.venv311/bin/python scripts/run_release_gates.py --output-dir /private/tmp/pdf2md-quality-20260521/release_core --gates corpus,schema,index-contract,provenance-integrity,artifact-integrity --corpus-input-dir pdf --max-partial-rate 1.0 --max-low-quality-table-rate 0.0 --corpus-min-pages-per-second 0.3 --index-contract-output-dir /private/tmp/pdf2md-quality-20260521/nvme_technical_profile_after --provenance-integrity-output-dir /private/tmp/pdf2md-quality-20260521/nvme_technical_profile_after --artifact-integrity-output-dir /private/tmp/pdf2md-quality-20260521/nvme_technical_profile_after`
- `.venv311/bin/python scripts/run_release_gates.py --output-dir /private/tmp/pdf2md-quality-20260521/release_integrity_after_fix --gates schema,index-contract,provenance-integrity,artifact-integrity --index-contract-output-dir /private/tmp/pdf2md-quality-20260521/nvme_technical_profile_after --provenance-integrity-output-dir /private/tmp/pdf2md-quality-20260521/nvme_technical_profile_after --provenance-integrity-fail-on-warning --artifact-integrity-output-dir /private/tmp/pdf2md-quality-20260521/nvme_technical_profile_after`

### 비범위

- 구조 마커 OCR early stop/cache 추가 최적화는 Q80 당시 비범위였고 Q81에서 후속 처리했다.
- expected HTML fallback warning과 partial success 정책 정리는 Q80 당시 비범위였고 Q82에서 후속 처리했다.
- cross-reference false positive/coverage 개선은 Q83으로 남긴다.

## P1 / Q72. Shared Batch Runner And GUI Batch Artifact Parity

### 목표

CLI batch와 GUI folder mode가 같은 batch/corpus artifact 계약을 공유하도록 batch 실행 로직을 공용 모듈로 분리한다. GUI batch에서도 기존 public output인 `batch_report.json`, `corpus_manifest.json`을 생성하되 새 public JSON schema는 만들지 않는다.

### 구현 결과

- `pdf2md/batch_runner.py`를 추가해 input folder validation, deterministic PDF ordering, duplicate stem detection, document output naming, skip-existing, partial/failed aggregation, batch/corpus artifact 생성을 공용화했다.
- `pdf2md/cli.py`의 batch mode는 공용 `run_batch_conversion()`을 호출하도록 변경해 기존 CLI output schema와 exit code 계약을 유지했다.
- `pdf2md/gui_runner.py`의 folder mode도 같은 batch runner를 호출하도록 변경하고, GUI summary에 `batch_report_path`, `corpus_manifest_path`, optional diff/impact report path를 보존한다.
- GUI cancel/retry candidate semantics는 document-level event wrapper에서 유지한다.
- GUI batch가 작성한 `batch_report.json`, `corpus_manifest.json`이 CLI batch와 같은 핵심 normalized contract를 갖는지 테스트로 고정했다.

### 검증

- `.venv311/bin/python -m pytest tests/test_gui_runner.py tests/test_cli.py`
- `.venv311/bin/python -m pytest tests/test_docs_examples.py`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- GUI previous corpus manifest UI 추가는 Q73 범위로 남긴다.
- CLI/GUI single-output golden parity gate는 Q74 범위로 남긴다.
- page-level progress와 metrics 표시는 Q75 범위로 남긴다.
- performance benchmark report는 Q76 범위로 남긴다.

## P1 / Q73. GUI Incremental Corpus Options

### 목표

CLI의 `--previous-corpus-manifest`, `--reuse-unchanged` 기능을 GUI folder mode에서도 사용할 수 있게 한다. GUI batch 결과에서 `corpus_diff_report.json`, `requirement_change_impact_report.json`을 확인할 수 있게 하되, previous manifest path는 profile/recent state에 저장하지 않는다.

### 구현 결과

- `GuiConversionRequest`에 `previous_corpus_manifest`, `reuse_unchanged`를 추가하고 Q72 shared batch runner의 `BatchConversionOptions`로 전달한다.
- `validate_gui_request()`가 previous manifest/reuse pair, folder-mode only contract, missing/non-JSON manifest를 구조화된 diagnostic으로 검증한다.
- GUI 화면에 `Previous corpus manifest` file picker와 `Reuse unchanged` toggle을 추가했다.
- GUI 결과 action에 `Open Corpus Manifest`, `Open Corpus Diff`, `Open Requirement Impact`를 추가했다.
- GUI profile forbidden fields에 previous manifest path 계열을 추가해 profile export/import가 path를 저장하지 않도록 고정했다.
- GUI incremental batch가 CLI와 같은 skipped/reuse summary와 diff/impact summary를 생성하는지 테스트로 검증했다.

### 검증

- `.venv311/bin/python -m pytest tests/test_gui_runner.py tests/test_gui_profiles.py tests/test_gui_layout.py tests/test_gui_i18n.py`
- `.venv311/bin/python -m pytest tests/test_cli.py`
- `.venv311/bin/python -m pytest tests/test_docs_examples.py`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- cloud corpus sync는 구현하지 않는다.
- previous manifest path를 profile/recent state에 저장하지 않는다.
- real private corpus 네트워크 검증은 포함하지 않는다.
- 새 public output schema는 추가하지 않는다.

## P1 / Q74. CLI/GUI Golden Parity Gate

### 목표

같은 synthetic PDF와 같은 옵션에서 CLI와 GUI headless runner가 동일 산출물을 생성하는지 자동 검증한다. GUI가 CLI와 같은 core pipeline을 호출한다는 계약을 release 전 optional gate로 회귀 방어하되, parity report는 local-only 검증 artifact로 유지한다.

### 구현 결과

- `scripts/run_gui_cli_parity.py`를 추가해 deterministic single-page PDF fixture를 생성하고 CLI와 GUI headless runner를 같은 옵션으로 실행한다.
- Markdown, manifest, report, RAG sidecar를 normalized SHA-256으로 비교하며, timing/duration 계열 dynamic JSON field는 hash 계산에서 제외한다.
- report에는 raw PDF/Markdown 본문을 저장하지 않고 artifact 이름, 존재 여부, normalized hash, match/mismatch summary만 기록한다.
- `scripts/run_release_gates.py`에 optional `gui-parity` gate를 추가해 `release_gate_output/gui-parity/gui_cli_parity_report.json`을 기록한다.
- mismatch 또는 missing artifact가 있으면 parity script와 release gate 모두 실패로 처리한다.
- 새 public output schema는 추가하지 않았고 `gui_cli_parity_report.json`은 local-only release 검증 artifact로 유지했다.

### 검증

- `.venv311/bin/python -m pytest tests/test_quality_gate_scripts.py tests/test_gui_runner.py`
- `.venv311/bin/python scripts/run_gui_cli_parity.py --output-dir /private/tmp/pdf2md-gui-cli-parity`
- `.venv311/bin/python scripts/run_release_gates.py --output-dir /private/tmp/pdf2md-q74-gates --gates gui-parity`
- `.venv311/bin/python -m pytest tests/test_docs_examples.py`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- real private corpus parity gate는 포함하지 않는다.
- visual GUI automation은 포함하지 않는다.
- 성능 pass/fail threshold는 Q76 범위로 남긴다.
- public output schema는 추가하지 않는다.

## P2 / Q75. GUI Metrics And Page Progress Contract

### 목표

GUI에서 CLI 운영자가 확인하는 수준의 elapsed time, page throughput, document/status/retry count를 summary/log로 확인할 수 있게 한다. 단일 PDF 진행률은 pipeline에서 실제 page progress event가 올 때만 percent로 전환하고, 폴더 배치는 기존 document-level percent와 혼동하지 않게 유지한다.

### 구현 결과

- `pdf2md/pipeline.py`에 observer-only `ConversionProgressEvent`와 `progress` callback을 추가했다. callback은 page selection과 normalization page start/finish 이벤트만 전달하며 core extraction/output 결정성에는 영향을 주지 않는다.
- `pdf2md/gui_runner.py`에 `GuiPageProgress`, document-level duration/page throughput metric, summary aggregate property를 추가했다.
- `format_gui_summary()`가 `documents`, status counts, `retry_candidates`, `elapsed_ms`, `processed_pages`, `pages_per_second`를 함께 표시한다.
- `pdf2md/gui.py`는 단일 PDF에서 page finish 이벤트가 들어올 때만 progress bar를 determinate percent로 전환한다. 폴더 배치 진행률은 계속 document-level `batch_progress` label을 사용한다.
- `pdf2md/gui_i18n.py`, `pdf2md/gui_layout.py`에 page progress label contract를 추가했다.
- 새 public output schema는 추가하지 않았다.

### 검증

- `.venv311/bin/python -m pytest tests/test_gui_runner.py tests/test_gui_layout.py tests/test_gui_i18n.py`
- `.venv311/bin/python -m pytest tests/test_pipeline_smoke.py`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- page 내부 fine-grained extractor progress는 포함하지 않는다.
- 성능 최적화 자체는 포함하지 않는다.
- native GUI visual screenshot automation은 포함하지 않는다.
- public output schema는 추가하지 않는다.

## P2 / Q76. CLI/GUI Performance Benchmark Report

### 목표

CLI와 GUI headless runner의 실행 시간을 같은 deterministic synthetic fixture와 같은 옵션으로 비교하고, output hash equality와 성능 값을 local-only benchmark report로 기록한다. 기본 정책은 advisory이며, 명시 threshold와 `--fail-on-regression`이 함께 제공될 때만 성능 회귀를 실패로 처리한다.

### 구현 결과

- `scripts/benchmark_gui_cli_parity.py`를 추가해 deterministic multi-page PDF fixture를 생성하고 CLI와 GUI headless runner를 같은 page range/marker 옵션으로 실행한다.
- `gui_cli_benchmark_report.json`에는 CLI/GUI elapsed ms, pages/sec, GUI duration ratio, output hash equality, optional threshold/advisory policy 결과를 기록한다.
- Q74의 normalized artifact comparison helper를 재사용해 Markdown, manifest, report, RAG sidecar hash equality를 함께 검증한다.
- `scripts/run_release_gates.py`에 optional `gui-benchmark` gate를 추가해 `release_gate_output/gui-benchmark/gui_cli_benchmark_report.json`을 기록한다.
- report는 raw PDF/Markdown 본문을 저장하지 않는 local-only 검증 artifact이며 새 public output schema는 추가하지 않았다.
- Q76 완료 후 active backlog와 active development specs는 없음 상태로 전환했다.

### 검증

- `.venv311/bin/python -m pytest tests/test_quality_gate_scripts.py`
- `.venv311/bin/python scripts/benchmark_gui_cli_parity.py --output-dir /private/tmp/pdf2md-gui-cli-benchmark`
- `.venv311/bin/python scripts/run_release_gates.py --output-dir /private/tmp/pdf2md-q76-benchmark --gates gui-benchmark`
- `.venv311/bin/python -m pytest tests/test_docs_examples.py`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- GUI rendering/frame-rate benchmark는 포함하지 않는다.
- OS-level click automation은 포함하지 않는다.
- hard performance threshold를 baseline 없이 강제하지 않는다.
- public output schema는 추가하지 않는다.

## P1 / Q34. Offline Index Contract Validator

### 목표

`pdf2md`가 생성한 RAG sidecar를 OpenAI Vector Store/generic embedding pipeline, Azure AI Search, LangChain, LlamaIndex mapping recipe에 넣기 전에 local-only로 검증하는 validator를 추가한다.
검증은 외부 네트워크나 실제 indexer 호출 없이 수행하며, 실패 위치를 deterministic JSON report로 남긴다.

### 사용자 가치

- 운영자가 `retrieval_chunks_rag.jsonl`과 관련 sidecar를 업로드하기 전에 field 누락, 타입 불일치, metadata 과대, source provenance 손실을 빠르게 발견한다.
- confidential-safe 공유 모드에서 path, filename, source hash 같은 민감 metadata가 노출되는지 사전 점검한다.
- RAG adapter별 mapping recipe가 문서에만 머무르지 않고 CI에서 검증 가능한 계약이 된다.

### 입력

- 기본 입력: `--output-dir`로 지정한 단일 변환 산출물 디렉터리
- 필수 검증 대상: `retrieval_chunks_rag.jsonl`
- 선택 검증 대상:
  - `text_blocks_rag.jsonl`
  - `semantic_units_rag.jsonl`
  - `requirements_rag.jsonl`
  - `cross_refs_rag.jsonl`
  - `requirement_traceability_rag.jsonl`
  - `technical_tables_rag.jsonl`
  - `tables_rag.jsonl`
  - `figures_rag.jsonl`
  - `domain_units_rag.jsonl`
  - `manifest.json`
  - `report.json`

### CLI 설계

새 스크립트:

```bash
python scripts/validate_index_contract.py --output-dir output
python scripts/validate_index_contract.py --output-dir output --target openai
python scripts/validate_index_contract.py --output-dir output --target azure-ai-search
python scripts/validate_index_contract.py --output-dir output --target langchain
python scripts/validate_index_contract.py --output-dir output --target llamaindex
python scripts/validate_index_contract.py --output-dir output --target all --confidential-safe --fail-on-error
```

권장 옵션:

- `--output-dir`: 변환 산출물 디렉터리
- `--target`: `all`, `openai`, `azure-ai-search`, `langchain`, `llamaindex`
- `--report-file`: 기본값 `index_contract_report.json`
- `--confidential-safe`: confidential-safe 공유 가능 metadata만 허용하는 추가 검사
- `--metadata-max-bytes`: metadata payload 크기 제한. target별 기본값을 갖고 명시값으로 override 가능
- `--fail-on-warning`: warning이 있어도 exit code 1
- `--fail-on-error`: error가 있으면 exit code 1

### 검증 규칙

공통 record contract:

- JSONL 각 줄은 유효한 JSON object여야 한다.
- `retrieval_chunks_rag.jsonl` record는 `docs/OUTPUT_SCHEMA.md`의 required field를 포함해야 한다.
- `tables_rag.jsonl`, `technical_tables_rag.jsonl`, `requirement_traceability_rag.jsonl`도 required field와 핵심 타입을 검사한다.
- `chunk_id`, `chunk_index`, `chunk_type`, `text`, `source_refs`, `page_range`, `source_dedupe_key` 타입을 엄격히 검증한다.
- `schema_version`과 `source_sha256`은 모든 retrieval chunk에 존재해야 한다.
- `source_refs`는 비어 있으면 error다.
- `source_refs[]`의 `source_type`, `source_id`, `page`는 citation lookup에 필요한 최소 field로 취급한다.
- `page_range`는 `[start, end]` 형태의 양의 정수 배열이어야 하며 `start <= end`여야 한다.
- `token_estimate`, `char_count`, `retrieval_priority`는 정수여야 한다.

Target별 mapping contract:

- OpenAI/generic:
  - `id`, `text`, `metadata`로 매핑 가능해야 한다.
  - metadata는 JSON 직렬화 가능해야 하고 target metadata size limit을 넘으면 warning 또는 error로 분류한다.
- Azure AI Search:
  - key field `id`는 문자열이고 비어 있으면 안 된다.
  - `page_start`, `page_end`, `retrieval_priority`, `token_estimate`는 정수형 index field로 변환 가능해야 한다.
  - `semantic_types`는 문자열 collection으로 변환 가능해야 한다.
  - `source_refs_json`은 deterministic JSON string으로 직렬화 가능해야 한다.
- LangChain:
  - `page_content=record["text"]`가 빈 문자열이면 error다.
  - metadata에 들어가는 값은 JSON-serializable scalar/list/dict여야 한다.
- LlamaIndex:
  - `TextNode(id_=chunk_id, text=text, metadata=...)`로 매핑 가능해야 한다.
  - metadata key는 문자열이어야 하고, nested object는 deterministic JSON-compatible이어야 한다.

Confidential-safe contract:

- public metadata allowlist를 둔다.
- 허용 기본 field: `chunk_id`, `chunk_type`, `page_range`, `section_path`, `semantic_types`, `retrieval_priority`, `token_estimate`, redacted `source_refs`
- raw `input_pdf` path, absolute asset path, local output path, 원본 filename, customer/product codename 후보는 warning 이상으로 보고한다.
- `source_sha256`는 공유 전 검토 대상으로 warning 처리한다.
- 원문 `text` 자동 익명화는 하지 않는다. 대신 report에 `text_redaction_not_performed` advisory를 남긴다.

### 출력 report

기본 파일: `index_contract_report.json`

필수 구조:

```json
{
  "schema_version": "1.0",
  "purpose": "rag_index_contract_validation",
  "status": "passed",
  "targets": ["openai", "azure-ai-search", "langchain", "llamaindex"],
  "summary": {
    "checked_files": 1,
    "checked_records": 10,
    "error_count": 0,
    "warning_count": 0
  },
  "files": [],
  "findings": []
}
```

Finding field:

- `severity`: `error`, `warning`, `info`
- `code`: deterministic snake_case code
- `target`: target 이름 또는 `common`
- `file`: 산출물 파일명
- `line`: JSONL line number, 파일 단위 finding이면 `null`
- `record_id`: `chunk_id` 또는 sidecar record id
- `field`: 문제 field path
- `message`: 사람이 읽는 설명

정렬 순서:

1. severity: error, warning, info
2. file name
3. line number
4. field
5. code

### 구현 위치

- `scripts/validate_index_contract.py`
- 필요 시 순수 로직 모듈: `pdf2md/utils/index_contract.py`
- target별 mapping helper는 스크립트 내부 함수로 시작하고, 중복이 커질 때만 모듈화한다.
- report 모델이 public schema로 승격되면 `pdf2md/models.py`, `docs/schema/`에 추가한다.

### 테스트

- `tests/test_index_contract_validator.py`
- 정상 `retrieval_chunks_rag.jsonl` fixture가 모든 target에서 passed 되는지 확인한다.
- required field 누락, 타입 오류, 빈 `source_refs`, 잘못된 `page_range`를 각각 error로 검증한다.
- metadata size 초과를 warning/error 정책에 맞게 검증한다.
- confidential-safe 모드에서 absolute path와 filename 노출을 탐지한다.
- JSONL line number와 finding 정렬이 deterministic인지 확인한다.
- script smoke:

```bash
python scripts/validate_index_contract.py --output-dir output --target all --fail-on-error
```

### 완료 조건

- validator가 외부 서비스 호출 없이 동작한다.
- 정상 golden corpus는 통과하고, 의도적으로 깨진 fixture는 안정적인 finding을 낸다.
- `docs/RAG_INDEXER_INTEGRATION_RECIPES.md`에 local validation 명령이 추가된다.
- release/rag gate에 optional로 연결할 수 있는 함수 또는 script command가 준비된다.

### 비범위

- OpenAI/Azure/LangChain/LlamaIndex SDK 의존성 추가
- 실제 embedding 생성 또는 index upload
- 원문 text anonymization

## P2 / Q35. Rendered Diagram Fixture Suite

### 목표

state machine, sequence diagram, register layout을 포함한 synthetic PDF fixture를 렌더링 기반으로 추가하고, `figures_rag.jsonl`의 diagram provenance와 diagnostics를 golden으로 고정한다.
OCR runtime 유무에 따라 기대 diagnostics를 분리해 CI가 환경 차이 때문에 흔들리지 않게 한다.

### 사용자 가치

- 다이어그램/그림 sidecar가 단순 이미지 추출을 넘어 bbox, caption, heading, label diagnostics를 안정적으로 유지하는지 회귀 방지한다.
- OCR이 없는 CI에서도 deterministic golden을 유지하고, OCR이 있는 로컬/확장 CI에서는 더 풍부한 label diagnostics를 검증한다.
- storage/security spec의 state/register/sequence diagram 분석용 RAG provenance 품질을 높인다.

### Fixture 범위

추가 synthetic PDF:

- state machine diagram
  - 상태 노드 3개 이상
  - 전이 화살표 2개 이상
  - transition label 예: `READY`, `ERROR`, `RESET`
  - Figure caption과 section heading 포함
- sequence diagram
  - lifeline 2개 이상
  - message arrow 2개 이상
  - message label 예: `Command`, `Completion`
  - Figure caption과 nearby text 포함
- register layout
  - bit range cell 예: `31:16`, `15:8`, `7:0`
  - field label 예: `RSVD`, `STATUS`, `ENABLE`
  - table이 아니라 figure/diagram 후보로도 잡힐 수 있는 렌더링 케이스 포함

권장 위치:

- 생성 helper: `tests/fixtures/pdf_builder.py` 확장 또는 `tests/fixtures/diagram_pdf_builder.py`
- golden output: `tests/golden/corpus/diagram_*`
- fixture source PDF는 repo policy에 따라 작고 deterministic한 synthetic 파일만 커밋한다.

### 기대 산출물

각 fixture 변환 시 최소 확인 대상:

- `document.md`
- `manifest.json`
- `report.json`
- `figures_rag.jsonl`
- 필요한 경우 `text_blocks_rag.jsonl`, `retrieval_chunks_rag.jsonl`

`figures_rag.jsonl` golden에서 고정할 field:

- `figure_id`
- `page`
- `figure_index`
- `record_type`
- `status`
- `path`
- `bbox`
- `caption_text`
- `caption_source`
- `caption_confidence`
- `heading_path`
- `source_refs`
- `figure_kind`
- `diagram_candidate`
- `detected_labels`
- `diagram_label_diagnostics`
- `nearby_text_refs`
- `classification_confidence`
- `classification_reasons`

### OCR 분기 정책

기본 CI 경로:

- OCR runtime이 없어도 통과해야 한다.
- `ocr_candidates`는 비어 있거나 runtime unavailable diagnostic을 가진다.
- low-confidence 또는 unavailable OCR 결과는 promoted label로 고정하지 않는다.

OCR available 경로:

- 별도 test marker 또는 runtime preflight로 분기한다.
- OCR label 후보가 `diagram_label_diagnostics.ocr_candidates` 또는 동등 diagnostics에 남는지 확인한다.
- promoted `detected_labels`는 confidence threshold를 넘는 deterministic 후보만 허용한다.

권장 test 구성:

- OCR-independent golden test: 항상 실행
- OCR runtime dependent test: `pytest.importorskip` 또는 기존 OCR runtime check helper로 조건부 실행

### 구현 요구사항

- synthetic PDF는 폰트/좌표/도형을 고정해 플랫폼별 layout drift를 최소화한다.
- bbox 비교는 소수점 고정 또는 tolerance-normalization helper를 사용한다.
- asset filename은 기존 deterministic 규칙을 따른다.
- caption과 heading provenance는 source_refs로 추적 가능해야 한다.
- register layout이 table extractor와 충돌하는 경우에도 figure diagnostics가 보존되는지 확인한다.

### 테스트

- `tests/test_rag_figures.py`에 diagram fixture 단위 테스트 추가
- `tests/test_golden_corpus.py`에 diagram corpus golden 포함
- OCR 없는 환경에서 `figures_rag.jsonl` expected output 고정
- OCR 있는 환경에서 label candidate diagnostics 별도 assertion
- caption/heading/source_refs가 누락되면 실패

권장 smoke:

```bash
python -m pytest tests/test_rag_figures.py tests/test_golden_corpus.py
python -m pdf2md tests/fixtures/diagram_state_machine.pdf -o /tmp/pdf2md-diagram-smoke --figure-crop-fallback
```

### 완료 조건

- state machine, sequence diagram, register layout fixture가 추가된다.
- OCR 미설치 CI에서 golden이 안정적으로 통과한다.
- OCR 설치 환경에서 추가 diagnostics test가 통과한다.
- `figures_rag.jsonl`의 diagram/caption/heading/source provenance 회귀가 잡힌다.

### 비범위

- 다이어그램 의미 해석 완성
- VLM 기반 이미지 설명 생성
- Mermaid/PlantUML로의 변환

## P2 / Q36. Page-Level Parallel Extractor

### 목표

문서 단위 증분 캐시 이후 page extraction, read-order, table 후보 생성을 page worker 단위로 병렬화할 수 있는 executor를 추가한다.
기본값은 기존 single-worker 경로를 유지하고, `--page-workers`를 명시했을 때만 병렬 경로를 사용한다.
병렬 실행에서도 출력 순서, warning/report ordering, asset naming, JSONL record order는 기존 deterministic contract를 유지해야 한다.

### 사용자 가치

- 긴 기술 PDF 변환 시간을 줄인다.
- 병렬화를 opt-in으로 두어 기존 안정성을 유지한다.
- 운영자는 benchmark gate로 속도 향상과 결과 동일성을 함께 확인할 수 있다.

### CLI/API 설계

CLI 옵션:

```bash
python -m pdf2md spec.pdf -o output --page-workers 4
python -m pdf2md spec.pdf -o output --page-workers 1
```

Config 추가:

- `page_workers: int = 1`

Validation:

- `page_workers >= 1`
- 기본값 `1`
- `1`이면 기존 single-worker behavior와 동일해야 한다.
- 너무 큰 값은 page 수 또는 CPU 수 기준으로 내부 cap을 둘 수 있지만, cap 적용 시 report에 diagnostic을 남긴다.

Manifest/report 추가 후보:

- `manifest.options.page_workers`
- `report.summary.page_worker_count`
- `report.summary.page_parallel_enabled`
- `report.summary.page_worker_effective_count`

public schema에 추가하면 `docs/OUTPUT_SCHEMA.md`, schema export test를 함께 갱신한다.

### 병렬화 대상

1차 범위:

- page text extraction/read-order 후보 생성
- page table candidate extraction
- page-level structure normalization 준비 데이터

보수적 제외 대상:

- final Markdown serialization
- manifest/report write
- RAG sidecar write
- image asset file write와 asset naming
- OCR execution

이미지 추출은 파일명과 dedupe ordering이 민감하므로 Q36 1차 구현에서는 single path를 유지한다.

### 아키텍처

권장 구조:

- `pdf2md/extractors/page_worker.py`
  - `PageWorkerInput`
  - `PageWorkerResult`
  - `extract_page_worker(input) -> PageWorkerResult`
- `pdf2md/utils/page_executor.py`
  - `run_page_workers(inputs, worker_count) -> list[PageWorkerResult]`

Worker result는 page number를 포함하고, parent process에서 반드시 page number 순으로 merge한다.

`PageWorkerResult` 최소 field:

- `page`
- `text_lines`
- `raw_lines`
- `text_metadata`
- `page_text`
- `table_assets`
- `table_blocks`
- `rag_tables`
- `table_debug_candidates`
- `warnings`
- `failed`
- `duration_ms`

### 결정성 규칙

- merge는 항상 `selected_pages` 순서를 기준으로 한다.
- warning은 `(page, code, message)` 기준으로 정렬하거나 selected page merge 순서를 유지한다.
- table/image/figure asset index는 병렬 worker 내부 최종값을 그대로 믿지 말고 parent merge 단계에서 page-local deterministic index를 재확정한다.
- JSONL record는 기존 builder의 입력 순서를 page-sorted로 제공한다.
- stage duration은 전체 wall-clock duration과 worker duration aggregate를 구분한다.
- debug artifact 파일명은 기존 `page-0001-*` 규칙을 유지한다.

### 구현 단계

1. `Config`와 CLI에 `page_workers`를 추가하고, `1`일 때 기존 테스트가 그대로 통과하게 한다.
2. text extraction을 page worker로 호출할 수 있도록 순수 page 단위 함수 경계를 만든다.
3. table 후보 추출을 page 단위로 분리하되, 기존 `extract_tables` public behavior는 유지한다.
4. `--page-workers > 1`에서 executor를 사용하고 parent merge로 기존 자료구조를 복원한다.
5. 동일 입력에 대해 single-worker와 multi-worker output diff가 없는지 테스트한다.
6. benchmark script 또는 release gate에 opt-in 성능 검증을 연결한다.

### 테스트

- CLI parser test: `--page-workers` 기본값과 validation
- config/model test: `page_workers` serialization
- deterministic equivalence test:
  - 같은 fixture를 `--page-workers 1`과 `--page-workers 2`로 변환
  - volatile field를 normalize한 뒤 `document.md`, `manifest.json`, `report.json`, JSONL sidecar 비교
- partial failure ordering test:
  - 특정 page worker 실패를 모의하고 warning/report ordering이 안정적인지 확인
- benchmark smoke:

```bash
python scripts/benchmark_conversion.py --input tests/fixtures/multi_page.pdf --page-workers 1
python scripts/benchmark_conversion.py --input tests/fixtures/multi_page.pdf --page-workers 4
```

### 완료 조건

- 기본 `page_workers=1` 경로에서 기존 golden이 변하지 않는다.
- `--page-workers > 1`에서 결과 산출물 내용이 single-worker와 동일하다.
- report에 worker count와 parallel enabled 여부가 남는다.
- benchmark gate가 결과 동일성과 최소 성능 신호를 함께 확인한다.

### 비범위

- batch document-level 병렬화
- OCR 병렬화
- image extraction/file write 병렬화
- distributed execution

## P1 / Q37. Cross-Sidecar Provenance Integrity Validator

### 목표

Q34의 index mapping 검증을 통과한 산출물이라도 내부 sidecar provenance가 깨져 있으면 RAG citation과 test script 수정 범위 계산이 잘못될 수 있다.
Q37은 모든 RAG sidecar의 `source_refs`가 실제 원본 record로 해소되는지 local-only로 검증한다.

### 주요 검증

- `retrieval_chunks_rag.jsonl.source_refs[].source_id`가 대응 sidecar record id에 존재하는지 확인한다.
- `source_refs[].page`, chunk `page_range`, record `page`, `bbox`가 상호 모순되지 않는지 확인한다.
- `source_record_count`가 실제 `source_refs` 개수와 일치하는지 확인한다.
- `source_dedupe_key`가 source id 집합에서 deterministic하게 복원 가능한지 확인한다.
- manifest/report summary count와 실제 JSONL record count가 어긋나면 warning 또는 error로 분류한다.

### 구현 위치

- 새 스크립트: `scripts/validate_provenance_integrity.py`
- 필요 시 helper: `pdf2md/utils/provenance_integrity.py`
- 출력 report: `provenance_integrity_report.json`
- release gate optional: `--gates provenance-integrity`

### 테스트

- 정상 golden corpus가 통과하는 test
- 없는 `source_id`, 잘못된 page, bbox page mismatch, count mismatch fixture test
- finding 정렬과 line/record id 위치가 deterministic인지 확인

### 완료 조건

- 외부 서비스 호출 없이 단일 output directory를 검증한다.
- 오류가 어느 sidecar/file/line/source_ref에서 발생했는지 report로 추적 가능하다.
- release gate에서 opt-in으로 실행 가능하다.

## P1 / Q38. Layout Stress Golden Corpus

### 목표

기존 synthetic corpus는 핵심 경로를 잘 막지만, 실제 기술 문서에서 문제가 되는 multi-column, sidebar, floated figure, footnote, mixed-language layout 조합은 더 강한 회귀 방어가 필요하다.
Q38은 reading order와 heading/source provenance 품질을 golden corpus로 고정한다.

### Fixture 범위

- 2-column 본문 + 우측 sidebar note
- figure가 본문 중간에 떠 있고 caption이 다음 줄/이전 줄에 있는 page
- 하단 footnote가 많은 page
- section heading이 다음 column/page 본문에 carry-over되는 page
- Korean/English mixed paragraph와 list

### 검증 대상

- `document.md`의 원문 순서
- `text_blocks_rag.jsonl.block_type`, `heading_path`, `parent_heading_block_id`
- `semantic_units_rag.jsonl.source_refs`
- `retrieval_chunks_rag.jsonl.page_range`, `section_path`, `source_refs`
- `report.summary.structure_low_confidence_count`, `page_results[].reading_order_strategy`

### 테스트

- `tests/fixtures/pdf_builder.py` 또는 별도 builder에 layout stress PDF 생성 함수 추가
- `tests/golden/corpus/layout_*` golden 추가
- volatile field normalize 후 golden corpus test에 포함

### 완료 조건

- layout stress fixture가 기본 CI에서 안정적으로 통과한다.
- reading order가 바뀌면 `document.md` 또는 RAG sidecar golden diff로 바로 드러난다.

## P1 / Q39. Table Reconstruction Accuracy Pack

### 목표

표는 이 프로젝트의 두 번째 우선순위이며 RAG 운영에서는 table row, technical table unit, domain unit의 source of truth다.
Q39는 복잡 표를 억지로 GFM으로 내보내지 않는 정책과 row-level structured sidecar 정확도를 더 강하게 검증한다.

### Fixture 범위

- merged cell / multi-row header
- stub column + footnote row
- continued table with repeated header
- repeated template table false-positive 방지
- register bitfield layout: `31:16`, `15:8`, `7:0`
- command/opcode/log page/feature/security method 형태의 technical table

### 검증 대상

- 단순 표만 GFM 사용
- 복잡 표는 HTML fallback 유지
- `tables_rag.jsonl.headers`, `cells`, `row_text`, `bbox`, `fallback_reasons`
- `technical_tables_rag.jsonl.unit_type`, `bit_range`, `field_name`, `value`, `source_refs`
- `report.summary.table_fallback_reason_counts`, `table_low_quality_count`

### 테스트

- 기존 `tests/test_tables.py`, `tests/test_rag_tables.py`, `tests/test_rag_technical_tables.py` 확장
- golden corpus에 table accuracy pack 추가
- unsafe GFM coercion이 발생하면 실패하는 regression test 추가

### 완료 조건

- 잘못된 GFM 표 생성 가능성이 낮아진다.
- register/bitfield/technical table row provenance가 RAG sidecar에서 안정적으로 추적된다.

## P2 / Q40. OCR Confidence And Language Calibration Matrix

### 목표

OCR은 환경 의존성이 크므로, runtime 없음/있음과 언어 데이터 상태에 따른 기대 diagnostics를 명확히 분리해야 한다.
Q40은 OCR 결과를 임의 교정하지 않는 원문 보존 정책과 confidence warning/report 계약을 고정한다.

### Fixture 범위

- OCR runtime unavailable path
- low-confidence scanned text
- empty OCR result
- Korean+English mixed scanned page
- scanned simple table

### 검증 대상

- `warnings[].code`: `OCR_RUNTIME_UNAVAILABLE`, `OCR_CONFIDENCE_WARN`, `OCR_CONFIDENCE_CRITICAL`, `OCR_EMPTY_RESULT`
- `warnings[].details.reason`: `dependency_unavailable`, `tesseract_unavailable`, `pdf_open_failed`, `language_data_missing`, `empty_result`, `ocr_failed`
- `page_results[].ocr_attempted`, `ocr_runtime_available`, `ocr_confidence_mean`, `low_conf_token_ratio`
- OCR text가 spelling correction이나 paraphrase 없이 그대로 sidecar/Markdown에 들어가는지 확인

### 테스트

- OCR 없는 환경에서도 통과하는 deterministic test
- OCR runtime이 있는 경우에만 실행되는 conditional test
- language data missing report test

### 완료 조건

- OCR 환경 차이 때문에 CI가 흔들리지 않는다.
- 낮은 confidence 결과가 정답처럼 소비되지 않고 warning/report로 드러난다.

## P2 / Q41. Output Artifact Integrity Gate

### 목표

변환 자체가 성공해도 Markdown link, asset file, manifest/report count, sidecar file map이 어긋나면 downstream agent가 실패한다.
Q41은 산출물 파일 간 무결성을 local gate로 검증한다.

### 주요 검증

- `document.md`의 image relative link가 실제 asset file을 가리키는지 확인한다.
- manifest `images[]`, `tables[]`, report summary count, 실제 sidecar record count가 일치하는지 확인한다.
- batch/corpus manifest의 file map이 실제 파일과 일치하는지 확인한다.
- orphan asset, missing asset, stale path, sidecar count mismatch를 deterministic finding으로 출력한다.

### 구현 위치

- 새 스크립트: `scripts/validate_artifact_integrity.py`
- 출력 report: `artifact_integrity_report.json`
- release gate optional: `--gates artifact-integrity`

### 테스트

- 정상 single output과 batch/corpus output 통과 test
- missing image file, broken Markdown link, stale manifest path, sidecar count mismatch fixture test
- confidential-safe mode에서 absolute path가 섞이지 않는지 확인

### 완료 조건

- 변환 결과가 downstream에서 바로 소비 가능한 파일 세트인지 자동 점검할 수 있다.
- partial success와 실제 artifact 누락을 report에서 구분할 수 있다.

## P2 / Q42. Full Page Worker Table Candidate Parallelization

### 목표

Q36에서 도입한 `--page-workers` text/read-order 병렬 경로를 table candidate extraction까지 확장한다.
기본값 `page_workers=1`의 기존 deterministic 경로는 유지하고, `--page-workers > 1`에서만 page-local table 후보 생성을 worker로 분산한다.

### 구현 범위

- `extract_tables`의 public behavior는 유지한다.
- page-local table candidate collection은 worker에서 수행한다.
- continuation grouping, table asset index, warning/report ordering, RAG table record ordering은 parent merge에서 selected page 순서로 재확정한다.
- image extraction, OCR, manifest/report write는 계속 single path로 둔다.

### 검증 대상

- `document.md`, `manifest.json`, `report.json`, `tables_rag.jsonl`, `technical_tables_rag.jsonl`가 worker 수와 무관하게 동일해야 한다.
- continuation table, repeated template table, complex HTML fallback, simple GFM table fixture에서 결과 동일성을 확인한다.
- `report.summary.page_worker_effective_count`, `page_parallel_enabled`, `pdf_open_count`가 병렬 실행을 설명할 수 있어야 한다.

### 테스트

- single-worker와 multi-worker output diff test
- worker 내부 table candidate 실패 시 page-scoped warning ordering test
- benchmark smoke 또는 release gate optional check

### 완료 조건

- table candidate extraction까지 병렬화해도 기존 golden corpus가 변하지 않는다.
- multi-worker 경로의 결과 동일성과 최소 성능 신호가 CI 또는 release gate에서 검증된다.

### 구현 결과

- `--page-workers > 1` 경로에서 worker가 isolated PDF open 1회로 page-local text/read-order와 table raw candidate를 함께 수집한다.
- `extract_tables`는 precomputed page candidate를 받아 parent에서 selected page 순서로 pruning, fallback warning, table index, continuation, RAG table ordering을 재확정한다.
- image extraction, OCR, manifest/report write는 single parent path를 유지한다.
- benchmark smoke는 `scripts/benchmark_conversion.py --page-workers 1,2`처럼 worker count별 실행과 core artifact hash 동등성 신호를 기록한다.

## P1 / Q43. Quality Scorecard Refresh

### 목표

Q31-Q42 구현 후 현재 품질 상태를 97/100 기준으로 재평가하고, 다음 backlog를 Q46/Q44로 축소한다.

### 구현 범위

- `docs/QUALITY_SCORECARD.md`에 2026-05-14 평가 항목을 추가한다.
- `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에는 완료된 Q43을 남기지 않고 다음 실제 작업인 Q46, Q44만 유지한다.
- Q46/Q44는 기능 구현 전 개발 명세와 테스트 기준을 이 문서에 추가한다.

### 완료 조건

- scorecard가 현재 merge 상태와 남은 리스크를 설명한다.
- next plan에는 앞으로 할 작업만 남는다.
- 문서 계약 테스트와 diff check가 통과한다.

## P1 / Q46. RAG Golden Query Expected Source Coverage

### 목표

RAG 평가가 단순 keyword hit뿐 아니라 expected source id를 맞히는지 검증한다.

### 구현 범위

- eval set query에 `expected_source_ids`와 optional `expected_source_types`를 지원한다.
- `scripts/run_rag_eval.py`는 retrieved chunk의 `source_refs[].source_id`와 chunk id를 비교해 source coverage를 계산한다.
- report summary에 `expected_source_coverage`, `expected_source_hit_count`, `expected_source_total_count`를 추가한다.
- release gate threshold로 `--min-expected-source-coverage`를 추가한다.

### 검증 대상

- requirement query가 requirement/text source id를 찾는지 확인한다.
- table-field query가 table row 또는 technical table unit source id를 찾는지 확인한다.
- missing source id는 query별 diagnostics와 gate regression으로 남긴다.

### 완료 조건

- Q46 fixture/eval test가 deterministic하게 통과한다.
- 기존 hit@k/MRR/citation coverage 동작은 유지된다.
- release gate `rag` command에서 expected source coverage threshold를 전달할 수 있다.

### 구현 결과

- eval set query에 `expected_source_types`를 추가해 chunk id와 source_refs source type을 함께 검증할 수 있다.
- requirement/table-field coverage는 기본 source type allowlist를 사용해 잘못된 source type의 우연한 id match를 막는다.
- `relationship_target_coverage`로 relationship metadata가 같은 `retrieval_chunks_rag.jsonl` 내부 final chunk id를 가리키는지 검증한다.
- `rag_eval_report.json` metrics에 `expected_source_coverage`, hit/total/miss count를 추가했다.
- query별 결과에 `missing_expected_source_ids`를 기록해 golden source id 누락 원인을 바로 추적할 수 있다.
- `scripts/run_release_gates.py`의 `rag` gate가 `--rag-min-expected-source-coverage` threshold를 전달한다.

## P1 / Q44. Domain Technical Table Coverage Expansion

### 목표

NVMe/PCIe/OCP/TCG technical table row를 더 구체적인 typed unit으로 분류해 agent가 register/opcode/security table provenance를 안정적으로 추적하게 한다.

### 구현 범위

- `technical_tables_rag.jsonl` classification을 보강한다.
- register map/bitfield, command opcode, log page, feature identifier, security method/object/authority/field fixture를 확장한다.
- domain adapter output이 technical table unit provenance를 유지하는지 테스트한다.

### 검증 대상

- `unit_type`, `bit_range`, `field_name`, `opcode`, `command`, `log_identifier`, `feature_identifier`, `source_refs`가 안정적으로 채워지는지 확인한다.
- conservative confidence와 classification reasons가 불명확한 row를 과분류하지 않는지 확인한다.

### 완료 조건

- `tests/test_rag_technical_tables.py`, `tests/test_rag_domain_adapters.py`, golden corpus 또는 focused fixture가 통과한다.
- Q46 expected source coverage query가 Q44 technical table source ids를 검증할 수 있다.

### 구현 결과

- `technical_tables_rag.jsonl`가 TCG `security_object`, `security_authority`, `security_field` row를 `security_method`와 구분해 typed unit으로 분류한다.
- security field/description/UID 계열 header를 normalized fields와 classification reasons에 보존한다.
- domain adapter records built from technical table rows now carry both `table_row` and `technical_table_unit` source refs.
- Q46 expected source coverage로 `technical_table_unit` source id를 검증하는 focused test를 추가했다.

## P1 / Q47. Local Technical Corpus Evidence Pack

### 목표

비공개/대형 technical corpus에서만 드러나는 failure pattern을 원본 PDF, local path, command, customer/vendor filename, eval query text 없이 공유 가능한 local-only evidence pack으로 정리한다.

Q47은 97/100 이후 남은 리스크를 “새 heuristic을 먼저 추가”하는 방식이 아니라, 실제 local corpus 운영 중 반복되는 실패 signature를 축적하고 우선순위를 판단할 수 있게 만드는 작업이다.

### 구현 범위

- `scripts/run_ssd_corpus_profile.py`에 opt-in `--evidence-pack`, `--evidence-pack-path`, `--evidence-profile-label` 옵션을 추가한다.
- `ssd_corpus_profile_report.json`의 contract finding code/path를 보존해 evidence pack signature 생성에 사용한다.
- `local_corpus_evidence_pack.json` public JSON 출력을 추가한다.
- evidence pack은 redacted `document-000001` 형태 label만 사용하고 raw `input_pdf`, `output_dir`, command, document name, query text를 포함하지 않는다.
- conversion exit code, SSD contract error/warning, RAG threshold failure, corpus budget failure를 deterministic `sig-<hash>` signature로 집계한다.
- `docs/OUTPUT_SCHEMA.md`, `docs/schema/local_corpus_evidence_pack.schema.json`, README, Windows guide, RAG indexer recipe를 갱신한다.

### 출력 구조

- `schema_version`: `1.0`
- `purpose`: `local_technical_corpus_evidence_pack`
- `profile_label`
- `profile_fingerprint`
- `redaction_policy`
- `summary`
- `domains`
- `documents`
- `failure_signatures`

### 테스트

- `tests/test_ssd_rag_contract.py`
  - raw path, filename, command, query text가 evidence pack에 포함되지 않는지 확인한다.
  - 동일 입력에서 `profile_fingerprint`와 failure signature id가 결정적인지 확인한다.
  - contract/budget/RAG threshold failure가 signature로 집계되는지 확인한다.
  - CLI option이 evidence pack 파일을 쓰는지 확인한다.
- `tests/test_output_schema_contract.py`
  - 새 schema export/check 계약을 추가한다.
- `tests/test_docs_examples.py`
  - Q47 archive와 새 schema/output 문서 계약을 확인한다.

### 구현 결과

- private corpus 운영 결과를 raw output 대신 redacted signature pack으로 공유할 수 있다.
- 새 fixture나 heuristic을 추가하기 전에 domain/spec/category/metric/code별 반복 실패를 먼저 확인할 수 있다.
- public JSON schema 계약에 `local_corpus_evidence_pack.schema.json`이 추가됐다.

## P1 / Q48. Corpus Evidence Signature Analysis Report

### 목표

Q47 `local_corpus_evidence_pack.json`을 단일 실행 단위로 분석해 failure signature를 category/domain/spec/code/metric 기준으로 재집계하고, deterministic follow-up 후보를 제공한다.

### 구현 결과

- `scripts/analyze_corpus_evidence_pack.py`를 추가해 redacted evidence pack만 입력으로 사용하는 local-only 분석 report를 생성한다.
- `corpus_evidence_analysis_report.json`은 category hotspot, domain/spec hotspot, follow-up hint를 deterministic하게 정렬한다.
- public schema `docs/schema/corpus_evidence_analysis_report.schema.json`와 `docs/OUTPUT_SCHEMA.md`, README, Windows guide, RAG indexer recipe를 갱신했다.
- `tests/test_corpus_evidence_tools.py`가 report model validation, script smoke, follow-up hint 계약을 검증한다.

## P1 / Q49. Appendix Clause Requirement Fixture Expansion

### 목표

긴 appendix, nested clause, vendor-specific requirement table 주변 heading carry-over를 synthetic fixture와 regression test로 고정한다.

### 구현 결과

- `build_appendix_clause_requirement_pdf` synthetic fixture를 추가했다.
- appendix heading과 nested numeric clause heading path를 requirement text, requirement table row, technical table row, customer requirement domain unit에 보수적으로 carry-over한다.
- carry-over는 high-risk appendix/clause/requirement/vendor heading context에만 적용해 기존 table golden 출력의 불필요한 churn을 피한다.
- `tests/test_appendix_clause_requirements.py`가 Appendix A와 Table 1 cross-reference 해소, `VEND-APP-1`, `VEND-APP-2` traceability, technical/domain provenance를 검증한다.

## P2 / Q50. Captionless Diagram Diagnostics Hardening

### 목표

caption 없는 diagram/image 후보를 환각 없이 diagnostics-only로 기록하고, OCR/nearby text label 승격이 보수적으로 동작하는지 고정한다.

### 구현 결과

- `figures_rag.jsonl` record에 optional `captionless_diagnostics`를 추가했다.
- caption이 없고 낮은 confidence OCR 후보만 있는 경우 promoted label이나 caption을 만들지 않고 `low_confidence`, `missing_caption`, `no_promoted_ocr_labels` 같은 rejection reason만 남긴다.
- `docs/OUTPUT_SCHEMA.md`에서 `diagram_label_diagnostics`와 `captionless_diagnostics`를 optional diagnostics로 명확히 설명했다.
- `tests/test_rag_figures.py`가 captionless low-confidence 후보가 hallucinated caption 없이 diagnostics-only로 남는지 검증한다.

## P2 / Q51. Evidence Pack History Comparison Gate

### 목표

baseline/current `local_corpus_evidence_pack.json`을 비교해 신규, 해결, 지속 failure signature를 local-only report로 만든다.

### 구현 결과

- `scripts/compare_corpus_evidence_packs.py`를 추가했다.
- `corpus_evidence_trend_report.json`은 signature id 기준 `added`, `persisting`, `resolved` 상태와 summary count를 deterministic하게 산출한다.
- `--fail-on-new-signature`가 신규 error signature에서 non-zero exit code를 반환한다.
- public schema `docs/schema/corpus_evidence_trend_report.schema.json`와 운영 문서를 갱신했다.
- `tests/test_corpus_evidence_tools.py`가 trend report model validation, script smoke, failure gate를 검증한다.

## P2 / Q52. Quality Document And Schema History Contract

### 목표

scorecard, next plan, development specs, implemented archive, output schema 사이의 stale 히스토리 표현을 더 강하게 자동 검증한다.

### 구현 결과

- `tests/test_output_schema_contract.py`가 `scripts/export_output_schema.py`의 public schema 목록이 `docs/OUTPUT_SCHEMA.md`에 모두 문서화되어 있는지 확인한다.
- Q48-Q52 완료 후 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`와 `docs/QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md`는 active backlog 없음 상태로 돌아왔다.
- 이 archive와 `docs/QUALITY_SCORECARD.md`가 Q48-Q52 구현 결과를 포함하도록 갱신했다.

## P2 / Q53. Minimal Desktop GUI Wrapper

### 목표

CLI에 익숙하지 않은 비개발자와 간단한 설치/실행만 원하는 개발자가 PDF 파일 또는 폴더를 선택해 변환할 수 있도록 최소 desktop GUI를 추가한다.

Q53의 핵심은 새 변환 엔진을 만드는 것이 아니라, 기존 `Config`와 `run_conversion` 경로를 그대로 사용하는 얇은 GUI wrapper를 제공하는 것이다. GUI는 사용 편의성을 높이되, CLI와 다른 산출물 계약을 만들면 안 된다.

### 구현 범위

- `pdf2md/gui_runner.py`
  - GUI와 테스트가 함께 쓰는 순수 orchestration helper
  - 단일 파일 변환과 폴더 batch 변환 request를 `Config`로 변환
  - batch document naming은 CLI batch 계약과 맞춘다.
  - skip-existing은 core output인 Markdown, manifest, report가 모두 있을 때만 적용한다.
- `pdf2md/gui.py`
  - Tkinter app entry
  - 파일 선택 / 폴더 선택 / 출력 폴더 선택
  - 주요 옵션 form
  - worker thread 기반 실행
  - 진행 로그와 완료 summary 표시
- `pyproject.toml`
  - `pdf2md-gui = "pdf2md.gui:main"` entry point 추가

### 구현 결과

- `python -m pdf2md.gui`와 설치형 `pdf2md-gui` entry point로 최소 GUI를 실행할 수 있다.
- GUI는 단일 PDF와 폴더 batch 변환을 지원한다.
- GUI는 별도 변환 경로를 만들지 않고 `Config`와 `run_conversion`을 사용한다.
- headless CI에서는 Tk mainloop를 띄우지 않고 `python -m pdf2md.gui --help`, runner config, 단일 변환 산출물 동일성, batch skip-existing 정책을 테스트한다.
- README와 Windows guide에 GUI와 CLI의 역할 차이를 문서화했다.

### 비범위

- 대형 GUI application framework 도입
- Electron, Qt, web server 기반 UI
- PDF 미리보기/페이지 썸네일/본문 편집기
- 변환 산출물 수동 편집 기능
- 외부 RAG/indexing 서비스 호출
- GUI 전용 output schema 또는 CLI와 다른 변환 옵션 의미

## P1 / Q54. GUI Runtime And Install Diagnostics

### 목표

Q53 GUI wrapper가 실제 사용자 환경에서 시작되거나 변환을 실행하기 전에 실패할 수 있는 runtime/setup 문제를 core 변환 실패와 구분한다. 대상은 Python 버전, Tkinter runtime, module/entry point 설치 상태, input/output path 접근성이다.

### 구현 범위

- `pdf2md/gui_runner.py`
  - `GuiDiagnostic`, `GuiDiagnosticReport`, `GuiDiagnosticError` 추가
  - `check_gui_runtime()`로 Python 3.11+ 지원 범위, Tkinter import 가능성, `pdf2md.gui` module import, `pdf2md-gui` console script 설치 여부를 사전 점검
  - `validate_gui_request()`로 file/folder input, PDF 확장자, readable input, duplicate batch stem, output directory 생성 가능성을 변환 전 점검
  - `run_gui_conversion()`이 diagnostic error를 먼저 반환하도록 보호
- `pdf2md/gui.py`
  - GUI launch 전 runtime diagnostic error는 창을 띄우기 전에 stderr로 표시하고 종료
  - 변환 시작 전 request diagnostic error는 messagebox/log로 표시하고 worker thread를 시작하지 않음
  - warning은 변환을 막지 않고 GUI log에 남김
- `tests/test_gui_runner.py`
  - Tkinter 미설치, Python 버전 불일치, output path file collision을 headless unit test로 고정

### 구현 결과

- Tkinter/runtime/setup failure와 PDF 변환 실패가 GUI에서 구분된다.
- `python -m pdf2md.gui --help`는 계속 창을 띄우지 않고 종료한다.
- output path가 파일인 경우처럼 사용자가 직접 조치할 수 있는 오류는 raw traceback 대신 diagnostic message로 노출된다.
- CLI `pdf2md` 변환 경로와 public JSON schema는 변경하지 않았다.

### 비범위

- 설치형 GUI app packaging
- OS별 native installer
- GUI 전용 conversion schema
- 변환 중 결과 검토 UI, batch cancel/retry controls, distribution guide 확장

## P1 / Q55. GUI Conversion Result Review UX

### 목표

GUI 변환 완료 후 사용자가 Markdown만 확인하는 데서 끝나지 않고 `manifest.json`, `report.json`, partial success warning, failed/skipped 상태를 한 화면에서 확인할 수 있게 한다. 표시 정보는 구조화된 report/manifest 경로와 warning code/count로 제한하고, 원문 텍스트/표/이미지 내용을 요약하지 않는다.

### 구현 범위

- `pdf2md/gui_runner.py`
  - `GuiDocumentSummary`에 Markdown, manifest, report, assets path와 warning count/code를 추가
  - `format_gui_summary()`로 단일/배치 완료 summary를 deterministic 문자열로 생성
  - warning display는 message 본문 대신 sorted unique warning code와 count만 사용
  - skipped 문서도 기존 core output path를 summary에 포함
- `pdf2md/gui.py`
  - 완료 결과를 `ttk.Treeview` 표에 document/status/warnings/Markdown/report 열로 표시
  - 완료 message와 log가 동일한 structured summary를 사용
  - output folder 열기 실패는 변환 실패로 바꾸지 않고 GUI warning으로만 표시
- `tests/test_gui_runner.py`
  - single conversion artifact path summary 검증
  - skipped batch artifact path summary 검증
  - partial success warning count/code ordering과 warning message 미노출 검증

### 구현 결과

- GUI 완료 화면에서 success, partial_success, failed, skipped count와 문서별 core artifact path를 확인할 수 있다.
- warning은 원문 내용을 복사하지 않고 code/count 중심으로 표시된다.
- 기존 CLI output naming, `Config`, `run_conversion` 경로는 유지했다.

### 비범위

- report/manifest 내용 편집기
- PDF/Markdown preview
- 변환 중 취소와 재시도 후보 summary
- 새 public JSON schema

## P1 / Q56. GUI Batch Operation Controls

### 목표

폴더 배치 변환에서 진행률, 취소 요청, 실패 문서 재시도 후보를 GUI runner가 deterministic하게 관리하도록 한다. core `run_conversion` 내부에는 GUI 전용 상태를 주입하지 않고, 문서 경계에서만 배치 제어를 수행한다.

### 구현 범위

- `pdf2md/gui_runner.py`
  - `GuiBatchProgress`와 batch progress callback 추가
  - `CancelCallback`을 받아 문서 경계에서 남은 문서를 `cancelled` 상태로 summary에 기록
  - batch input ordering을 `(lowercase name, original name)` 기준으로 안정화
  - conversion exception을 문서 단위 `failed` summary로 기록하고 batch는 partial exit로 계속 진행
  - 실패 문서에는 raw command 대신 input path, output path, deterministic option fingerprint를 포함
  - `cancelled_count`, `retry_candidates`, `gui_options_fingerprint()` 추가
- `pdf2md/gui.py`
  - Cancel 버튼 추가
  - batch progress event를 log에 표시
  - 결과 표에 retry candidate 여부 표시
- `tests/test_gui_runner.py`
  - deterministic batch ordering
  - skip-existing artifact path/fingerprint
  - document-boundary cancellation
  - failed document retry candidate summary

### 구현 결과

- 배치 변환 중 취소 요청은 현재 문서가 끝난 뒤 남은 문서를 `cancelled`로 기록한다.
- 실패 문서는 batch 전체를 즉시 중단하지 않고 retry candidate로 summary에 남긴다.
- 동일 입력/옵션에서는 문서 순서, option fingerprint, 상태 summary가 안정적으로 유지된다.

### 비범위

- 실행 중인 단일 PDF 변환 강제 중단
- 산출물 자동 삭제/rollback
- 실패 문서 원클릭 재실행
- 새 public JSON schema

## P2 / Q57. Non-Developer GUI Distribution Guide

### 목표

CLI에 익숙하지 않은 사용자가 설치, GUI 실행, 단일/폴더 변환, 결과 확인, 초기 문제 진단을 문서만 보고 따라갈 수 있게 한다. 설치형 native app packaging은 만들지 않고, 현재 Python/venv/editable install 기반 실행 흐름을 명확히 문서화한다.

### 구현 범위

- `README.md`
  - macOS GUI 빠른 시작 가이드 링크 추가
  - GUI 결과 표, 문서 경계 취소, 실패 retry candidate, 초기 진단 체크리스트 추가
- `docs/MACOS_GUI_QUICKSTART.md`
  - Python 3.11+ 확인
  - venv 생성과 `python -m pip install -e .[dev]`
  - `python -m pdf2md.gui`, `pdf2md-gui`, `python -m pdf2md.gui --help`
  - 단일 PDF 변환, 폴더 배치 변환, Results 표, Cancel, Retry, OCR/Tkinter/output folder troubleshooting
- `docs/WINDOWS_A_TO_Z_GUIDE.md`
  - GUI 사용 순서와 Results 표 확인 절차 추가
  - GUI 실행 실패와 output folder 오류 troubleshooting 추가
- `tests/test_docs_examples.py`
  - README/Windows/macOS GUI guide 핵심 명령과 정책 문구 고정

### 구현 결과

- Windows/macOS 사용자가 CLI 지식 없이도 GUI 실행과 샘플 변환까지 진행할 수 있는 문서 경로가 생겼다.
- automation/CI/반복 배치는 계속 CLI 권장이라는 정책을 유지했다.
- GUI 문서가 실제 `python -m pdf2md.gui`, `pdf2md-gui`, `--help`, Cancel/Retry/status 표시와 일치하도록 테스트로 고정됐다.

### 비범위

- native app packaging
- pyinstaller/briefcase/installer 생성
- OS별 코드 서명/배포 채널 구축
- GUI 전용 output schema

## P2 / Q58. GUI Smoke And Contract Test Expansion

### 목표

Q54-Q57로 GUI wrapper 주변 기능이 늘어난 뒤에도 CLI `Config`/산출물 계약에서 벗어나지 않도록 headless smoke와 contract test를 확장한다. 실제 Tk window를 요구하지 않는 runner/module 수준 테스트를 우선한다.

### 구현 범위

- `tests/test_gui_runner.py`
  - single config option mapping에 password, page_workers, debug, verbose, skip_existing 추가
  - batch config option mapping과 CLI batch naming contract를 별도 테스트로 고정
  - missing `pdf2md-gui` entry point는 warning이고 module 실행은 계속 가능하다는 diagnostic contract 고정
  - duplicate batch stem validation 고정
  - option fingerprint의 deterministic/sensitive 속성 고정
  - 기존 help smoke, output equality, warning summary, cancel/retry tests와 함께 GUI wrapper contract를 방어
- `tests/test_docs_examples.py`
  - Q58 완료 후 active backlog/spec 없음 상태와 Q34-Q58 archive 범위를 고정

### 구현 결과

- GUI option mapping이 CLI `Config`와 달라지면 headless test가 실패한다.
- batch output naming, duplicate stem rejection, skip-existing, cancel/retry summary, diagnostic warning 정책이 테스트로 고정됐다.
- GUI 관련 tests는 실제 창을 띄우지 않고 CI Python 3.11/3.14에서 실행된다.

### 비범위

- GUI visual regression screenshot
- native desktop UI automation
- 새 public JSON schema

## P2 / Q59. GUI User Guide And Help Entry

### 목표

CLI 문서와 분리된 GUI 전용 사용자 가이드를 추가해, 비개발자가 GUI 화면만 기준으로 변환, 결과 확인, 문제 진단을 진행할 수 있게 한다. GUI 실행 화면에서도 Help 버튼으로 해당 문서를 바로 열 수 있게 한다.

### 구현 범위

- `docs/GUI_USER_GUIDE.md`
  - GUI 실행 방법
  - 화면 구성
  - 단일 PDF 변환
  - 폴더 배치 변환
  - Results 표 읽는 법
  - status 의미
  - Start/Cancel/Open output folder/Help 버튼 동작
  - Tkinter, entry point, output folder, OCR, 표/이미지 문제 진단
- `pdf2md/gui.py`
  - `gui_user_guide_path()` 추가
  - Help 버튼 추가
  - 로컬 `docs/GUI_USER_GUIDE.md`를 열고, 문서가 없으면 조치 가능한 warning 표시
- `README.md`, `docs/MACOS_GUI_QUICKSTART.md`, `docs/WINDOWS_A_TO_Z_GUIDE.md`
  - GUI 전용 사용자 가이드 링크와 Help 버튼 안내 추가
- `tests/test_docs_examples.py`, `tests/test_gui_runner.py`
  - GUI guide 핵심 문구와 Help path contract 고정

### 구현 결과

- GUI 사용법이 CLI 문서에서 분리된 독립 문서로 제공된다.
- GUI 화면에서 `Help` 버튼으로 사용자 가이드를 열 수 있다.
- `python -m pdf2md.gui --help`는 계속 GUI 창을 띄우지 않는다.

### 비범위

- GUI embedded rich help viewer
- native installer에 docs resource bundling
- CLI 사용법 확장
- 새 public JSON schema

## P1 / Q60. GUI Practical UX And Distribution Hardening

### 목표

Q59 이후 실제 GUI 사용 흐름에서 남는 마찰을 줄인다. 진행 상태 가시성, 변환 결과 파일 접근, 반복 사용 시 최근 경로 복구, 비개발자 배포 경로 판단을 개선하되, CLI `Config` / `run_conversion` / output schema 계약은 바꾸지 않는다.

### 구현 범위

- `pdf2md/gui_state.py`
  - GUI recent path state helper 추가
  - 최근 input file, input folder, output folder를 local-only JSON으로 저장/복구
  - corrupt/missing/unknown state fallback
  - selected result artifact open target helper
  - document-level batch progress snapshot helper
- `pdf2md/gui.py`
  - status label과 progressbar 추가
  - 단일 변환은 indeterminate progress로 표시
  - 폴더 배치 변환은 document index/total 기반 determinate progress로 표시
  - 결과 행 선택 후 `Open Markdown`, `Open Report`, `Open Manifest`, `Open Assets`, `Open output folder` 지원
  - `Clear recent` 버튼 추가
  - GUI 시작 시 최근 경로를 보수적으로 복구
- 문서
  - README, GUI user guide, macOS quickstart, Windows guide에 Q60 UX와 배포 판단 반영
  - 기본 비개발자 배포 경로는 source/ZIP + venv setup + `python -m pdf2md.gui`로 유지
  - PyInstaller/native bundle은 Tkinter/PyMuPDF/Tesseract/code signing smoke가 정리되기 전까지 공식 기본 경로로 승격하지 않음
- 테스트
  - `tests/test_gui_state.py`로 recent state, corrupt fallback, clear, open target, progress snapshot 검증
  - `tests/test_docs_examples.py`로 문서 계약 갱신

### 구현 결과

- GUI가 최근 입력/출력 경로를 저장하고 재시작 시 복구한다.
- 사용자가 Results 행에서 Markdown/report/manifest/assets/output folder를 바로 열 수 있다.
- progressbar와 status label이 GUI 작업 상태를 보여준다.
- `python-tk@3.14` 설치 후 macOS에서 실제 Tkinter GUI launch를 확인했다.
- PR #37에서 CI Python 3.11/3.14가 통과했고 `main`에 merge됐다.

### 검증

- `.venv311/bin/python -m pytest`
- `python3 -m pdf2md.gui --help`
- `git diff --check`
- macOS Python/Tkinter GUI window launch smoke

### 비범위

- PDF/Markdown preview 또는 editor
- core pipeline page-level progress callback
- native installer, code signing, notarization, auto-update
- PyInstaller artifact 공식 배포
- 새 public JSON schema

## P1 / Q61. GUI Localization, Presets, And Progress Percent

### 목표

Q60 이후 실제 GUI 확인에서 나온 요구를 반영해, GUI를 한국어 기본 UI로 제공하고 English 전환을 지원한다. 또한 처음부터 세부 flag를 직접 고르게 하지 않고 목적 기반 preset을 제공하며, 신뢰 가능한 document-level batch progress percent를 함께 표시한다. CLI `Config`, core `run_conversion`, output schema 계약은 유지한다.

### 구현 범위

- `pdf2md/gui_i18n.py`
  - `ko`, `en` GUI 문자열 catalog 추가
  - `normalize_language()`와 `translate()` helper 추가
  - missing key는 English/key fallback으로 GUI 시작 실패를 피함
  - warning code, report/manifest key, PDF 원문 내용은 번역하지 않음
- `pdf2md/gui_presets.py`
  - `preserve`, `rag_optimized`, `custom` preset 추가
  - `preserve`는 referenced image, auto table, no RAG table sidecar, heuristic flags off
  - `rag_optimized`는 RAG table sidecar, page marker, header/footer removal, hyphenation repair를 켜되 `force_ocr`는 강제하지 않음
  - `custom`은 현재 UI 값을 보존하고 세부 옵션 편집을 허용
- `pdf2md/gui_state.py`
  - schema version 2로 language/preset preference 저장
  - Q60 schema version 1 state를 tolerant load
  - recent path 저장 정책은 local-only로 유지
- `pdf2md/gui.py`
  - language selector 추가
  - preset selector 추가
  - `custom`이 아닌 preset에서는 세부 변환 옵션을 disabled/readonly 처리
  - batch progress label에 `current/total (percent%)` 표시
  - single conversion은 indeterminate 상태를 유지하고 완료 시 `100%` 표시
- 문서와 테스트
  - README, GUI user guide, macOS quickstart, Windows guide에 Q61 UX 설명 추가
  - `tests/test_gui_i18n.py`, `tests/test_gui_presets.py`, `tests/test_gui_state.py`, `tests/test_docs_examples.py`로 계약 고정

### 구현 결과

- GUI 기본 표시 언어가 한국어로 전환됐고, English 선택을 local-only state로 저장/복구한다.
- 사용자는 `기본 모드(원본 유지)`, `RAG 등록용(최적화)`, `Optimize Options(유저 선택)` 중 하나를 먼저 선택한다.
- preset 변경은 `pages`, `password`, `OCR lang`, 입력/출력 경로를 덮어쓰지 않는다.
- 폴더 배치 변환은 progressbar와 함께 percent text를 표시한다.
- 단일 PDF 변환은 처리 중 가짜 percent를 만들지 않고 완료 시 `100%`만 표시한다.
- PR #38에서 CI Python 3.11/3.14가 통과했고 `main`에 merge됐다.

### 검증

- `.venv311/bin/python -m pytest`
- `python3 -m pdf2md.gui --help`
- `git diff --check`
- GitHub Actions CI `test (3.11)`, `test (3.14)`

### 비범위

- PDF 원문 내용 번역 또는 localization
- report/manifest schema key 또는 warning code localization
- core pipeline page-level progress callback
- OCR language 자동 선택 또는 문서 언어 감지
- native installer/package 생성
- 새 public JSON schema

## P1 / Q62. GUI Smoke Evidence And Layout Guardrails

### 목표

Q61 GUI 기능이 실제 로컬 환경에서 반복 확인 가능하도록 local-only smoke evidence runner를 제공하고, 긴 한글/영문 label과 preset 상태가 화면/상태 계층에서 누락되지 않도록 headless guardrail을 보강한다. core conversion, Markdown/manifest/report 산출물, public schema, warning code는 변경하지 않는다.

### 구현 범위

- `scripts/run_gui_smoke_evidence.py`
  - `--output-dir`, `--state-path`, `--json-only` 옵션 추가
  - `check_gui_runtime()`, `python -m pdf2md.gui --help`, single/batch `run_gui_conversion()` smoke를 하나의 evidence JSON으로 기록
  - `preserve`, `rag_optimized`, `custom` preset을 runner smoke에 반영
  - evidence에는 absolute path 대신 `<output>`, `<workspace>`, `<home>` style label을 저장
  - 실패 시 non-zero exit code와 actionable summary 제공
- `pdf2md/gui_i18n.py`
  - `GUI_TEXT_TRACKING_KEYS`, `catalog_keys()`, `missing_catalog_keys()` 추가
  - 한국어/영문 catalog key coverage를 headless로 검증 가능하게 함
- `pdf2md/gui_presets.py`
  - `preset_editable_fields()` 추가
  - preset별 option lock/unlock 계약을 Tk window 없이 검증 가능하게 함
- 문서
  - README, GUI user guide, macOS quickstart, Windows guide에 smoke evidence runner와 수동 GUI checklist 설명 추가
  - evidence 포함 가능 정보와 포함 금지 정보를 명확히 분리

### 구현 결과

- GUI smoke evidence runner가 local-only `gui_smoke_evidence.json`을 생성한다.
- evidence에는 runtime diagnostics, help command result, preset/language 상태, sanitized artifact labels, status counts, manual checklist 상태만 남는다.
- 원문 PDF 텍스트, 표 내용, 이미지 내용, 변환 warning message, workspace/home absolute path는 저장하지 않는다.
- 실제 Tk window 확인은 사람이 수행하는 수동 checklist로 유지한다.
- PR #40에서 CI Python 3.11/3.14가 통과했고 `main`에 merge됐다.

### 검증

- `.venv311/bin/python -m pytest`
- `.venv314/bin/python scripts/run_gui_smoke_evidence.py --output-dir /private/tmp/pdf2md-q62-gui-smoke-merge --state-path /private/tmp/pdf2md-q62-gui-smoke-merge/gui_state.json`
- `git diff --cached --check`
- GitHub Actions CI `test (3.11)`, `test (3.14)`

### 비범위

- OS-level 자동 클릭 또는 screenshot visual regression을 CI 필수로 만드는 것
- Computer Use 기반 자동 GUI 클릭을 release gate로 편입
- native installer/package 생성
- core pipeline page-level progress callback
- PDF/Markdown preview/editor
- OCR language 자동 선택 또는 LLM 기반 preset 추천
- public output schema 추가

## P1 / Q63. GUI Backlog Rollover And Forward Specs

### 목표

Q62 구현/merge 이후 stale active backlog를 정리하고, GUI 완성도와 호환성 개선을 위한 Q64-Q67 개발 명세를 한 번에 작성한다. 이 작업은 문서/계획 정합성 개선이며 core conversion, GUI runtime behavior, output schema는 변경하지 않는다.

### 구현 범위

- `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`
  - 완료된 Q62 active 항목 제거
  - Q64-Q67 남은 작업 항목 등록
- `docs/QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md`
  - active development specs를 Q64-Q67로 교체
  - 각 Q 작업의 목표, 구현 범위, 테스트 범위, 비범위 작성
- `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`
  - Q62 구현 결과 archive
  - Q63 명세/구현 결과 archive
- README와 scorecard/test 문서 계약
  - 현재 active backlog 문구를 Q64 기준으로 갱신
  - docs example tests가 stale Q62 active 상태를 허용하지 않도록 갱신

### 구현 결과

- Q62가 implemented archive로 이동했다.
- Q64 Responsive GUI Layout, Q65 Runtime Doctor, Q66 Support Bundle, Q67 Expert Options/Profile specs가 active backlog와 development specs에 등록됐다.
- Q63 자체는 문서 정합성 작업으로 archive에 기록됐다.

### 검증

- `.venv311/bin/python -m pytest tests/test_docs_examples.py`
- `git diff --check`

### 비범위

- Q64-Q67의 실제 GUI 기능 구현
- GUI window layout 변경
- runtime doctor 기능 확장
- support bundle/profile import/export 구현
- public output schema 추가

## P1 / Q64. Responsive GUI Layout And Accessibility Guardrails

### 목표

Q62/Q63 이후 실제 Tk window가 작은 화면, Windows display scaling, 긴 한국어/영문 label에서도 더 안정적으로 동작하도록 GUI layout을 responsive/scrollable 구조로 개선한다. core conversion, CLI option 의미, output schema 계약은 변경하지 않는다.

### 구현 범위

- `pdf2md/gui_layout.py`
  - `GUI_WINDOW_MIN_SIZE`, wrapping length, layout section metadata 추가
  - `gui_layout_text_keys()`, `gui_wrapping_text_keys()`, `gui_scrollable_section_keys()` helper 추가
- `pdf2md/gui.py`
  - root minimum size를 `760x560`으로 낮추고 scrollable canvas body 도입
  - preset radio buttons를 vertical layout으로 변경
  - options form을 single-column responsive layout으로 변경
  - flags는 2-column layout으로 조정
  - command/result action buttons를 grid layout으로 재배치
  - status label wrapping과 progressbar row 분리
  - result table horizontal scrollbar 추가
- 문서/test contract
  - Q64 완료 후 active backlog를 Q65-Q67로 이동
  - docs example tests가 Q64 archive와 Q65-Q67 active 상태를 검증

### 구현 결과

- 작은 window height에서도 main GUI body가 vertical scroll로 접근 가능해졌다.
- 긴 preset/action/status label은 wrapping 대상 metadata로 관리된다.
- options, flags, action button 영역이 좁은 width에서 덜 깨지는 구조로 바뀌었다.
- result table에는 horizontal scrollbar가 추가되어 긴 artifact path를 더 안전하게 확인할 수 있다.

### 검증

- `.venv311/bin/python -m pytest tests/test_gui_layout.py tests/test_gui_i18n.py tests/test_gui_runner.py tests/test_gui_state.py`
- `python3 -m pdf2md.gui --help`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- screenshot visual regression을 CI 필수로 편입
- OS-level click automation
- PDF/Markdown preview/editor
- native installer/package 생성
- runtime doctor 기능 확장

## P1 / Q65. GUI Runtime Doctor And Packaging Compatibility Smoke

### 목표

GUI 실행 전후의 runtime과 packaging 환경을 더 구체적으로 진단한다. Python/Tkinter import만 확인하던 기존 runtime check를 Tcl/Tk patchlevel, display/window availability, optional OCR/Tesseract, Pillow/pypdfium2 import, help document path, package distribution mode까지 구조화된 doctor로 확장한다. 새 public output schema는 만들지 않는다.

### 구현 범위

- `pdf2md/gui_runner.py`
  - `GuiDiagnostic`에 optional `action` 필드와 `advisory` severity를 backward-compatible하게 추가
  - `check_gui_runtime()`가 Tcl/Tk patchlevel, display environment, optional Tk window probe, Pillow/pypdfium2/pytesseract import, Tesseract executable, GUI help document, package distribution mode를 진단하도록 확장
  - `gui_diagnostic_report_to_dict()`, `format_gui_diagnostic_report()` 추가
- `pdf2md/gui.py`
  - `python -m pdf2md.gui --doctor`
  - `python -m pdf2md.gui --doctor --doctor-format json`
- `scripts/run_gui_smoke_evidence.py`
  - runtime section을 `gui_runtime_doctor` evidence로 확장
  - action/path/message를 기존 redaction policy로 sanitized 저장
- 문서/test contract
  - Q65 완료 후 active backlog를 Q66-Q67로 이동
  - README, GUI guide, macOS quickstart, Windows guide에 doctor 명령과 해석 방법 추가

### 구현 결과

- doctor 결과는 `code`, `severity`, `message`, `action` 중심으로 해석 가능하다.
- Tk window creation은 CI/headless 환경에서 실패 조건이 아니라 `advisory`로 기록된다.
- source checkout, editable install, wheel smoke 차이를 package metadata/entry point 진단으로 확인할 수 있다.
- smoke evidence는 원문 PDF 텍스트, 표/이미지 내용, 변환 warning message, workspace/home absolute path를 저장하지 않는 기존 정책을 유지한다.

### 검증

- `.venv311/bin/python -m pytest tests/test_gui_runner.py tests/test_gui_smoke_evidence.py tests/test_docs_examples.py`
- `python3 -m pdf2md.gui --help`
- `python3 -m pdf2md.gui --doctor --doctor-format json`
- `.venv314/bin/python scripts/run_gui_smoke_evidence.py --output-dir /private/tmp/pdf2md-q65-gui-smoke --state-path /private/tmp/pdf2md-q65-gui-smoke/gui_state.json`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- native bundle 생성
- code signing/notarization
- 실제 GUI screenshot regression
- Tesseract 자동 설치
- public output schema 추가

## P2 / Q66. Sanitized GUI Support Bundle

### 목표

GUI 사용자가 문제를 보고할 때 공유할 수 있는 local-only support bundle을 추가한다. bundle은 GUI summary, smoke evidence, runtime diagnostics에서 status count, warning code/count, sanitized artifact labels, environment/runtime code만 추출하고, 원문 PDF 텍스트, 표/이미지 내용, 변환 warning message, home/workspace absolute path는 저장하지 않는다. 새 public output schema는 만들지 않는다.

### 구현 범위

- `pdf2md/gui_support.py`
  - `sanitize_support_path_label()` redaction helper 추가
  - `build_gui_support_bundle()`로 `GuiConversionSummary`, `GuiDiagnosticReport`, `gui_smoke_evidence.json`을 sanitized support payload로 변환
  - `support_bundle_redaction_findings()`로 forbidden value와 absolute path 노출을 검증
  - `write_gui_support_bundle()`와 `render_support_bundle_markdown()`으로 JSON/Markdown support artifact 생성
- `scripts/create_gui_support_bundle.py`
  - runtime doctor와 optional smoke evidence를 기반으로 `gui_support_bundle.json`, `gui_support_bundle.md` 생성
  - `--json-only` 자동화 출력 지원
- 문서/test contract
  - Q66 완료 후 active backlog를 Q67로 이동
  - GUI guide, macOS quickstart, Windows guide, README에 support bundle 공유 정책 추가

### 구현 결과

- support bundle은 public output schema가 아닌 local-only 지원 artifact로 명확히 분리됐다.
- runtime diagnostics는 message/path/action 대신 code/severity/count만 저장한다.
- conversion summary는 status count, warning count/code, retry/skipped 여부, sanitized artifact label만 저장한다.
- smoke evidence는 failed check code, runtime code, runner smoke status count만 요약한다.

### 검증

- `.venv311/bin/python -m pytest tests/test_gui_support.py`
- `.venv311/bin/python -m pytest tests/test_gui_support.py tests/test_gui_runner.py tests/test_gui_smoke_evidence.py tests/test_docs_examples.py`
- `python3 scripts/create_gui_support_bundle.py --output-dir /private/tmp/pdf2md-q66-support --smoke-evidence /private/tmp/pdf2md-q65-gui-smoke/gui_smoke_evidence.json`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- public JSON schema 추가
- 원문 PDF/Markdown 첨부
- GitHub issue 자동 생성 또는 업로드
- GUI 버튼 노출

## P2 / Q67. GUI Expert Options And Profile Import/Export

### 목표

반복 작업자가 preset을 넘어 `page_workers`, `debug`, `verbose` 같은 expert option을 GUI에서 직접 조정하고, local-only profile로 저장/불러올 수 있게 한다. profile JSON은 input/output path, password, PDF 원문 텍스트, 표/이미지 내용, raw Markdown을 저장하지 않으며 public output schema로 취급하지 않는다.

### 구현 범위

- `pdf2md/gui_profiles.py`
  - `gui_profile_payload()`, `write_gui_profile()`, `load_gui_profile()`, `options_from_gui_profile()` 추가
  - schema version/kind, option type, enum value, page worker range, forbidden field를 구조화된 `GuiDiagnosticReport`로 검증
  - password/path/raw content 미저장 정책을 profile payload에 포함
- `pdf2md/gui.py`
  - Expert options section 추가
  - `page_workers`, `debug`, `verbose` GUI controls 추가
  - Import profile / Export profile 버튼 추가
  - page workers numeric guardrail을 GUI diagnostic으로 표시
- `pdf2md/gui_i18n.py`, `pdf2md/gui_layout.py`, `pdf2md/gui_presets.py`
  - 한글/영문 label, layout metadata, preset lock contract 확장
- 문서/test contract
  - Q67 완료 후 active backlog 없음 상태로 전환
  - GUI guide, macOS quickstart, Windows guide, README에 profile local-only 정책 추가

### 구현 결과

- expert options는 `Optimize Options(유저 선택)` preset에서 편집 가능하며 기존 `Config` option 의미와 동일하게 전달된다.
- profile export는 password, input/output path, raw PDF/Markdown/table/image content를 저장하지 않는다.
- profile import는 현재 GUI의 password 같은 profile 비저장 값을 유지하면서 profile option만 적용한다.
- invalid profile은 raw traceback 대신 구조화된 GUI diagnostic으로 표시된다.

### 검증

- `.venv311/bin/python -m pytest tests/test_gui_profiles.py tests/test_gui_presets.py tests/test_gui_layout.py tests/test_gui_i18n.py`
- `.venv311/bin/python -m pytest tests/test_gui_profiles.py tests/test_gui_runner.py tests/test_gui_presets.py tests/test_gui_layout.py tests/test_gui_i18n.py tests/test_docs_examples.py`
- `python3 -m pdf2md.gui --help`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- cloud profile sync
- password 저장
- profile 기반 자동 preset 추천
- OCR language 자동 감지 또는 LLM 기반 preset 추천

## P1 / Q68. GUI Release Gate Integration

### 목표

Q65-Q67로 갖춰진 GUI runtime doctor, headless smoke evidence, sanitized support bundle, expert profile 흐름을 release gate runner의 optional `gui` gate로 연결한다. Tk window를 띄우지 않고 GUI help, doctor JSON, smoke evidence, support bundle redaction 검증을 release 전 자동 점검 경로에 포함한다. smoke evidence/support bundle은 public output schema가 아닌 local-only 지원 artifact로 유지한다.

### 구현 범위

- `scripts/run_release_gates.py`
  - optional `gui` gate 추가
  - `gui:module-help`, `gui:doctor`, `gui:smoke-evidence`, `gui:support-bundle` command record 추가
  - 현재 release runner interpreter에 Tkinter가 없으면 GUI-capable `python3`/`python` 실행기로 headless GUI checks 수행
  - `release_gate_output/gui` 하위에 help/doctor command report와 smoke/support artifact path 기록
  - smoke evidence/support bundle redaction failure exit code를 release gate failure로 전파
- `tests/test_quality_gate_scripts.py`
  - GUI gate command 구성, report path, success summary 검증
  - redaction failure 시 release gate failed 처리 검증
- 문서/test contract
  - README, Windows guide, GUI guide에 optional GUI release gate 명령 추가
  - Q68 완료 후 active backlog를 Q69-Q71로 이동

### 구현 결과

- `--gates gui`로 Tk window 없이 GUI help, doctor, smoke evidence, support bundle을 순차 실행할 수 있다.
- `release_gate_report.json`은 GUI gate별 command/status/report path를 기록한다.
- `scripts/run_gui_smoke_evidence.py` 또는 `scripts/create_gui_support_bundle.py`가 원문 PDF 텍스트, 표/이미지 내용, warning message, absolute path redaction failure로 non-zero를 반환하면 전체 release gate도 실패한다.
- 새 public JSON schema는 추가하지 않았고, GUI evidence/support bundle은 local-only artifact로 유지했다.

### 검증

- `.venv311/bin/python -m pytest tests/test_quality_gate_scripts.py`
- `.venv311/bin/python -m pytest tests/test_gui_smoke_evidence.py tests/test_gui_support.py`
- `.venv311/bin/python scripts/run_release_gates.py --output-dir /private/tmp/pdf2md-q68-gui-gate --gates gui`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- 실제 Tk window screenshot 자동화
- native installer 생성
- 네트워크 기반 배포 검증
- public output schema 추가

## P1 / Q69. Wheel Contents And GUI Help Resource Contract

### 목표

wheel/sdist 배포에서 GUI module, console script metadata, support/profile helper, GUI help document availability가 깨지지 않도록 package artifact 수준의 검증을 강화한다. GUI help는 source checkout의 `docs/GUI_USER_GUIDE.md`를 우선하되, wheel 설치 환경에서는 package resource fallback으로 진단 가능해야 한다.

### 구현 범위

- `pdf2md/gui_help.py`, `pdf2md/resources/GUI_USER_GUIDE.md`
  - source checkout help path와 packaged resource fallback을 분리
  - `gui_user_guide_path()`가 source docs가 없을 때 package resource를 반환하도록 보강
- `pyproject.toml`
  - `pdf2md.resources` package와 `GUI_USER_GUIDE.md` package data 포함
- `scripts/inspect_wheel_contract.py`
  - built wheel에 GUI module, `gui_help.py`, `gui_support.py`, `gui_profiles.py`, packaged help resource가 포함되는지 검사
  - `entry_points.txt`에서 `pdf2md`, `pdf2md-gui` console script metadata 검증
- `scripts/run_release_gates.py`
  - packaging gate에 `packaging:wheel-contract`, `packaging:gui-module-help` command 추가
- 문서/test contract
  - README, Windows guide, GUI guide에 wheel help fallback과 wheel contract report 설명 추가
  - Q69 완료 후 active backlog를 Q70-Q71로 이동

### 구현 결과

- wheel 설치 환경에서 repository-level `docs/`가 없더라도 GUI help document availability를 package resource로 진단할 수 있다.
- packaging gate는 wheel build 이후 `wheel_contract_report.json`을 생성하고, GUI help resource/console scripts/support/profile helper 누락을 실패로 처리한다.
- `python -m pdf2md.gui --help`도 packaging gate에 포함되어 CLI help와 GUI module help를 함께 확인한다.
- 새 public JSON schema는 추가하지 않았고, wheel contract report는 release packaging용 local-only artifact로 유지했다.

### 검증

- `.venv311/bin/python -m pytest tests/test_gui_runner.py tests/test_quality_gate_scripts.py`
- `.venv311/bin/python scripts/run_release_gates.py --output-dir /private/tmp/pdf2md-q69-packaging --gates packaging`
- `python3 -m pdf2md.gui --doctor --doctor-format json`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- PyPI upload
- code signing/notarization
- 외부 네트워크 dependency download 전제
- public output schema 추가

## P2 / Q70. GUI Profile And Support Bundle Failure Fixture

### 목표

실패/partial success 상황에서 GUI support bundle과 profile import가 raw exception/warning/path를 누출하지 않는지 regression fixture를 강화한다. Q66/Q67의 정상/구조 검증 위에 실패 fixture를 더해 local-only 지원 artifact가 count/code/retry signal 중심으로 유지되는지 고정한다.

### 구현 범위

- `pdf2md/gui_profiles.py`
  - invalid `schema_version`, `kind`, unknown option diagnostic이 raw value/path를 echo하지 않도록 보수화
- `tests/test_gui_support.py`
  - partial/failed GUI summary fixture 추가
  - support bundle이 status count, warning code/count, retry candidate만 저장하고 raw warning/exception message와 absolute path를 저장하지 않는지 검증
- `tests/test_gui_profiles.py`
  - invalid profile import diagnostic이 raw path, raw option value, raw content를 message/action/path에 남기지 않는지 검증

### 구현 결과

- support bundle failure fixture는 partial/failed 문서의 warning code/count, status count, retry candidate만 공유 대상으로 남긴다.
- invalid profile diagnostic은 unsupported schema/kind 값과 unknown option 이름을 그대로 출력하지 않는다.
- profile forbidden field는 fixed field name 중심 diagnostic으로 유지하고, raw field value/content는 출력하지 않는다.
- 새 public JSON schema는 추가하지 않았다.

### 검증

- `.venv311/bin/python -m pytest tests/test_gui_support.py tests/test_gui_profiles.py`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- GUI modal click automation
- GitHub issue 자동 생성
- public output schema 추가

## P2 / Q71. Quality Scorecard Refresh And Next Backlog Reassessment

### 목표

Q68-Q70 결과를 반영해 scorecard를 보수적으로 재평가하고, 다음 active backlog를 비워둘지 변환 품질 중심 Q72+를 새로 열지 결정한다.

### 구현 범위

- `docs/QUALITY_SCORECARD.md`
  - Q68-Q70이 릴리스/배포/지원 artifact 신뢰도 개선임을 반영
  - 총점 97/100 유지 근거 기록
- `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`
  - Q71 완료 후 active backlog 없음 상태로 전환
  - 변환 품질 중심 Q72+는 구체적인 corpus failure evidence가 생길 때 새로 열기로 결정
- `docs/QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md`
  - active 개발 명세 없음 상태로 전환
- `tests/test_docs_examples.py`
  - Q71 archive와 active backlog 없음 계약 갱신

### 구현 결과

- scorecard는 **97/100**을 유지한다.
- Q68-Q70은 GUI release gate, wheel packaging/help resource, support/profile failure fixture를 강화했지만 core conversion 품질을 새로 입증한 작업은 아니므로 점수 상승은 보류한다.
- 다음 active backlog는 비워 둔다. Q72+는 실제 변환 품질 regression, real corpus failure, table/layout/OCR evidence처럼 구체적인 입력 증거가 생길 때 새로 등록한다.
- 새 public output schema는 추가하지 않았다.

### 검증

- `.venv311/bin/python -m pytest tests/test_docs_examples.py`
- `.venv311/bin/python -m pytest`
- `git diff --check`

### 비범위

- 변환 heuristic 신규 추가
- Q72+ 선등록
- public output schema 추가

## P1 / Q77. RAG Sibling Chunk Merge

### 목표

짧은 text block retrieval chunk가 과도하게 잘게 나뉘는 문제를 줄이기 위해 같은 page/section/heading context의 인접 `text_block` chunk만 token budget 안에서 병합한다.

### 구현 범위

- `pdf2md/serializers/rag_chunks.py`
  - `merge_sibling_text_chunks()` 추가
  - `chunk_boundary_policy="merged_sibling_text_blocks"`, `merged_source_chunk_ids`, `merged_source_chunk_count`, `merge_strategy` metadata 추가
- `pdf2md/config.py`, `pdf2md/cli.py`, `pdf2md/gui_runner.py`, `pdf2md/batch_runner.py`, `pdf2md/pipeline.py`
  - `rag_merge_sibling_text_chunks` opt-in 옵션 연결
- `pdf2md/gui_presets.py`
  - RAG optimized profile에서 sibling merge 활성화
- `scripts/run_rag_eval.py`
  - `chunk_count`, `merged_chunk_count`, `merged_source_chunk_count`, `average_source_record_count` metric 추가

### 구현 결과

- 기본 preserve 변환은 backward compatible하게 유지한다.
- opt-in/RAG optimized 경로에서는 인접 sibling text block을 source 순서대로만 결합하며 requirement/table/technical/domain chunk는 병합하지 않는다.
- merged chunk는 모든 source id를 `source_refs`와 `source_dedupe_key`로 추적할 수 있다.

### 검증

- `.venv311/bin/python -m pytest`
- `git diff --check`

## P1 / Q78. RAG Chunk Relationship Metadata

### 목표

retrieval chunk 사이의 previous/next/section relationship metadata를 deterministic하게 추가해 citation expansion, UI drilldown, downstream context expansion을 쉽게 만든다.

### 구현 범위

- `pdf2md/serializers/rag_chunks.py`
  - `assign_chunk_relationships()` 추가
  - `previous_chunk_id`, `next_chunk_id`, `section_anchor_chunk_id`, `related_chunk_ids`, `relationship_strategy` optional metadata 추가
- `pdf2md/config.py`, `pdf2md/cli.py`, `pdf2md/gui_runner.py`, `pdf2md/batch_runner.py`, `pdf2md/pipeline.py`
  - `rag_chunk_relationship_metadata` opt-in 옵션 연결
- `scripts/validate_index_contract.py`
  - relationship field type과 target chunk id 존재 여부 검증

### 구현 결과

- relationship metadata는 merge/split 이후 최종 chunk id 기준으로 생성된다.
- 같은 `chunk_group_id` 안에서 prev/next를 연결하고, 같은 `section_path`의 첫 chunk를 section anchor로 참조한다.
- target id는 같은 `retrieval_chunks_rag.jsonl` 안에서 해소 가능해야 한다.

### 검증

- `.venv311/bin/python -m pytest`
- `git diff --check`

## P2 / Q79. Purpose-Specific RAG Profiles

### 목표

단일 `rag_optimized` preset을 보완해 technical spec ingest, confidential sharing, preserve+sidecar 같은 반복 목적을 CLI/GUI에서 같은 option matrix로 재사용하게 한다.

### 구현 범위

- `pdf2md/rag_profiles.py`
  - `preserve`, `rag_optimized`, `technical_spec_rag`, `confidential_rag`, `preserve_with_sidecars` profile matrix 추가
- `pdf2md/cli.py`
  - `--rag-profile` 추가
- `pdf2md/gui_presets.py`, `pdf2md/gui_i18n.py`, `pdf2md/gui_layout.py`, `pdf2md/gui.py`
  - GUI preset 확장, localized label, locked/editable contract 갱신
- 문서
  - README, GUI guide, Windows guide, RAG indexer recipe 갱신

### 구현 결과

- 기존 `preserve`, `rag_optimized`, `custom` GUI 동작은 유지한다.
- CLI와 GUI가 같은 local-only profile matrix를 사용한다.
- profile export/import는 기존처럼 password, path, raw PDF/Markdown/table/image content를 저장하지 않는다.
- 외부 RAG, embedding, indexing 서비스 호출은 추가하지 않았다.

### 검증

- `.venv311/bin/python -m pytest`
- `git diff --check`
