# pdf2md MCP Server Install And Usage Guide

이 문서는 AI Agent 또는 MCP client에서 `pdf2md` local stdio MCP 서버를 설치하고 사용하는 방법을 정리한다.

현재 권장/검증된 설치 방식은 **source checkout + editable install**이다. MCP server가 `docs/` resource와 `scripts/` validator를 함께 사용하기 때문이다.

## 1. Prerequisites

- Python 3.11+
- source checkout of this repository
- PDF 변환 의존성 설치 가능 환경
- OCR을 사용할 경우 Tesseract runtime

Windows OCR 설정은 [WINDOWS_INSTALL_RUN_QUICKSTART.md](WINDOWS_INSTALL_RUN_QUICKSTART.md)의 `OCR 설정` 절을 따른다.

macOS OCR 예시:

```bash
brew install tesseract
```

## 2. Install

저장소 루트에서 가상환경을 만든다.

```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
python -m pip install -U pip
```

MCP extra를 포함해 editable install을 수행한다.

```bash
python -m pip install -e ".[mcp]"
```

기존 개발 의존성까지 같이 설치하려면 아래처럼 실행한다.

```bash
python -m pip install -e ".[dev,mcp]"
```

## 2.1 Python 3.14 Install

이 프로젝트의 최소 지원축은 Python 3.11이고, 최신 안정화 검증축은 Python 3.14다.
MCP 서버도 같은 정책을 따른다.

Python 3.14가 설치되어 있으면 `.venv314`를 별도로 만들어 3.11 환경과 분리한다.

macOS/Linux:

```bash
python3.14 -m venv .venv314
source .venv314/bin/activate
python -m pip install -U pip
python -m pip install -e ".[mcp]"
```

개발/테스트 의존성까지 포함:

```bash
python -m pip install -e ".[dev,mcp]"
```

Windows PowerShell:

```powershell
py -3.14 -m venv .venv314
.\.venv314\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[mcp]"
```

Python 3.14 실행기가 없고 새 Python 설치가 허용되는 Windows 환경에서는 기존 setup helper를 사용할 수 있다.

```powershell
.\scripts\setup_windows_env.ps1 -PythonVersion 3.14 -VenvDir .venv314 -RecreateVenv
.\.venv314\Scripts\python.exe -m pip install -e ".[mcp]"
```

회사 보안 환경처럼 Python 3.14 설치가 막혀 있으면 Python 3.11 `.venv311`을 fallback으로 사용한다.
MCP client 설정의 `command`만 `.venv314` 또는 `.venv311` 중 실제 사용하는 venv의 `pdf2md-mcp`로 맞추면 된다.

## 3. Smoke Check

CLI entry point가 보이는지 확인한다.

```bash
pdf2md-mcp --help
```

Python import와 helper 상태를 확인한다.

```bash
python -c "from pdf2md.mcp_server import doctor; print(doctor(skip_ocr_check=True)['status'])"
```

OCR runtime까지 점검하려면 MCP client에서 `pdf2md_doctor`를 호출하거나 아래 스크립트를 실행한다.

```bash
python scripts/check_ocr_runtime.py --ocr-lang kor+eng
```

## 4. Run Local stdio Server

macOS/Linux에서 가장 단순한 실행:

```bash
pdf2md-mcp --project-root /path/to/ConvertPdfToMarkdown
```

macOS/Linux에서 보안을 위해 MCP가 접근할 수 있는 root를 명시한다.

```bash
PDF2MD_MCP_ROOTS="/path/to/ConvertPdfToMarkdown:/path/to/pdfs:/path/to/output" \
  pdf2md-mcp --project-root /path/to/ConvertPdfToMarkdown
```

Windows PowerShell에서 직접 실행:

```powershell
.\.venv314\Scripts\pdf2md-mcp.exe --project-root C:\Work\ConvertPdfToMarkdown
```

Windows PowerShell에서 root를 명시해 실행:

```powershell
$env:PDF2MD_MCP_ROOTS = "C:\Work\ConvertPdfToMarkdown;C:\Work\pdfs;C:\Work\pdf2md-output"
.\.venv314\Scripts\pdf2md-mcp.exe --project-root C:\Work\ConvertPdfToMarkdown
```

