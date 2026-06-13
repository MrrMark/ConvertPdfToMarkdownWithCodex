# pdf2md MCP Server Development Spec

이 문서는 `pdf2md`를 AI Agent가 Model Context Protocol(MCP)로 사용할 수 있게 하는 개발 명세다.

현재 구현 범위는 **local stdio MCP server**다. Streamable HTTP는 후속 확장으로만 설계한다.

설치와 MCP client 설정은 [MCP_SERVER_INSTALL_USAGE_GUIDE.md](MCP_SERVER_INSTALL_USAGE_GUIDE.md)를 따른다.

## Goals

- PDF 변환 로직을 재작성하지 않고 기존 `pdf2md` CLI/library 계약을 MCP tool로 노출한다.
- raw PDF text나 전체 Markdown body를 tool result에 직접 붙이지 않고, 생성 artifact URI와 요약만 반환한다.
- RAG sidecar, manifest, report, validator를 agent가 안정적으로 찾을 수 있게 한다.
- 로컬 파일 접근은 명시된 root 내부로 제한한다.

## Non-goals

- 외부 RAG/indexing service 호출
- 외부 LLM/VLM 호출
- remote HTTP MCP 배포
- PDF/Markdown 원문 전체를 기본 응답에 포함
- Streamable HTTP 구현

## Local stdio Server

설치:

```bash
python -m pip install -e ".[mcp]"
```

실행:

```bash
pdf2md-mcp
```

특정 작업 루트만 허용:

```bash
PDF2MD_MCP_ROOTS="/path/to/project:/path/to/pdfs:/path/to/output" pdf2md-mcp --project-root /path/to/project
```

`PDF2MD_MCP_ROOTS`를 지정하지 않으면 서버 실행 시점의 현재 작업 디렉터리만 허용한다.

## Tools

### `pdf2md_doctor`

목적:

- pdf2md import 가능 여부, MCP extra 안내, 허용 root, OCR runtime 상태를 확인한다.

주요 입력:

- `skip_ocr_check: bool`
- `ocr_lang: str`

출력:

- `status`
- `mcp_sdk_available`
- `roots`
- `ocr_backends`
- optional `ocr_check`

### `pdf2md_list_profiles`

목적:

- MCP client가 지원 profile과 adapter option을 자동 발견하게 한다.

출력:

- `profiles`
- `domain_adapters`
- `image_modes`
- `table_modes`
- `rag_table_outputs`
- `output_profiles`
- `rag_sidecar_scopes`

### `pdf2md_convert_pdf`

목적:

- 단일 PDF를 기존 `pdf2md.pipeline.run_conversion` 경로로 변환한다.

주요 입력:

- `input_pdf`
- `output_dir`
- `rag_profile`
- `domain_adapter`
- `manual_domain_adapter_label`
- `manual_domain_adapter_keywords`
- `pages`
- `password`
- `image_mode`
- `table_mode`
- `rag_table_output`
- `output_profile`
- `rag_sidecar_scope`
- `force_ocr`
- `ocr_lang`
- `ocr_backend`
- `page_workers`
- `assetless_figure_text`
- `skip_existing`

정책:

- `technical_spec_rag`는 기본적으로 `domain_adapter`를 요구한다.
- `assetless_figure_text=true`는 `image_mode=placeholder`와 `rag_figure_text_chunks=true`를 적용한다.
- 응답에는 `password` 값을 포함하지 않고 `password_supplied` boolean만 포함한다.
- 응답에는 `manual_domain_adapter_keywords` 값을 포함하지 않고 supplied boolean만 포함한다.
- 응답에는 full Markdown body를 포함하지 않는다.

출력:

- `status`
- `exit_code`
- `output_dir`
- `artifact_uris`
- `markdown_uri`
- `manifest_uri`
- `report_uri`
- `warning_count`
- `warnings_preview`
- `report_summary`

### `pdf2md_validate_output`

목적:

- 변환된 output directory에 대해 local-only validator 3종을 실행한다.

실행 validator:

- `validate_index_contract.py`
- `validate_provenance_integrity.py`
- `validate_artifact_integrity.py`

출력 파일:

- `index_contract_report.json`
- `provenance_integrity_report.json`
- `artifact_integrity_report.json`

응답 정책:

- 전체 report payload를 MCP 응답에 직접 싣지 않는다.
- `report_uris`, `report_summaries`, 제한된 `findings_preview`만 반환한다.

### `pdf2md_inspect_report`

목적:

- 기존 output directory의 `report.json`, `manifest.json`을 요약한다.

정책:

- raw Markdown body를 읽어 응답하지 않는다.
- warning preview는 제한된 개수만 반환한다.

## Resources

현재 static documentation resource만 노출한다.

- `pdf2md://docs/output-schema`
- `pdf2md://docs/rag-indexer-recipes`
- `pdf2md://docs/mcp-server-development-spec`

Artifact 본문은 tool result의 `file://` URI로 노출한다. 동적 artifact resource template은 client별 URI template 호환성 확인 후 추가한다.

## Prompts

- `convert_pdf_for_rag`
- `convert_technical_spec`
- `triage_conversion_warnings`

프롬프트는 tool 사용 순서를 안내할 뿐, 변환 로직을 대체하지 않는다.

## Security

- MCP tool은 입력/출력 경로가 configured root 밖이면 실패한다.
- stdout은 MCP protocol 전용으로 유지해야 하며 일반 로그는 stderr/logging으로 보내야 한다.
- tool result는 원문 전문을 기본 반환하지 않는다.
- `confidential_rag` 또는 confidential validation은 path/filename/source hash 노출 점검용이며 원문 text 익명화 기능이 아니다.
- 외부 network, embedding, LLM 호출은 하지 않는다.

## Streamable HTTP Follow-up Plan

Streamable HTTP는 아래 조건을 만족할 때 별도 작업으로 추가한다.

1. `stdio` 서버가 Codex, Claude Code, Cline/Roo/Continue 계열에서 호환 검증된다.
2. local-only path root 정책과 artifact URI 정책이 실제 agent workflow에서 충분히 안정화된다.
3. HTTP용 보안 요구사항을 별도 구현한다.

후속 HTTP 명세:

- localhost bind가 기본이다. `0.0.0.0` bind는 금지하거나 명시 opt-in으로 둔다.
- Origin header 검증을 구현한다.
- remote 배포 시 OAuth/resource indicator/audience validation 설계를 별도 문서화한다.
- large conversion은 HTTP request 장기 점유 대신 job id + poll/status tool로 분리한다.
- progress notification과 cancellation은 stdio 안정화 후 추가한다.

초기 HTTP 후보 command:

```bash
pdf2md-mcp-http --host 127.0.0.1 --port 8765 --root /path/to/project
```

이 command는 현재 구현하지 않는다.

## Validation

로컬 변경 검증:

```bash
python -m pytest tests/test_mcp_server.py
python -m pytest
python -m ruff check .
git diff --check
```
