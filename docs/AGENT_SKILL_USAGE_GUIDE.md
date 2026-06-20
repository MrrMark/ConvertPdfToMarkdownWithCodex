# pdf2md Agent Skill Usage Guide

이 문서는 Claude Code, Cline, Roo Code, Cursor, Continue 같은 AI coding agent에서 `pdf2md` Skill/Rule 패키지를 설치하고 사용하는 방법을 정리한다.

포팅 구조와 유지보수 원칙은 [AGENT_SKILL_PORTABILITY.md](AGENT_SKILL_PORTABILITY.md)를 따른다. 이 문서는 실제 설치, 업데이트, 사용, 문제 해결 절차만 다룬다.

## 1. Prerequisites

- 이 저장소의 source checkout
- Python 3.11+
- `pdf2md` editable install
- OCR을 사용할 경우 Tesseract runtime

기본 개발 환경:

```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

Windows PowerShell에서 Python 3.14 환경을 쓰는 경우:

```powershell
py -3.14 -m venv .venv314
.\.venv314\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

회사 보안 환경이나 Python 3.14 설치 제한이 있으면 Python 3.11 `.venv311`을 fallback으로 사용한다.

## 2. Canonical Source

canonical Skill source는 아래 경로다.

```text
agent-pack/skills/pdf2md-rag-ingest/
```

직접 수정은 이 canonical source에만 한다. `.claude/`, `.cline/`, `.roo/`, `.cursor/`, `.continue/`, `.agents/` 아래에 설치되는 파일은 생성물로 취급한다.

## 3. Supported Clients

| Client | Installed target | Type |
| --- | --- | --- |
| Cross-agent / Roo compatible | `.agents/skills/pdf2md-rag-ingest/` | Skill directory |
| Claude Code | `.claude/skills/pdf2md-rag-ingest/` | Skill directory |
| Cline | `.cline/skills/pdf2md-rag-ingest/` | Skill directory |
| Roo Code | `.roo/skills/pdf2md-rag-ingest/` | Skill directory |
| Cursor | `.cursor/rules/pdf2md-rag-ingest.mdc` | Project rule |
| Continue | `.continue/rules/pdf2md-rag-ingest.md` | Project rule |

## 4. Install

설치 전 dry-run으로 생성 대상 경로를 확인한다.

```bash
python3 scripts/install_agent_skill_pack.py --clients all --scope project --mode copy --dry-run
```

프로젝트 로컬에 모든 target을 설치한다.

```bash
python3 scripts/install_agent_skill_pack.py --clients all --scope project --mode copy
```

일부 client만 설치할 수도 있다.

```bash
python3 scripts/install_agent_skill_pack.py --clients claude,cline,roo --scope project --mode copy
python3 scripts/install_agent_skill_pack.py --clients cursor,continue --scope project --mode copy
```

공통 `.agents` target만 설치:

```bash
python3 scripts/install_agent_skill_pack.py --clients agents --scope project --mode copy
```

## 5. Windows Notes

Windows 사용자는 `copy` mode를 기본으로 사용한다. `symlink` mode는 Developer Mode, 권한, 보안 정책에 따라 실패할 수 있다.

PowerShell 예시:

```powershell
py -3.14 scripts\install_agent_skill_pack.py --clients all --scope project --mode copy --dry-run
py -3.14 scripts\install_agent_skill_pack.py --clients all --scope project --mode copy
```

Python 3.11 fallback:

```powershell
py -3.11 scripts\install_agent_skill_pack.py --clients all --scope project --mode copy
```

경로에 공백이 있으면 `--project-root`를 명시한다.

```powershell
py -3.14 scripts\install_agent_skill_pack.py --project-root "C:\Work\ConvertPdfToMarkdown" --clients all --scope project --mode copy
```

## 6. Update Existing Installs

canonical source를 수정한 뒤 기존 설치물을 갱신하려면 `--overwrite`를 사용한다.

```bash
python3 scripts/install_agent_skill_pack.py --clients all --scope project --mode copy --overwrite
```

변경 전 실제 덮어쓸 경로를 확인하려면:

```bash
python3 scripts/install_agent_skill_pack.py --clients all --scope project --mode copy --overwrite --dry-run
```

dry-run 출력은 각 client의 target과 source를 `target <- source` 형태로 보여준다. Cursor/Continue rule은 최신 sidecar 계약을 직접 복사하지 않고 canonical Skill과 `references/` 문서로 유도해야 한다.

## 7. Agent Usage

Agent에게 PDF 변환을 맡길 때는 원문 보존과 산출물 검증을 명시한다.

일반 변환 요청 예시:

```text
Use the pdf2md-rag-ingest skill. Convert input.pdf to output/input with source-preserving defaults, then report the artifact paths, status, warning codes, and validation result. Do not summarize or rewrite PDF text.
```

기술 스펙 RAG 요청 예시:

```text
Use the pdf2md-rag-ingest skill. Convert the NVMe Base or NVM Command Set spec PDF with technical_spec_rag and the nvme domain adapter, generate RAG sidecars, validate the output bundle, preserve adapter_metadata and cross_spec_compatibility, and summarize only counts, artifact paths, metadata coverage, and actionable warnings.
```

이미지 업로드가 불가능한 RAG 환경:

```text
Use the pdf2md-rag-ingest skill with the assetless technical RAG workflow. Use placeholder images plus figure text chunks, then validate the output bundle.
```

대형 technical spec의 text/table/domain ingest:

