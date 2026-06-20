# PDF to Markdown Converter

PDF 문서를 **원문 보존 중심 Markdown**으로 변환하는 CLI/라이브러리입니다.
보기 좋은 재구성보다 재처리 가능한 산출물과 추적 가능한 report를 우선합니다.

## Overview

- **텍스트는 그대로 유지**: 요약, 교정, 재서술 없이 원문 중심으로 추출합니다.
- **테이블은 안전하게 유지**: 단순 표는 GFM, 복잡 표는 HTML fallback을 사용합니다.
- **이미지는 참조가 기본**: 이미지 파일은 `assets/`에 저장하고 Markdown은 상대경로로 참조합니다.
- **부분 실패를 기록**: 페이지/표/이미지/OCR 경고는 `report.json`에 남기고 가능한 처리는 계속합니다.
- **기술 스펙 RAG 지원**: retrieval chunks, table/domain/figure/layout sidecar와 provenance validator를 제공합니다.
- **Domain adapter registry**: NVMe/PCIe/OCP/TCG/SPDM/Caliptra/customer/manual adapter metadata를 안정적으로 기록합니다.
- **AI Agent 연동 지원**: Claude Code, Cline, Roo Code, Cursor, Continue용 Skill/Rule 패키지와
  local stdio MCP 서버를 제공합니다.

## Quick Start

```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m pdf2md --help
```

가장 기본 변환:

```bash
python3 -m pdf2md input.pdf
```

출력 폴더 지정:

```bash
python3 -m pdf2md input.pdf -o output/input
```

폴더 배치 변환:

```bash
python3 -m pdf2md --input-dir ./pdfs --skip-existing
```

기본 출력은 단일 PDF 기준으로 `<pdf_stem>_output/`에 생성됩니다.

## Common Commands

| 목적 | 명령 |
| --- | --- |
| GUI 실행 | `python3 -m pdf2md.gui` |
| 비밀번호 PDF | `python3 -m pdf2md input.pdf -o output/ --password secret` |
| 일부 페이지만 변환 | `python3 -m pdf2md input.pdf -o output/ --pages 1-3,7` |
| OCR 강제 | `python3 -m pdf2md scan.pdf -o output/ --force-ocr --ocr-lang kor+eng` |
| OCR backend 선택 | `python3 -m pdf2md scan.pdf -o output/ --force-ocr --ocr-backend tesseract-cli` |
| 복잡 표 보존 우선 | `python3 -m pdf2md input.pdf -o output/ --table-mode html` |
| RAG sidecar 포함 | `python3 -m pdf2md spec.pdf -o output/spec --rag-profile rag_optimized` |
| 기술 스펙 RAG | `python3 -m pdf2md spec.pdf -o output/spec --rag-profile technical_spec_rag --domain-adapter nvme` |
| 기술 스펙 Visual RAG | `python3 -m pdf2md spec.pdf -o output/spec --rag-profile technical_spec_rag_visual --domain-adapter nvme` |
| 이미지 업로드 불가 Visual RAG | `python3 -m pdf2md spec.pdf -o output/spec --rag-profile technical_spec_rag_visual --domain-adapter nvme --image-mode placeholder` |
| 민감정보 보호 | `python3 -m pdf2md customer.pdf -o output/customer --rag-profile confidential_rag` |

## Outputs

단일 변환의 핵심 산출물:

```text
output/
  document.md
  assets/
    images/
  manifest.json
  report.json
```

RAG/기술 스펙 profile에서는 필요에 따라 아래 sidecar가 추가됩니다.

- Text/semantic: `text_blocks_rag.jsonl`, `semantic_units_rag.jsonl`, `retrieval_chunks_rag.jsonl`
- Requirements/cross-ref: `requirements_rag.jsonl`, `requirement_traceability_rag.jsonl`, `cross_refs_rag.jsonl`
- Tables/domain: `tables_rag.jsonl`, `rag_tables.md`, `technical_tables_rag.jsonl`, `domain_units_rag.jsonl`
- Layout/figure: `page_layout_rag.jsonl`, `figures_rag.jsonl`, `figure_ocr_evidence_rag.jsonl`, `figure_descriptions_rag.jsonl`, `figure_structures_rag.jsonl`