Python 3.11 fallback 환경이면 `.venv314` 대신 `.venv311`을 사용한다.

```powershell
$env:PDF2MD_MCP_ROOTS = "C:\Work\ConvertPdfToMarkdown;C:\Work\pdfs;C:\Work\pdf2md-output"
.\.venv311\Scripts\pdf2md-mcp.exe --project-root C:\Work\ConvertPdfToMarkdown
```

정책:

- `PDF2MD_MCP_ROOTS`에 포함되지 않은 입력/출력 경로는 거부된다.
- `--project-root`는 static docs resource를 읽는 기준 경로다.
- MCP client가 어떤 cwd에서 시작해도 `docs/` resource와 `scripts/` validator를 찾을 수 있게 `--project-root`를 항상 지정한다.
- stdout은 MCP protocol 전용이므로 일반 실행 로그를 기대하지 않는다.

## 5. MCP Client Configuration

Client별 설정 파일 위치는 다르지만, server block은 아래 형태를 사용한다.

Python 3.11 venv:

```json
{
  "mcpServers": {
    "pdf2md": {
      "command": "/path/to/ConvertPdfToMarkdown/.venv311/bin/pdf2md-mcp",
      "args": ["--project-root", "/path/to/ConvertPdfToMarkdown"],
      "env": {
        "PDF2MD_MCP_ROOTS": "/path/to/ConvertPdfToMarkdown:/path/to/pdfs:/path/to/output"
      }
    }
  }
}
```

Python 3.14 venv:

```json
{
  "mcpServers": {
    "pdf2md": {
      "command": "/path/to/ConvertPdfToMarkdown/.venv314/bin/pdf2md-mcp",
      "args": ["--project-root", "/path/to/ConvertPdfToMarkdown"],
      "env": {
        "PDF2MD_MCP_ROOTS": "/path/to/ConvertPdfToMarkdown:/path/to/pdfs:/path/to/output"
      }
    }
  }
}
```

Windows PowerShell에서 만든 Python 3.14 venv를 client 설정에 넣는 경우:

```json
{
  "mcpServers": {
    "pdf2md": {
      "command": "C:\\path\\to\\ConvertPdfToMarkdown\\.venv314\\Scripts\\pdf2md-mcp.exe",
      "args": ["--project-root", "C:\\path\\to\\ConvertPdfToMarkdown"],
      "env": {
        "PDF2MD_MCP_ROOTS": "C:\\path\\to\\ConvertPdfToMarkdown;C:\\path\\to\\pdfs;C:\\path\\to\\output"
      }
    }
  }
}
```

경로에 공백이 있으면 client 설정 방식에 맞게 JSON string 그대로 지정한다.
macOS/Linux의 `PDF2MD_MCP_ROOTS` 구분자는 `:`이고, Windows의 구분자는 `;`다.
MCP tool argument JSON에서는 Windows 경로를 `C:/Work/pdfs/spec.pdf`처럼 forward slash로 써도 된다.
이 방식은 `C:\\Work\\pdfs\\spec.pdf`처럼 backslash를 escape해야 하는 실수를 줄인다.

## 6. Available Tools

### `pdf2md_doctor`

용도:

- 서버 상태, 허용 root, OCR backend/runtime 상태 확인

권장 첫 호출:

```json
{
  "skip_ocr_check": true
}
```

OCR 포함 점검:

```json
{
  "skip_ocr_check": false,
  "ocr_lang": "kor+eng"
}
```

### `pdf2md_list_profiles`

용도:

- 지원 RAG profile, domain adapter, image/table/output mode 확인

Agent는 변환 전에 이 tool로 option set을 확인하는 것이 좋다.

### `pdf2md_convert_pdf`

기본 원문 보존 변환:

```json
{
  "input_pdf": "/path/to/pdfs/input.pdf",
  "output_dir": "/path/to/output/input",
  "rag_profile": "preserve"
}
```

일반 RAG 최적화:

```json
{
  "input_pdf": "/path/to/pdfs/spec.pdf",
  "output_dir": "/path/to/output/spec",
  "rag_profile": "rag_optimized"
}
```

