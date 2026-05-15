# Project Quality Scorecard

이 문서는 프로젝트의 성능, 완성도, 운영 준비도를 주기적으로 평가하고 히스토리로 남기기 위한 기록 문서다.

## 운영 규칙

- 평가는 보수적으로 수행한다. 기능이 “있다”보다 실제 PDF에서 반복 검증되고 회귀 방어가 가능한지를 더 중요하게 본다.
- 새 평가를 수행할 때마다 `평가 히스토리`에 새 항목을 추가한다.
- 기존 평가 항목은 삭제하지 않는다. 과거 판단과 점수 변화 흐름을 추적하기 위함이다.
- 앞으로 구현할 작업은 이 문서에 backlog로 관리하지 않는다. 실제 다음 작업은 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에만 기록한다.
- 평가 후 새로 발견한 개선 과제가 있으면 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에 추가하고, 이 문서에서는 해당 Q 번호만 참조한다.
- 점수 기준이나 가중치를 바꾸는 경우, 해당 평가 항목에 변경 이유를 남긴다.

## 평가 기준

총점은 100점 만점이며, 다음 항목을 기준으로 한다.

| 항목 | 배점 | 평가 관점 |
|---|---:|---|
| 핵심 변환 완성도 | 18 | text/table/image/OCR/manifest/report/partial success의 실제 동작 안정성 |
| 표 변환/RAG 대응 | 18 | 단순 표 GFM, 복잡 표 HTML fallback, RAG sidecar, table diagnostics 품질 |
| 텍스트 구조 보존 | 16 | reading order, heading/list/code/footnote, hyphenation, 원문 보존 안정성 |
| 이미지/OCR 신뢰도 | 14 | referenced image, dedupe, crop fallback, OCR runtime/language 진단 |
| 성능/효율 | 12 | page cache, 중복 open 방지, stage duration, benchmark와 회귀 감지 |
| 테스트/결정성/CI | 12 | unit/integration/golden/CLI smoke/CI matrix/결정적 출력 |
| 운영/릴리스 준비도 | 10 | 문서, schema 계약, 배포 smoke, 릴리스 전 품질 게이트 |

배점 합은 100점이며, 항목별 점수 합계를 현재 평가 총점으로 기록한다.

## 현재 스코어보드

| 평가일 | 평가 관점 | 총점 | 이전 대비 | 핵심 근거 |
|---|---|---:|---:|---|
| 2026-05-16 | GUI batch 운영성 | 97/100 | 0 | Q56. GUI Batch Operation Controls 구현. batch progress, document-boundary cancel, failed retry candidate, deterministic ordering/fingerprint 추가. 다음 active backlog는 Q57-Q58 |
| 2026-05-16 | GUI 결과 검토 UX | 97/100 | 0 | Q55. GUI Conversion Result Review UX 구현. 완료 결과 표, artifact path, warning code/count summary 추가. 다음 active backlog는 Q56-Q58 |
| 2026-05-16 | GUI runtime/install 안정성 | 97/100 | 0 | Q54. GUI Runtime And Install Diagnostics 구현. Tkinter/Python/entry point/input/output path 진단을 변환 실패와 분리. 다음 active backlog는 Q55-Q58 |
| 2026-05-16 | GUI 후속 운영 계획 | 97/100 | 0 | Q54-Q58 active backlog 추가. GUI runtime diagnostics, result review UX, batch controls, non-developer distribution guide, GUI smoke/contract tests를 구현 전 문서 계약으로 정리 |
| 2026-05-16 | Storage/PCIe/Security Spec RAG 운영툴 + 사용성 | 97/100 | 0 | Q53. Minimal Desktop GUI Wrapper 구현. 변환 품질 점수는 유지하고, CLI 비숙련 사용자를 위한 간편 실행 UX 추가. active quality backlog 없음 |
| 2026-05-15 | Storage/PCIe/Security Spec RAG 운영툴 | 97/100 | 0 | Q48-Q52로 evidence pack analysis/trend gate, appendix clause fixture, captionless diagnostics, docs/schema history contract를 추가. active quality backlog 없음 |
| 2026-05-15 | Storage/PCIe/Security Spec RAG 운영툴 | 97/100 | 0 | Q47 local technical corpus evidence pack으로 비공개 corpus failure pattern을 redacted signature로 축적 가능. active quality backlog 없음 |
| 2026-05-15 | Storage/PCIe/Security Spec RAG 운영툴 | 97/100 | 0 | Q46 expected source coverage와 Q44 domain technical table typed coverage까지 구현되어 active quality backlog 없음 |
| 2026-05-14 | Storage/PCIe/Security Spec RAG 운영툴 | 97/100 | +3 | corpus/profile/evidence gates, offline index/provenance/artifact validators, layout/table/OCR/diagram golden packs, page-worker table candidate parallelization 구현 |
| 2026-05-13 | Storage/PCIe/Security Spec RAG 운영툴 | 94/100 | +2 | RAG calibration gate, requirement change impact report, domain deep fixtures, indexer recipes, diagram label diagnostics 구현 |
| 2026-05-13 | Storage/PCIe/Security Spec RAG 변환툴 | 92/100 | +5 | domain adapter profile, requirement traceability, technical table sidecar, safe mode, corpus diff, chunk diagnostics 구현 |
| 2026-05-13 | Storage/PCIe/Security Spec RAG 변환툴 | 87/100 | +2 / -4 | NVMe/OCP/PCIe/TCG/customer spec 기준으로는 domain table, requirement traceability, confidential-safe 운영 보강 필요 |
| 2026-05-13 | RAG용 PDF to MD 변환툴 | 91/100 | +6 | RAG text/semantic/retrieval/figure/domain/corpus sidecar, schema 계약, CI 3.11/3.14 통과 |
| 2026-05-11 | 범용 PDF to MD 변환툴 | 85/100 | - | 기본 변환, table/image/OCR/report 기반은 양호하나 schema/release/RAG semantic 계층은 미완 |