```text
Use the pdf2md-rag-ingest skill. Convert the NVMe Base PDF with technical_spec_rag,
domain_adapter=nvme, and image_mode=none. If using MCP, prefer page-window conversion and merge.
Report artifact paths, window status, warning codes, and validator summaries only.
```

민감정보/고객 문서:

```text
Use confidential-safe pdf2md settings. Do not paste raw PDF text, table contents, image contents, full Markdown, or customer paths into the response.
```

## 8. Runner Commands

Skill 내부 runner는 agent가 긴 CLI option을 안전하게 조립하는 데 사용한다.

Doctor:

```bash
python3 agent-pack/skills/pdf2md-rag-ingest/scripts/pdf2md_agent_runner.py doctor --ocr-lang kor+eng
```

일반 변환:

```bash
python3 agent-pack/skills/pdf2md-rag-ingest/scripts/pdf2md_agent_runner.py convert input.pdf \
  --workflow preserve \
  --output-dir output/input
```

기술 스펙 RAG:

```bash
python3 agent-pack/skills/pdf2md-rag-ingest/scripts/pdf2md_agent_runner.py convert spec.pdf \
  --workflow technical-rag \
  --domain-adapter nvme \
  --output-dir output/spec \
  --rag-table-output jsonl
```

NVMe Base와 NVM Command Set은 모두 같은 `--domain-adapter nvme` 계약을 사용한다. NVM Command Set 산출물은 CDW layout, command pointer, command scope, status taxonomy metadata를 추가로 포함할 수 있으며, Agent 응답에는 raw spec 전문, full Markdown body, table row content, image bytes, local input path를 붙이지 말고 sidecar count, command relationship metadata coverage, `adapter_metadata`/`cross_spec_compatibility` coverage, validator 결과만 요약한다.

`technical_spec_rag_visual` 산출물은 `page_layout_rag.jsonl`, `figure_ocr_evidence_rag.jsonl`, `figure_descriptions_rag.jsonl`, `figure_structures_rag.jsonl`까지 포함할 수 있다. Agent는 이 파일들의 생성 여부와 record count만 보고하고, figure OCR text, generated description, structure row 원문은 기본 응답에 붙이지 않는다.

이미지 업로드 불가 RAG:

```bash
python3 agent-pack/skills/pdf2md-rag-ingest/scripts/pdf2md_agent_runner.py convert spec.pdf \
  --workflow assetless-technical-rag \
  --domain-adapter nvme \
  --output-dir output/spec
```

대형 technical spec text-first ingest:

```bash
python3 -m pdf2md nvme-base.pdf -o output/nvme-base \
  --rag-profile technical_spec_rag \
  --domain-adapter nvme \
  --image-mode none
```

MCP client에서는 먼저 `pdf2md_plan_large_spec_conversion`으로 page-window/profile/image mode 권고를 확인한 뒤
`pdf2md_convert_pdf_windowed` 또는 `pdf2md_plan_page_windows` ->
`pdf2md_convert_page_window` -> `pdf2md_merge_window_outputs` 순서를 사용한다.
변환 후 일반 artifact 검증은 `pdf2md_validate_output`, SSD technical spec 계약 검증은
`pdf2md_validate_ssd_rag_contract`를 사용한다. visual sidecar를 생성한 경우
`pdf2md_validate_visual_sidecars`로 figure/source linkage와 generated content sidecar-only 계약을 추가 검증한다.

출력 검증:

```bash
python3 agent-pack/skills/pdf2md-rag-ingest/scripts/pdf2md_agent_runner.py validate --output-dir output/spec --target all
```

실행 전 command만 확인:

```bash
python3 agent-pack/skills/pdf2md-rag-ingest/scripts/pdf2md_agent_runner.py convert spec.pdf \
  --workflow technical-rag \
  --domain-adapter nvme \
  --output-dir output/spec \
  --dry-run
```

## 9. Validation

Skill/Rule 설치 상태를 확인한다.

```bash
python3 scripts/install_agent_skill_pack.py --clients all --scope project --mode copy --dry-run
python3 -m pytest tests/test_agent_skill_pack.py -q
```

변환 산출물 검증은 Skill runner 또는 validator script를 사용한다.

```bash
python3 agent-pack/skills/pdf2md-rag-ingest/scripts/pdf2md_agent_runner.py validate --output-dir output/spec --target all
python3 scripts/validate_index_contract.py --output-dir output/spec --target all --fail-on-error
python3 scripts/validate_provenance_integrity.py --output-dir output/spec --fail-on-error
python3 scripts/validate_artifact_integrity.py --output-dir output/spec --fail-on-error
python3 scripts/validate_ssd_rag_contract.py --output-dir output/spec --ssd-agent-domain HIL --ssd-agent-spec-type NVMe --domain-adapter nvme
```

## 10. Troubleshooting

- 설치 대상이 이미 있으면 `--overwrite`를 붙인다.
- Windows에서 symlink가 실패하면 `--mode copy`를 사용한다.
- Cursor/Continue는 현재 project scope만 지원한다.
- OCR warning이 있으면 `scripts/check_ocr_runtime.py --ocr-lang kor+eng`로 Tesseract와 language data를 확인한다.
- Agent 응답에 원문 PDF/Markdown 본문이 길게 포함되면 artifact path와 warning summary만 보고하도록 다시 지시한다.
- 고객/비공개 문서는 `--confidential-safe-mode` 또는 `--rag-profile confidential_rag`를 사용한다.
