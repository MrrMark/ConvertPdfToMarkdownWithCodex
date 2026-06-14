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

### Q115. Visual Technical Spec RAG Profile and Metrics

개발 명세: `docs/VISUAL_TECHNICAL_SPEC_RAG_DEVELOPMENT_SPEC.md`

목표:

- NVMe Base/Command와 OCP spec의 image/figure/diagram evidence를 `ssd-verification-agent`가 안정적으로 사용할 수 있게 한다.
- 기존 `technical_spec_rag`는 backward compatible하게 유지하고, visual semantics를 켠 공식 preset 또는 동등한 option bundle을 제공한다.

주요 작업:

- `technical_spec_rag_visual` profile 후보 추가
- CLI/MCP/GUI/agent-pack workflow 노출
- visual sidecar and retrieval chunk schema/docs 갱신
- validator의 figure provenance/source ref 검증 강화
- latest NVMe/OCP benchmark visual metric 추가

검증:

```bash
.venv311/bin/python -m pytest tests/test_rag_figures.py tests/test_rag_chunks.py -q
.venv311/bin/python -m pytest tests/test_mcp_server.py tests/test_gui_presets.py -q
.venv311/bin/python -m pytest tests/test_output_schema_contract.py tests/test_docs_examples.py -q
.venv311/bin/python -m pytest tests/test_quality_gate_scripts.py -q
git diff --check
```

### Q116. SSD Verification Agent PDF2MD Sidecar Handoff

Handoff 명세: `docs/SSD_VERIFICATION_AGENT_PDF2MD_VISUAL_RAG_HANDOFF_SPEC.md`

목표:

- `ssd-verification-agent`가 pdf2md sidecar bundle을 direct ingest하고 local evidence를 source of truth로 사용할 수 있게 작업 범위를 분리한다.
- RAG server upload-only 경로와 local sidecar direct ingest 경로의 책임을 분명히 한다.

주요 작업:

- `ssd-verification-agent`에 추가할 API/MCP/direct ingest 작업 정의
- figure sidecar, generated figure description, figure structure evidence ingest 기준 정의
- `SpecAnalysisAgent` visual source quality/scoring 개선 기준 정의
- RAG server result와 local sidecar reconciliation 기준 정의

검증:

- 이 repo에서는 문서/계약 검증과 `git diff --check`를 수행한다.
- 실제 구현 검증은 `ssd-verification-agent` repo의 unit/replay/MCP/API test에서 수행한다.

## 완료 명세 Archive

완료된 Q34-Q114 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