## 평가 히스토리

### 2026-05-16 (Q56 구현 후)

#### 총평

현재 프로젝트를 **Storage/PCIe/Security Spec용 RAG 운영툴 + 간편 GUI 사용성** 관점으로 보면 **97/100점** 수준을 유지한다.

Q56은 폴더 배치 변환 운영성을 보강했다. 진행률 callback, 문서 경계 취소, 실패 문서 retry candidate, deterministic option fingerprint를 GUI runner에 추가했으며, core 변환 산출물 계약은 변경하지 않았다.

#### 다음 개선 참조

- Q57. Non-Developer GUI Distribution Guide
- Q58. GUI Smoke And Contract Test Expansion

### 2026-05-16 (Q55 구현 후)

#### 총평

현재 프로젝트를 **Storage/PCIe/Security Spec용 RAG 운영툴 + 간편 GUI 사용성** 관점으로 보면 **97/100점** 수준을 유지한다.

Q55는 변환 품질 자체가 아니라 GUI 사용자가 결과 품질을 확인하는 진입점을 보강한 작업이다. 문서별 status, Markdown/report/manifest 경로, warning count/code를 표시하되 원문 텍스트/표/이미지 내용을 GUI summary에서 재서술하지 않는다.

#### 다음 개선 참조

- Q56. GUI Batch Operation Controls
- Q57. Non-Developer GUI Distribution Guide
- Q58. GUI Smoke And Contract Test Expansion

### 2026-05-16 (Q54 구현 후)

#### 총평

현재 프로젝트를 **Storage/PCIe/Security Spec용 RAG 운영툴 + 간편 GUI 사용성** 관점으로 보면 **97/100점** 수준을 유지한다.

Q54는 변환 품질을 직접 높이는 작업이 아니라, GUI 사용자가 변환 엔진에 도달하기 전 겪는 runtime/install/path 문제를 더 명확히 진단하는 운영 안정성 보강이다. Tkinter 미설치, Python 버전 불일치, `pdf2md-gui` entry point 누락, input/output path 문제를 구조화된 diagnostic으로 구분한다.

#### 다음 개선 참조

- Q55. GUI Conversion Result Review UX
- Q56. GUI Batch Operation Controls
- Q57. Non-Developer GUI Distribution Guide
- Q58. GUI Smoke And Contract Test Expansion

### 2026-05-16 (Q54-Q58 계획 수립)

#### 총평

현재 프로젝트를 **Storage/PCIe/Security Spec용 RAG 운영툴 + 간편 GUI 사용성** 관점으로 보면 **97/100점** 수준을 유지한다.

이번 변경은 구현 완료 평가가 아니라 Q53 이후 발견된 GUI 운영 후속 과제를 active backlog와 개발 명세로 정리한 것이다. 변환 엔진 품질, schema, 산출물 계약은 변하지 않았으므로 점수는 유지한다.

#### 다음 개선 참조

- Q54. GUI Runtime And Install Diagnostics
- Q55. GUI Conversion Result Review UX
- Q56. GUI Batch Operation Controls
- Q57. Non-Developer GUI Distribution Guide
- Q58. GUI Smoke And Contract Test Expansion

### 2026-05-16 (Q53 구현 후)

#### 총평

현재 프로젝트를 **Storage/PCIe/Security Spec용 RAG 운영툴**로 보면 **97/100점** 수준을 유지한다.

Q53은 core 변환 품질을 바꾸는 작업이 아니라, CLI에 익숙하지 않은 사용자도 파일 또는 폴더를 선택해 변환할 수 있게 하는 최소 desktop GUI wrapper 구현이다. `pdf2md.gui_runner`가 기존 `Config`와 `run_conversion` 경로를 그대로 사용하고, `pdf2md.gui`는 Tkinter 기반 입력/옵션 선택, worker thread 실행, 로그와 완료 summary 표시를 제공한다.

#### 다음 개선 참조

현재 active quality backlog는 없다.

### 2026-05-15 (Q48-Q52 구현 후)

#### 총평

현재 프로젝트를 **Storage/PCIe/Security Spec용 RAG 운영툴**로 보면 **97/100점** 수준을 유지한다.

Q48-Q52는 Q47 evidence pack을 운영 신호로 더 잘 쓰기 위한 후속 작업이다. 단일 evidence pack 분석 report, baseline/current trend comparison gate, appendix/nested clause/vendor requirement table fixture, captionless diagram diagnostics-only 기록, 그리고 schema/docs history contract가 추가됐다.

점수를 올리지 않는 이유는 이 작업들이 실제 대형 corpus 품질을 새로 입증했다기보다, 비공개 corpus에서 발견되는 실패를 더 안전하게 분류하고 장기 추적하는 운영 장치를 보강한 성격이 강하기 때문이다. 현재 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에는 active quality backlog가 없다.

#### 세부 점수

