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

### Q117. MCP NVMe Base Large Conversion Stability

개발 명세: `docs/PDF2MD_MCP_NVME_BASE_STABILITY_DEVELOPMENT_SPEC.md`

목표:

- `ssd-verification-agent`의 pdf2md MCP 운영에서 NVMe Base 784페이지급 전체 변환을 더 안정적으로 수행한다.
- image/figure 처리가 필요 없는 SpecAnalysisAgent ingest 경로에서는 true no-image mode로 병목을 제거한다.
- visual evidence가 필요한 경로에서는 page-level progress와 timeout fallback으로 어느 페이지에서 병목이 발생했는지 식별 가능하게 한다.
- 대형 PDF는 page-window conversion과 deterministic merge contract로 재시도/복구 가능한 workflow를 제공한다.

주요 작업:

- `image_mode=none` 또는 동등한 no-image option contract 추가
- image/figure extraction timeout, page progress, report counters 추가
- MCP page-window conversion and sidecar merge workflow 추가
- interrupted/partial conversion state journal과 JSON report 추가
- NVMe Base slice/window fixture와 merge validator 테스트 추가

검증:

```bash
.venv311/bin/python -m pytest tests/test_images.py tests/test_mcp_server.py -q
.venv311/bin/python -m pytest tests/test_rag_chunks.py tests/test_provenance_integrity_validator.py -q
.venv311/bin/python -m pytest tests/test_docs_examples.py tests/test_output_schema_contract.py -q
git diff --check
```

## 완료 명세 Archive

완료된 Q34-Q116 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.