NVMe technical spec RAG:

```json
{
  "input_pdf": "/path/to/pdfs/nvme.pdf",
  "output_dir": "/path/to/output/nvme",
  "rag_profile": "technical_spec_rag",
  "domain_adapter": "nvme"
}
```

Windows path를 forward slash로 쓴 NVMe technical spec RAG:

```json
{
  "input_pdf": "C:/Work/pdfs/nvme.pdf",
  "output_dir": "C:/Work/pdf2md-output/nvme",
  "rag_profile": "technical_spec_rag",
  "domain_adapter": "nvme"
}
```

이미지 파일 업로드가 불가능한 RAG 환경:

```json
{
  "input_pdf": "/path/to/pdfs/spec.pdf",
  "output_dir": "/path/to/output/spec-assetless",
  "rag_profile": "technical_spec_rag",
  "domain_adapter": "nvme",
  "assetless_figure_text": true
}
```

manual domain adapter:

```json
{
  "input_pdf": "/path/to/pdfs/customer.pdf",
  "output_dir": "/path/to/output/customer",
  "rag_profile": "technical_spec_rag",
  "domain_adapter": "manual",
  "manual_domain_adapter_label": "Customer Requirements",
  "manual_domain_adapter_keywords": "Requirement ID, Customer Key"
}
```

응답에는 전체 Markdown 본문이 아니라 `artifact_uris`, `report_summary`, `warnings_preview`가 반환된다.

### `pdf2md_validate_output`

변환 결과 검증:

```json
{
  "output_dir": "/path/to/output/spec",
  "target": "all"
}
```

confidential-safe metadata 점검:

```json
{
  "output_dir": "/path/to/output/spec",
  "target": "all",
  "confidential_safe": true,
  "fail_on_warning": true
}
```

생성되는 report:

- `index_contract_report.json`
- `provenance_integrity_report.json`
- `artifact_integrity_report.json`

MCP 응답에는 전체 report payload 대신 `report_uris`, `report_summaries`, `findings_preview`만 포함된다.

### `pdf2md_inspect_report`

기존 산출물 상태 요약:

```json
{
  "output_dir": "/path/to/output/spec",
  "warning_limit": 20
}
```

## 7. Available Resources

- `pdf2md://docs/output-schema`
- `pdf2md://docs/rag-indexer-recipes`
- `pdf2md://docs/mcp-server-development-spec`

## 8. Available Prompts

- `convert_pdf_for_rag`
- `convert_technical_spec`
- `triage_conversion_warnings`

Prompts는 tool 호출 순서를 안내할 뿐, 변환 로직을 대체하지 않는다.

## 9. Recommended Agent Workflow

1. `pdf2md_doctor`로 서버 상태와 root를 확인한다.
2. `pdf2md_list_profiles`로 profile/adapter 선택지를 확인한다.
3. `pdf2md_convert_pdf`로 변환한다.
4. `pdf2md_validate_output`으로 RAG/index/provenance/artifact 계약을 검증한다.
5. `pdf2md_inspect_report`로 warning을 triage한다.
6. 필요할 때만 artifact URI의 파일을 열어 원문을 확인한다.

## 10. Troubleshooting

`The MCP SDK is not installed`:

```bash
python -m pip install -e ".[mcp]"
```

`outside configured MCP roots`:

- `PDF2MD_MCP_ROOTS`에 input PDF와 output directory의 상위 경로를 추가한다.

`technical_spec_rag requires a non-none domain_adapter`:

- `domain_adapter`를 `nvme`, `pcie`, `ocp`, `tcg`, `spdm`, `customer-requirements`, `manual` 중 하나로 지정한다.

OCR warning:

- OCR을 쓰지 않는 PDF라면 무시할 수 있다.
- OCR이 필요하면 Tesseract와 language data를 설치한다.

## 11. Current Scope

- 구현됨: local stdio MCP server
- 구현됨: single PDF conversion
- 구현됨: local output validation
- 구현됨: docs resources and prompts
- 후속: batch conversion MCP tool
- 후속: dynamic artifact resource templates
- 후속: Streamable HTTP server