| 항목 | 점수 | 직전 평가 대비 | 평가 |
|---|---:|---:|---|
| 핵심 변환 완성도 | 18/18 | 0 | 변환 본문 경로는 유지하고 evidence 분석/비교와 focused fixture를 추가했다. |
| 표 변환/RAG 대응 | 18/18 | 0 | appendix nested clause의 requirement table row, technical table row, customer requirement domain unit provenance를 회귀 테스트로 고정했다. |
| 텍스트 구조 보존 | 15/16 | 0 | appendix heading과 nested clause heading carry-over가 개선됐지만 실제 장문 private corpus 증거는 계속 운영 중 축적해야 한다. |
| 이미지/OCR 신뢰도 | 13/14 | 0 | captionless low-confidence OCR 후보가 hallucinated caption 없이 diagnostics-only로 남도록 고정했다. |
| 성능/효율 | 11/12 | 0 | 성능 경로 변경은 없고, evidence trend gate가 장기 운영 신호를 남긴다. |
| 테스트/결정성/CI | 12/12 | 0 | schema export list와 OUTPUT_SCHEMA 문서 목록 일치, evidence tool smoke, focused regression이 추가됐다. |
| 운영/릴리스 준비도 | 10/10 | 0 | private corpus evidence pack을 분석하고 baseline/current signature trend로 gate할 수 있는 local-only 운영 절차가 문서화됐다. |

#### 다음 개선 참조

현재 active quality backlog는 없다.

향후 Q는 실제 private/large corpus evidence pack에서 반복되는 added/persisting error signature가 확인될 때 새 번호로 추가한다.

### 2026-05-15 (Q47 구현 후)

#### 총평

현재 프로젝트를 **Storage/PCIe/Security Spec용 RAG 운영툴**로 보면 **97/100점** 수준을 유지한다.

Q47로 `run_ssd_corpus_profile.py`가 `local_corpus_evidence_pack.json`을 opt-in 생성할 수 있게 됐다. 이 산출물은 비공개/대형 technical corpus의 conversion, SSD RAG contract, RAG threshold, budget failure를 raw path, command, document name, query text 없이 deterministic signature로 공유하기 위한 것이다.

점수를 올리지 않는 이유는 Q47이 실제 대형 corpus evidence 자체를 repo에 추가한 것이 아니라, 해당 evidence를 안전하게 축적하고 공유하는 운영 경로를 만든 작업이기 때문이다. 텍스트 구조, caption 없는 diagram, 성능 대형 corpus 리스크는 기존 97/100 평가와 동일하게 보수적으로 유지한다. 현재 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에는 active quality backlog가 없다.

#### 세부 점수

| 항목 | 점수 | 직전 평가 대비 | 평가 |
|---|---:|---:|---|
| 핵심 변환 완성도 | 18/18 | 0 | 기존 변환 경로는 변경하지 않고 local corpus profile 후처리 산출물을 opt-in 추가했다. |
| 표 변환/RAG 대응 | 18/18 | 0 | SSD contract와 RAG threshold failure가 evidence signature로 집계되어 table/domain failure pattern 추적이 쉬워졌다. |
| 텍스트 구조 보존 | 15/16 | 0 | 긴 clause/appendix carry-over 자체를 새로 확장하지는 않았고, 해당 실패가 발견되면 signature로 관리할 수 있다. |
| 이미지/OCR 신뢰도 | 13/14 | 0 | caption 없는 diagram/OCR label 의미 해석은 여전히 보수적 opt-in 영역이다. |
| 성능/효율 | 11/12 | 0 | 성능 threshold failure를 evidence signature로 보존하지만 새 병렬화나 benchmark 기준 변경은 없다. |
| 테스트/결정성/CI | 12/12 | 0 | evidence pack fingerprint/signature id, schema export, redaction 테스트가 결정적 출력 계약을 방어한다. |
| 운영/릴리스 준비도 | 10/10 | 0 | private corpus failure pattern을 raw artifact 없이 공유하는 운영 경로와 public schema가 추가됐다. |

#### 다음 개선 참조

현재 active quality backlog는 없다.

Q47 evidence pack에서 반복 signature가 쌓이면, 해당 signature를 근거로 appendix/nested clause fixture, captionless diagram diagnostics, vendor requirement table coverage 같은 새 Q 항목을 추가한다.

### 2026-05-15 (Q46/Q44 구현 후)

#### 총평

현재 프로젝트를 **Storage/PCIe/Security Spec용 RAG 운영툴**로 보면 **97/100점** 수준을 유지한다.

Q46으로 RAG golden query가 `expected_source_ids`와 `expected_source_types`를 검증하고, Q44로 NVMe/PCIe/OCP/TCG technical table row의 typed coverage와 `technical_table_unit` provenance가 보강됐다. 2026-05-14 평가에서 다음 작업으로 지목했던 두 병목은 실제 코드, golden fixture, release gate wiring, GitHub Actions CI까지 반영되어 닫혔다.

점수를 100점으로 올리지 않는 이유는 남은 리스크가 “다음에 구현할 명확한 backlog”라기보다, 공개 저장소에 넣기 어려운 실제 대형/비공개 technical corpus에서 장기적으로 더 많은 증거를 쌓아야 하는 영역이기 때문이다. 현재 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에는 active quality backlog가 없다.

#### 세부 점수