`domain_units_rag.jsonl`은 Q125 이후 `adapter_metadata`와 `cross_spec_compatibility`를 포함합니다.
Downstream ingest에서는 `source_sha256`, `source_dedupe_key`, `stable_source_id`, `stable_requirement_seed`를 함께 보존해야 합니다.

상세 schema와 report 필드는 [docs/OUTPUT_SCHEMA.md](docs/OUTPUT_SCHEMA.md)를 기준으로 합니다.

## Validation Helpers

운영 산출물 검증에는 아래 validator를 함께 사용합니다.

```bash
python scripts/validate_index_contract.py --output-dir output/spec --fail-on-error
python scripts/validate_provenance_integrity.py --output-dir output/spec --fail-on-error
python scripts/validate_artifact_integrity.py --output-dir output/spec --fail-on-error
python scripts/validate_ssd_rag_contract.py \
  --output-dir output/spec \
  --ssd-agent-domain HIL \
  --ssd-agent-spec-type NVMe \
  --domain-adapter nvme
```

최신 NVMe/OCP/SSD security 기술 스펙 smoke/evidence path는 다음 스크립트로 관리합니다.

```bash
python scripts/run_latest_nvme_base_benchmark.py --help
python scripts/run_latest_ocp_datacenter_nvme_ssd_benchmark.py --help
python scripts/run_latest_ssd_security_spec_benchmark.py --help
```

## Exit Codes

- `0`: 완전 성공
- `1`: 치명적 실패
- `2`: 부분 성공

`2`는 변환 실패만을 뜻하지 않습니다. actionable warning이나 품질 진단이 포함된 성공 실행일 수 있으므로
항상 `report.json`과 warning code를 함께 확인합니다.

## Documentation

| 주제 | 문서 |
| --- | --- |
| Windows 빠른 시작 | [docs/WINDOWS_INSTALL_RUN_QUICKSTART.md](docs/WINDOWS_INSTALL_RUN_QUICKSTART.md) |
| Windows 상세 운영 | [docs/WINDOWS_A_TO_Z_GUIDE.md](docs/WINDOWS_A_TO_Z_GUIDE.md) |
| macOS GUI 빠른 시작 | [docs/MACOS_GUI_QUICKSTART.md](docs/MACOS_GUI_QUICKSTART.md) |
| GUI 사용자 가이드 | [docs/GUI_USER_GUIDE.md](docs/GUI_USER_GUIDE.md) |
| 출력 schema | [docs/OUTPUT_SCHEMA.md](docs/OUTPUT_SCHEMA.md) |
| RAG indexer 연동 | [docs/RAG_INDEXER_INTEGRATION_RECIPES.md](docs/RAG_INDEXER_INTEGRATION_RECIPES.md) |
| Native migration 이력 | [docs/PDF2MD_NATIVE_MIGRATION_DEVELOPMENT_SPEC.md](docs/PDF2MD_NATIVE_MIGRATION_DEVELOPMENT_SPEC.md) |
| 품질 scorecard | [docs/QUALITY_SCORECARD.md](docs/QUALITY_SCORECARD.md) |
| Agent Skill 사용 | [docs/AGENT_SKILL_USAGE_GUIDE.md](docs/AGENT_SKILL_USAGE_GUIDE.md) |
| Agent Skill 포팅 구조 | [docs/AGENT_SKILL_PORTABILITY.md](docs/AGENT_SKILL_PORTABILITY.md) |
| MCP 설치/사용 | [docs/MCP_SERVER_INSTALL_USAGE_GUIDE.md](docs/MCP_SERVER_INSTALL_USAGE_GUIDE.md) |
| MCP 개발 명세 | [docs/MCP_SERVER_DEVELOPMENT_SPEC.md](docs/MCP_SERVER_DEVELOPMENT_SPEC.md) |
| 품질 개선 이력 | [docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md](docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md) |
| 다음 작업 계획 | [docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md](docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md) |