| 항목 | 점수 | 직전 평가 대비 | 평가 |
|---|---:|---:|---|
| 핵심 변환 완성도 | 18/18 | 0 | text/table/image/OCR/manifest/report/partial success 경로가 golden corpus와 release gate에서 안정적으로 유지된다. |
| 표 변환/RAG 대응 | 18/18 | 0 | table row, technical table, domain unit, requirement trace가 retrieval chunks와 expected source coverage 검증에 연결된다. Q44 이후 TCG security method/object/authority/field typed unit도 회귀 테스트로 고정됐다. |
| 텍스트 구조 보존 | 15/16 | 0 | layout stress, header/footer, hyphenation, heading/list/code/footnote fixture가 회귀를 방어한다. 매우 긴 clause/appendix carry-over는 실제 corpus evidence가 더 쌓이면 재평가한다. |
| 이미지/OCR 신뢰도 | 13/14 | 0 | rendered diagram fixture와 OCR confidence calibration이 안정적이다. caption 없는 diagram 의미 해석은 여전히 opt-in 영역으로 남긴다. |
| 성능/효율 | 11/12 | 0 | page cache와 page-worker text/read-order/table-candidate 병렬 경로가 worker count별 동일성 검증과 benchmark smoke에 연결됐다. |
| 테스트/결정성/CI | 12/12 | 0 | 전체 pytest, golden corpus, schema check, GitHub Actions Python 3.11/3.14가 결정적 출력 계약을 방어한다. |
| 운영/릴리스 준비도 | 10/10 | 0 | schema, release gates, offline index/provenance/artifact validators, README/Windows 운영 문서가 local-only 운영 흐름을 설명한다. |

#### 남은 리스크

- 비공개/대형 실제 technical corpus는 repo golden fixture로 직접 커밋하지 않으므로, 장기 운영 중 새 failure pattern이 발견되면 별도 Q 항목으로 추가해야 한다.
- 외부 OpenAI/Azure/LangChain/LlamaIndex index upload 자체는 의도적으로 local validator 범위 밖이다.
- caption 없는 diagram의 의미 해석이나 OCR 기반 label 승격은 환각 방지를 위해 보수적으로 남겨둔다.
- 매우 긴 appendix, nested clause, vendor-specific requirement table은 현재 fixture보다 넓은 corpus evidence가 생길 때 추가 검증 후보가 된다.

#### 다음 개선 참조

현재 active quality backlog는 없다.

새 개선 과제가 발견되면 먼저 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에 신규 Q 항목을 추가하고, active 개발 명세는 `docs/QUALITY_IMPROVEMENT_DEVELOPMENT_SPECS.md`에 작성한다. 완료된 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.

#### 검증 기준

- Q46 PR #25: GitHub Actions Python 3.11, 3.14 통과
- Q44 PR #26: GitHub Actions Python 3.11, 3.14 통과
- `env PYTHONPATH=. pytest`
- `env PYTHONPATH=. /Library/Frameworks/Python.framework/Versions/3.9/bin/python3 scripts/export_output_schema.py --check`
- `git diff --check`

### 2026-05-14 (Q31-Q42 구현 후)

#### 총평

현재 프로젝트를 **Storage/PCIe/Security Spec용 RAG 운영툴**로 보면 **97/100점** 수준으로 평가한다.

직전 Q26-Q30 구현 후 평가 94/100점 대비 **+3점** 상승했다. 상승 요인은 local corpus profile runner, requirement impact review pack, technical cross-reference hardening, offline index contract validator, rendered diagram fixture suite, cross-sidecar provenance validator, layout/table/OCR/artifact integrity gates, 그리고 Q42의 page-worker table candidate 병렬화가 모두 실제 검증 경로에 들어간 점이다.

아직 100점으로 보지는 않는다. 남은 리스크는 기능의 존재 여부보다 **대표 RAG 질의와 expected source id coverage**, 그리고 **도메인 technical table typed coverage**가 실제 NVMe/PCIe/OCP/TCG 운영 질문을 얼마나 잘 막아내는지에 있다. 다음 작업은 이 두 영역을 우선한다.

#### 세부 점수

| 항목 | 점수 | 직전 평가 대비 | 평가 |
|---|---:|---:|---|
| 핵심 변환 완성도 | 18/18 | +1 | text/table/image/OCR/manifest/report/partial success 경로가 golden corpus와 release gate에서 안정적으로 유지된다. |
| 표 변환/RAG 대응 | 18/18 | 0 | table row, technical table, domain unit, requirement trace가 RAG sidecar와 retrieval chunks에 연결된다. 다만 도메인별 typed field coverage는 다음 개선 대상이다. |
| 텍스트 구조 보존 | 15/16 | 0 | layout stress, header/footer, hyphenation, heading/list/code/footnote fixture가 회귀를 방어한다. 긴 표준 문서의 nested clause coverage는 추가 여지가 있다. |
| 이미지/OCR 신뢰도 | 13/14 | 0 | rendered diagram fixture와 OCR confidence calibration으로 provenance 품질은 좋아졌다. caption 없는 diagram 의미 해석은 의도적으로 opt-in 영역에 남긴다. |
| 성능/효율 | 11/12 | +1 | page cache와 page-worker text/read-order/table-candidate 병렬 경로가 worker count별 동일성 검증과 benchmark smoke에 연결됐다. |
| 테스트/결정성/CI | 12/12 | 0 | 전체 pytest, golden corpus, schema check, GitHub Actions Python 3.11/3.14가 결정적 출력 계약을 방어한다. |
| 운영/릴리스 준비도 | 10/10 | +1 | schema, release gates, offline index/provenance/artifact validators, Windows/README 운영 문서가 실제 local-only 운영 흐름을 설명한다. |

#### 남은 리스크

- 대표 RAG query set의 expected source id coverage가 아직 점수 상승의 가장 직접적인 병목이다.
- `technical_tables_rag.jsonl`은 유용하지만 register map, bitfield, opcode, log page, security method/object/security field typed coverage를 더 넓혀야 한다.
- domain adapter 출력은 보수적으로 동작하지만, 도메인별 golden query와 table-field coverage가 더 강해지면 운영 신뢰도가 올라간다.
- 긴 clause/appendix/requirement table 주변 heading carry-over는 현재 안전하지만 더 넓은 fixture로 고정할 가치가 있다.

#### 다음 개선 참조

Q31-Q42는 완료되어 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에서 제거했다. 다음 작업은 평가 병목을 직접 줄이는 순서로 진행한다.

- Q46. RAG Golden Query Expected Source Coverage
- Q44. Domain Technical Table Coverage Expansion

#### 검증 기준

- `env PYTHONPATH=. pytest`
- `env PYTHONPATH=. /Library/Frameworks/Python.framework/Versions/3.9/bin/python3 scripts/export_output_schema.py --check`
- `git diff --check`
- GitHub Actions CI: PR #23에서 Python 3.11, 3.14 통과

### 2026-05-13 (Q26-Q30 구현 후)

#### 총평

현재 프로젝트를 **NVMe/PCIe/OCP/TCG/고객 Requirement Spec용 RAG 운영툴**로 보면 **94/100점** 수준으로 평가한다.

직전 Q16-Q25 구현 후 평가 92/100점 대비 **+2점** 상승했다. 상승 요인은 `scripts/run_rag_eval.py`의 calibration threshold, `scripts/run_release_gates.py`의 optional `rag` gate, batch mode의 `requirement_change_impact_report.json`, 도메인별 deep fixture, indexer integration recipe, `figures_rag.jsonl`의 diagram label confidence diagnostics가 실제 운영 경로에 들어간 점이다.

아직 95점 이상으로 보지는 않는다. 실제 공개 스펙/고객 유사 corpus는 보안 정책상 repo에 커밋하지 않고 로컬 profile로만 운영하므로, corpus-level aggregate runner와 rendered diagram fixture suite가 더 필요하다.

#### 세부 점수

| 항목 | 점수 | 직전 평가 대비 | 평가 |
|---|---:|---:|---|
| 핵심 변환 완성도 | 17/18 | 0 | 기본 변환 안정성과 partial success 정책은 유지됐다. 새 운영 sidecar는 기존 Markdown 정본을 침범하지 않는다. |
| 표 변환/RAG 대응 | 18/18 | +1 | table row, technical table, domain unit, requirement trace가 retrieval/eval gate와 연결됐다. |
| 텍스트 구조 보존 | 15/16 | 0 | 원문 requirement diff provenance를 보존하고, 요약/재서술 없이 변경 영향 분석 입력을 제공한다. |
| 이미지/OCR 신뢰도 | 13/14 | +1 | diagram OCR/label 후보를 confidence 기준으로 promoted/rejected diagnostics에 분리한다. |
| 성능/효율 | 10/12 | 0 | conversion duration과 chunk token 분포가 RAG calibration gate에 포함됐다. 대량 corpus aggregate runner는 다음 단계다. |
| 테스트/결정성/CI | 12/12 | 0 | `143 tests collected`, 전체 pytest, schema check, GitHub Actions Python 3.11/3.14 통과로 회귀 방어가 좋다. |
| 운영/릴리스 준비도 | 9/10 | 0 | indexer recipe, calibration profile, schema 계약이 보강됐다. offline index contract validator는 아직 남았다. |

#### 다음 개선 참조

Q26-Q30은 완료되어 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에서 제거했다. 다음 RAG 운영 목적 개선 과제는 Q31-Q35로 정리했다.

- Q31. Local Corpus Profile Runner
- Q32. Requirement Impact Review Pack
- Q33. Technical Cross-Reference Resolver Hardening
- Q34. Offline Index Contract Validator
- Q35. Rendered Diagram Fixture Suite

#### 검증 기준

- `./.venv311/bin/python -m pytest -q`: 정상
- `./.venv311/bin/python scripts/export_output_schema.py --check`: 정상
- `git diff --check`: 정상
- `./.venv311/bin/python -m pdf2md --help`: 정상
- GitHub Actions CI: PR #17/#18에서 Python 3.11, 3.14 통과

### 2026-05-13 (Q16-Q25 구현 후)

#### 총평

현재 프로젝트를 **NVMe/PCIe/OCP/TCG/고객 Requirement Spec용 RAG 변환툴**로 보면 **92/100점** 수준으로 평가한다.

직전 기술 스펙 기준 평가 87/100점 대비 **+5점** 상승했다. 상승 요인은 도메인 adapter profile 확장, `requirement_traceability_rag.jsonl`, `technical_tables_rag.jsonl`, technical cross-reference, chunk boundary diagnostics, confidential safe mode, corpus diff report가 실제 RAG 운영 흐름에 들어간 점이다.

아직 95점 이상으로 보지는 않는다. 실제 공개/사내 대표 corpus threshold, 버전 간 requirement impact matrix, 도메인별 deep fixture, diagram OCR calibration은 다음 작업으로 남아 있다.

#### 세부 점수