## AI Agent / Skill

공통 Skill source는 `agent-pack/skills/pdf2md-rag-ingest/`입니다.
도구별 설치 파일은 아래 명령으로 생성합니다.

```bash
python3 scripts/install_agent_skill_pack.py --clients all --scope project --mode copy
```

지원 target:

- `.agents/skills/pdf2md-rag-ingest/`
- `.claude/skills/pdf2md-rag-ingest/`
- `.cline/skills/pdf2md-rag-ingest/`
- `.roo/skills/pdf2md-rag-ingest/`
- `.cursor/rules/pdf2md-rag-ingest.mdc`
- `.continue/rules/pdf2md-rag-ingest.md`

설치, 업데이트, Windows 주의사항은
[docs/AGENT_SKILL_USAGE_GUIDE.md](docs/AGENT_SKILL_USAGE_GUIDE.md)를 따릅니다.

## MCP

local stdio MCP 서버는 `pdf2md/mcp_server.py`에 구현되어 있습니다.

```bash
python -m pip install -e ".[mcp]"
python -m pip install -e ".[dev,mcp]"
PDF2MD_MCP_ROOTS="/path/to/project:/path/to/pdfs:/path/to/output" \
  pdf2md-mcp --project-root /path/to/project
```

제공 tool:

- Discovery/plan: `pdf2md_doctor`, `pdf2md_list_profiles`, `pdf2md_plan_large_spec_conversion`, `pdf2md_plan_page_windows`
- Convert/merge: `pdf2md_convert_pdf`, `pdf2md_convert_page_window`, `pdf2md_merge_window_outputs`, `pdf2md_convert_pdf_windowed`
- Validate/inspect: `pdf2md_validate_output`, `pdf2md_validate_ssd_rag_contract`, `pdf2md_validate_visual_sidecars`, `pdf2md_inspect_report`

MCP 응답은 전체 Markdown 본문 대신 artifact URI, report summary, warning preview를 반환합니다.
대형 technical spec은 `pdf2md_plan_large_spec_conversion`으로 보수적 권고를 확인한 뒤 page-window tool을 사용합니다.
window output은 `windows/pages-0001-0100/` 같은 안정적인 하위 디렉터리로 나뉘며, merge report에는 sidecar inventory와 advisory memory guard가 포함됩니다.

## Development

```bash
python -m pytest
python -m ruff check .
git diff --check
```

릴리스 전 packaging contract:

```bash
python -m build
python scripts/inspect_wheel_contract.py --dist-dir dist --report-file dist/wheel_contract_report.json
```

`wheel_contract_report.json`은 wheel 내부 typed package marker, GUI/MCP module, packaged GUI help resource,
`pdf2md`/`pdf2md-gui`/`pdf2md-mcp` console script metadata를 검사합니다.

## Project Layout

```text
pdf2md/                 # CLI, GUI, MCP server, conversion pipeline
tests/                  # unit, integration, golden, docs contract tests
docs/                   # detailed user, operator, schema, and quality docs
agent-pack/             # canonical AI Agent Skill package
agent-adapters/         # Cursor/Continue rule adapters
scripts/                # validation, release gate, benchmark, install helpers
```

## Product Principles

1. 원문을 바꾸지 않습니다.
2. 애매한 표는 안전한 형식을 선택합니다.
3. 이미지는 기본적으로 참조로 남깁니다.
4. 실패는 숨기지 않고 report에 기록합니다.
5. 같은 입력과 같은 옵션은 같은 출력을 만들어야 합니다.