| 항목 | 점수 | 직전 기술 스펙 평가 대비 | 평가 |
|---|---:|---:|---|
| 핵심 변환 완성도 | 17/18 | 0 | 기본 변환 안정성은 유지했고 새 sidecar가 기존 Markdown 정책을 침범하지 않는다. |
| 표 변환/RAG 대응 | 17/18 | +2 | `technical_tables_rag.jsonl`로 register/bitfield/opcode/log page/feature/security table row를 typed provenance로 제공한다. |
| 텍스트 구조 보존 | 15/16 | +1 | requirement trace와 technical cross-reference가 heading/source_refs와 더 잘 연결된다. |
| 이미지/OCR 신뢰도 | 12/14 | +1 | `figures_rag.jsonl`에 conservative `figure_kind`, diagram candidate, label metadata를 추가했다. |
| 성능/효율 | 10/12 | 0 | corpus diff report가 재색인 최소화 기반을 제공한다. 실제 대량 corpus benchmark gate는 아직 필요하다. |
| 테스트/결정성/CI | 12/12 | +1 | 신규 unit/CLI/golden/schema 테스트와 golden corpus 갱신으로 결정적 출력 계약을 유지했다. |
| 운영/릴리스 준비도 | 9/10 | 0 | confidential safe mode와 schema/docs가 보강됐다. 실 corpus 운영 runbook은 다음 단계다. |

#### 다음 개선 참조

Q16-Q25는 완료되어 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에서 제거했다. 다음 RAG 운영 목적 개선 과제는 Q26-Q30으로 재정리했다.

- Q26. Real Technical Corpus Calibration Gate
- Q27. Requirement Change Impact Matrix
- Q28. Domain Adapter Deep Fixtures
- Q29. RAG Indexer Integration Recipes
- Q30. Diagram OCR And Label Recovery Calibration

### 2026-05-13 (NVMe/PCIe/OCP/TCG/고객 Requirement Spec 기준)

#### 총평

현재 프로젝트를 **기술 스펙 기반 RAG 변환툴**로 보면 **87/100점** 수준으로 평가한다.

이 점수는 기존 2026-05-13의 일반 RAG 평가 91/100점보다 **4점 낮다**. 기능 퇴보가 아니라 평가 관점이 더 엄격해졌기 때문이다. NVMe, PCIe, OCP Datacenter NVMe SSD, TCG, 고객 Requirement Spec은 단순 섹션 검색보다 `Requirement ID`, `shall/must` 규범 문장, command/opcode/log page/register/bitfield 표, 보안 method/object, cross reference, traceability, 대외비 운영 안정성이 더 중요하다.

공개 표준 문서 기준으로도 NVMe specification set은 command set, transports, data structures, features, log pages, commands, status values를 분리해 다루고, PCIe Base는 architecture/interconnect/programming interface와 ECN 흐름이 강하다. OCP Datacenter NVMe SSD 문서는 `Requirement ID / Description` 표가 반복되고, TCG storage 쪽은 SED, key management, storage security subsystem, method/object 성격의 자료가 핵심이다.

#### 세부 점수

| 항목 | 점수 | 일반 RAG 평가 대비 | 평가 |
|---|---:|---:|---|
| 핵심 변환 완성도 | 17/18 | 0 | 기본 text/table/image/OCR/manifest/report와 partial success는 안정적이다. 기술 스펙의 원문 보존 요구에는 잘 맞는다. |
| 표 변환/RAG 대응 | 15/18 | -1 | table RAG와 HTML fallback은 강점이다. 다만 register map, bitfield, command dword, opcode, log page, security table을 별도 typed sidecar로 안정 추출하는 수준은 아직 부족하다. |
| 텍스트 구조 보존 | 14/16 | -1 | heading/list/code/footnote 구조화는 좋아졌지만, 긴 표준 문서의 nested clause, appendix, requirement table 주변 heading carry-over는 추가 검증이 필요하다. |
| 이미지/OCR 신뢰도 | 11/14 | -1 | figure provenance는 생겼지만 PCIe/NVMe/TCG의 state machine, sequence diagram, register layout figure를 RAG에서 의미 있게 찾는 수준은 아직 제한적이다. |
| 성능/효율 | 10/12 | 0 | page cache와 batch/corpus manifest 기반은 좋다. 수백 페이지 표준 문서 묶음에서 incremental diff와 재색인 최소화는 다음 단계다. |
| 테스트/결정성/CI | 11/12 | -1 | deterministic output과 CI는 강하다. 도메인별 golden query, expected source id, requirement/table-field coverage가 부족해 1점 감점한다. |
| 운영/릴리스 준비도 | 9/10 | 0 | schema와 문서화는 좋다. 고객 대외비 자료 운영을 위해 privacy/safe mode, path redaction, sanitized report가 필요하다. |

#### 도메인별 적합도

| 도메인 | 현재 적합도 | 판단 |
|---|---:|---|
| NVMe / NVMe Command Set | 88/100 | 현재 `--domain-adapter nvme`와 RAG sidecar 구조가 가장 잘 맞는다. command, opcode, log page, feature id, status value coverage는 더 필요하다. |
| OCP Datacenter NVMe SSD | 85/100 | Requirement ID 기반 표와 NVMe overlap 덕분에 활용 가능성이 높다. OCP 전용 requirement/conformance matrix와 table-field 추출이 필요하다. |
| PCIe | 82/100 | capability, register, bitfield, ECN, state machine, security extension 참조가 많아 현재 generic semantic layer만으로는 부족하다. PCIe adapter가 필요하다. |
| TCG Storage/Security | 80/100 | method, UID/object, authority/session/security table 의미 추출이 필요하다. 현재는 원문 검색과 요구사항 추출은 가능하지만 보안 도메인 의미 계층이 얕다. |
| 고객 Requirement Spec | 84/100 | normative sentence 추출은 유용하다. 다만 대외비 안전 모드, requirement traceability matrix, testability hint, 변경 diff가 있어야 실무 운영성이 높아진다. |

#### 우선 보강 방향

기술 스펙 RAG 운영 관점에서는 다음 항목이 점수 상승에 직접 연결된다. 자세한 backlog는 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`의 Q16-Q25에 반영한다.

- Q16. Domain-Specific Technical Spec Adapter Framework
- Q17. Requirement Traceability And Conformance Matrix
- Q18. Technical Table Semantic Sidecars
- Q19. Storage Spec RAG Evaluation Golden Set
- Q20. RAG Chunk Boundary Quality For Long Specs
- Q21. RAG Cross-Reference Resolution Expansion
- Q22. Confidential Corpus Safe Mode
- Q23. Incremental Corpus Ingest Diff
- Q24. Figure/Diagram Semantic Provenance
- Q25. Domain Adapter Coverage Expansion

#### 참고한 공개 근거

- [NVM Express Specifications](https://nvmexpress.org/specifications/)
- [PCI-SIG PCI Express Base](https://pcisig.com/specification-overview/pci-express-base)
- [OCP Datacenter NVMe SSD Specification](https://www.opencompute.org/documents/datacenter-nvme-ssd-specification-v2-7-final-pdf-1)
- [TCG Storage Specifications and Key Management](https://trustedcomputinggroup.org/resource/tcg-storage-specifications-and-key-management/)

#### 검증 기준

이 평가 항목은 문서/백로그 갱신 성격이며, 다음 검증으로 문서 계약과 formatting 문제를 확인한다.

- `git diff --check`
- `./.venv311/bin/python -m pytest tests/test_docs_examples.py`

### 2026-05-13

#### 총평

현재 프로젝트를 **RAG용 PDF to MD 변환툴**로 보면 **91/100점** 수준으로 평가한다.

기존 2026-05-11 평가의 85/100점 대비 **+6점** 상승했다. 상승 요인은 Markdown 자체보다 RAG ingest의 source of truth가 되는 JSONL sidecar 계층이 크게 보강된 점이다. `text_blocks_rag.jsonl`, semantic sidecar 3종, `retrieval_chunks_rag.jsonl`, `figures_rag.jsonl`, opt-in `domain_units_rag.jsonl`, batch `corpus_manifest.json`까지 생기면서 AI Agent/Copilot이 스펙 분석, 요구사항 추적, 테스트 스크립트 구현에 활용할 수 있는 provenance가 훨씬 안정적이 됐다.

다만 95점 이상으로 보지는 않는다. 실제 대규모 PDF corpus에서 RAG hit@k/MRR/citation coverage를 강제하는 golden set이 아직 초기 단계이고, chunk boundary 품질, cross-reference resolved coverage, incremental ingest diff, 도메인 adapter coverage는 다음 작업으로 남아 있다.

#### 세부 점수

| 항목 | 점수 | 2026-05-11 대비 | 평가 |
|---|---:|---:|---|
| 핵심 변환 완성도 | 17/18 | +1 | text/table/image/OCR/manifest/report/partial success 흐름은 안정적이다. RAG sidecar가 기본 산출물에 통합되어 재처리성이 좋아졌다. |
| 표 변환/RAG 대응 | 16/18 | +1 | `tables_rag.jsonl`, stable table/row id, semantic parameter, retrieval chunk 연계가 강해졌다. 실문서 복잡 표 calibration과 cross-ref 연계는 더 필요하다. |
| 텍스트 구조 보존 | 15/16 | +3 | font/geometry 기반 `heading/list/code/footnote/caption` 블록화와 `heading_path`가 RAG provenance에 직접 반영된다. 극단적 multi-column/불량 PDF는 아직 corpus 검증이 필요하다. |
| 이미지/OCR 신뢰도 | 12/14 | 0 | `figures_rag.jsonl`로 image/excluded image provenance가 좋아졌다. OCR과 diagram 의미 추출은 여전히 환경/문서 품질 의존성이 있다. |
| 성능/효율 | 10/12 | 0 | page cache, benchmark, release gate 기반은 있다. 대량 corpus incremental ingest diff와 chunk packing 최적화는 아직 남아 있다. |
| 테스트/결정성/CI | 12/12 | 0 | `127 passed`, golden corpus, GitHub Actions Python 3.11/3.14 통과. 환경별 이미지 hash 차이는 golden normalize로 방어했다. |
| 운영/릴리스 준비도 | 9/10 | +1 | schema export/check, packaging release gate, README/Windows/schema 문서가 갱신됐다. RAG evaluation gate의 release gate 승격은 아직 남았다. |

#### RAG 운영 관점 장점

- Markdown을 무리하게 “예쁘게” 바꾸지 않고, RAG ingest용 정본을 JSONL sidecar로 분리했다.
- `retrieval_chunks_rag.jsonl`이 text block, requirement, semantic unit, table row, domain unit provenance를 함께 제공한다.
- `requirements_rag.jsonl`은 명확한 normative keyword만 보수적으로 분류해 스펙 추적과 테스트 케이스 후보 추출에 유리하다.
- `corpus_manifest.json`이 batch output file map과 source hash를 기록해 multi-PDF corpus 운영의 기반을 만든다.
- `scripts/run_rag_eval.py`로 embedding 없이도 deterministic local retrieval smoke/eval을 시작할 수 있다.
- schema 문서와 machine-readable schema가 함께 갱신되어 외부 indexing pipeline이 참조하기 좋아졌다.

#### 남은 리스크

- 실제 RAG 품질을 대표하는 golden query set과 expected source id coverage가 아직 충분하지 않다.
- chunk boundary는 현재 보수적 deterministic packing 수준이며, 긴 section/짧은 requirement 혼합 문서에서 최적화 여지가 있다.
- `cross_refs_rag.jsonl`은 unresolved를 보존하지만, table/figure/section target id resolution coverage는 더 높일 수 있다.
- `--domain-adapter nvme`는 유용한 시작점이지만 command set/opcode/register/enum fixture coverage가 아직 제한적이다.
- figure/diagram sidecar는 provenance 중심이며, 도표 의미 해석이나 caption 없는 diagram 분석은 의도적으로 다루지 않는다.

#### 다음 개선 참조

현재 평가에서 확인된 주요 개선 과제는 이후 기술 스펙 RAG 운영 관점으로 재분류했으며, `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`의 Q16-Q25 항목으로 반영되어 있다.

#### 검증 기준

이 평가 시점의 확인 결과는 다음과 같다.

- `./.venv311/bin/python -m pytest`: `127 passed`
- `git diff --check`: 정상
- `./.venv311/bin/python -m pdf2md --help`: 정상
- `./.venv311/bin/python scripts/export_output_schema.py --check`: 정상
- `./.venv311/bin/python scripts/run_release_gates.py --output-dir /private/tmp/pdf2md-rag-q11-q15-final-gates --gates schema,packaging`: 정상
- 대표 RAG smoke: `--debug --rag-table-output jsonl --domain-adapter nvme`로 RAG sidecar 생성 확인
- GitHub Actions CI: Python 3.11, 3.14 통과

### 2026-05-11

#### 총평

현재 프로젝트는 **85/100점** 수준으로 평가한다.

기능 수와 테스트 상태만 보면 더 높게 볼 수도 있지만, 실제 PDF corpus 기준의 정량 품질 게이트, 성능 회귀 기준선, 출력 schema/패키징 릴리스 계약이 아직 완성되지 않았으므로 90점대 평가는 보류한다.

#### 세부 점수

| 항목 | 점수 | 평가 |
|---|---:|---|
| 핵심 변환 완성도 | 16/18 | text/table/image/OCR/manifest/report/partial success가 갖춰져 있고 기본 동작은 안정적이다. |
| 표 변환/RAG 대응 | 15/18 | HTML fallback 정책과 RAG sidecar가 좋다. 실문서 복잡 표 calibration은 더 필요하다. |
| 텍스트 구조 보존 | 12/16 | 보수적 heading/list/code/hyphenation은 있다. font/geometry 기반 판단은 아직 다음 단계다. |
| 이미지/OCR 신뢰도 | 12/14 | image dedupe, crop fallback, OCR lang 진단이 있다. crop 시각 검증과 OCR preflight는 미완이다. |
| 성능/효율 | 10/12 | page cache, stage duration, benchmark script는 있다. 성능 regression gate는 아직 없다. |
| 테스트/결정성/CI | 12/12 | `92 passed`, golden corpus, GitHub Actions Python 3.11/3.14까지 양호하다. |
| 운영/릴리스 준비도 | 8/10 | README/Windows guide는 좋다. schema 계약, wheel 패키징 smoke, release gate가 더 필요하다. |

#### 장점

- 기본 변환 정책이 보수적이다. 복잡 표를 억지로 GFM으로 만들지 않고 HTML fallback과 RAG sidecar를 분리했다.
- `manifest.json`, `report.json`, page-level diagnostics, debug artifacts가 있어 재처리와 분석이 가능하다.
- synthetic golden corpus와 CI가 있어 회귀 방어력이 올라갔다.
- `PdfDocumentContext`, page cache, `stage_durations_ms`, benchmark script가 있어 성능을 추적할 기반이 있다.
- 새 기능 대부분이 opt-in이라 기본 출력 호환성을 크게 흔들지 않는다.

#### 단점

- 실제 PDF corpus 품질을 threshold로 막는 게이트가 아직 없다.
- OCR은 runtime/language 환경 의존성이 커서 사전 점검 도구가 필요하다.
- figure crop fallback은 opt-in으로 안전하지만, blank crop이나 잘못된 영역 검증은 부족하다.
- multi-page table continuation은 기본 metadata가 있으나 오탐 방지용 calibration fixture가 더 필요하다.
- 출력 schema와 패키징 릴리스 계약이 아직 별도 문서/테스트로 고정되어 있지 않다.

#### 다음 개선 참조

현재 평가에서 확인된 주요 개선 과제는 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에 다음 항목으로 반영되어 있다.

- Q01. 실문서 Corpus 품질 게이트 고도화
- Q02. Font/Geometry 기반 텍스트 블록 구조화
- Q03. Figure Crop Fallback 시각 검증 및 보정
- Q04. Multi-page Table Continuation 보정
- Q05. OCR Runtime/Language 사전 점검
- Q06. Benchmark 성능 회귀 게이트
- Q07. Output Schema / 패키징 릴리스 계약

#### 검증 기준

이 평가 시점의 확인 결과는 다음과 같다.

- `./.venv311/bin/python -m pytest`: `92 passed`
- `./.venv311/bin/python -m pdf2md --help`: 정상
- GitHub Actions CI: Python 3.11, 3.14 통과
