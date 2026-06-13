from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from pdf2md import mcp_server
from pdf2md.models import ConversionStatus


def test_pyproject_declares_mcp_extra_and_entry_point() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["optional-dependencies"]["mcp"] == ["mcp>=1.27,<2"]
    assert pyproject["project"]["scripts"]["pdf2md-mcp"] == "pdf2md.mcp_server:main"


def test_list_profiles_exposes_agent_selectable_modes() -> None:
    payload = mcp_server.list_profiles()

    assert payload["profiles"]["technical_spec_rag"]["rag_table_output"] == "both"
    assert "nvme" in payload["domain_adapters"]
    assert "placeholder" in payload["image_modes"]
    assert "minimal" in payload["rag_sidecar_scopes"]


def test_path_guard_rejects_paths_outside_configured_roots(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    inside = root / "input.pdf"
    outside = tmp_path / "outside.pdf"

    assert mcp_server.ensure_within_roots(inside, [root], label="input_pdf") == inside.resolve()
    with pytest.raises(ValueError, match="outside configured MCP roots"):
        mcp_server.ensure_within_roots(outside, [root], label="input_pdf")


def test_convert_pdf_builds_assetless_technical_config_and_hides_password(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_pdf = tmp_path / "spec.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n% synthetic placeholder\n")
    output_dir = tmp_path / "out"
    captured = {}

    def fake_run_conversion(config):  # noqa: ANN001
        captured["config"] = config
        output_dir.mkdir()
        markdown_path = output_dir / "document.md"
        manifest_path = output_dir / "manifest.json"
        report_path = output_dir / "report.json"
        markdown_path.write_text("# Spec\n", encoding="utf-8")
        manifest_path.write_text("{}", encoding="utf-8")
        report_path.write_text("{}", encoding="utf-8")
        return SimpleNamespace(
            exit_code=0,
            markdown_path=markdown_path,
            manifest_path=manifest_path,
            report_path=report_path,
            warnings=[],
            status=ConversionStatus.SUCCESS,
            report=None,
        )

    monkeypatch.setattr(mcp_server, "run_conversion", fake_run_conversion)

    result = mcp_server.convert_pdf(
        input_pdf=str(input_pdf),
        output_dir=str(output_dir),
        rag_profile="technical_spec_rag",
        domain_adapter="manual",
        manual_domain_adapter_label="Customer A",
        manual_domain_adapter_keywords="Requirement ID, Customer Key",
        assetless_figure_text=True,
        password="secret",
        roots=[tmp_path],
    )

    config = captured["config"]
    assert config.rag_profile == "technical_spec_rag"
    assert config.domain_adapter == "manual"
    assert config.manual_domain_adapter_label == "Customer A"
    assert config.manual_domain_adapter_keywords == "Requirement ID, Customer Key"
    assert config.image_mode == "placeholder"
    assert config.rag_figure_text_chunks is True
    assert result["options"]["password_supplied"] is True
    assert result["options"]["manual_domain_adapter_keywords_supplied"] is True
    assert "secret" not in json.dumps(result, ensure_ascii=False, sort_keys=True)
    assert result["artifact_uris"]["document.md"].startswith("file://")


def test_convert_pdf_requires_domain_adapter_for_technical_profile(tmp_path: Path) -> None:
    input_pdf = tmp_path / "spec.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n% synthetic placeholder\n")

    with pytest.raises(ValueError, match="technical_spec_rag requires"):
        mcp_server.convert_pdf(
            input_pdf=str(input_pdf),
            output_dir=str(tmp_path / "out"),
            rag_profile="technical_spec_rag",
            roots=[tmp_path],
        )


def test_validate_output_writes_local_reports_for_missing_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    result = mcp_server.validate_output(output_dir=str(output_dir), roots=[tmp_path])

    assert result["status"] == "failed"
    assert (output_dir / "index_contract_report.json").is_file()
    assert (output_dir / "provenance_integrity_report.json").is_file()
    assert (output_dir / "artifact_integrity_report.json").is_file()
    assert "reports" not in result
    assert "report_summaries" in result
    assert "findings_preview" in result


def test_validate_output_uses_project_root_when_cwd_is_elsewhere(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = Path.cwd().resolve()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("scripts", None)
    pruned_path = [
        item
        for item in sys.path
        if item and Path(item).expanduser().resolve() != repo_root
    ]
    monkeypatch.setattr(sys, "path", pruned_path)

    try:
        result = mcp_server.validate_output(output_dir=str(output_dir), roots=[tmp_path], project_root=repo_root)

        assert result["status"] == "failed"
        assert str(repo_root) in sys.path
        assert (output_dir / "index_contract_report.json").is_file()
    finally:
        for module_name in list(sys.modules):
            if module_name == "scripts" or module_name.startswith("scripts."):
                sys.modules.pop(module_name, None)


def test_inspect_report_returns_summary_without_markdown_body(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (output_dir / "document.md").write_text("raw body should not be returned", encoding="utf-8")
    (output_dir / "report.json").write_text(
        json.dumps(
            {
                "status": "partial_success",
                "summary": {"warning_count": 1},
                "warnings": [{"code": "LOW_CONFIDENCE", "message": "Check page", "page": 1}],
            }
        ),
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_text(json.dumps({"options": {"rag_profile": "preserve"}}), encoding="utf-8")

    result = mcp_server.inspect_report(output_dir=str(output_dir), roots=[tmp_path])

    assert result["status"] == "partial_success"
    assert result["summary"] == {"warning_count": 1}
    assert result["warnings_preview"][0]["code"] == "LOW_CONFIDENCE"
    assert "raw body should not be returned" not in json.dumps(result, ensure_ascii=False, sort_keys=True)


def test_mcp_development_spec_documents_stdio_and_http_follow_up() -> None:
    text = Path("docs/MCP_SERVER_DEVELOPMENT_SPEC.md").read_text(encoding="utf-8")

    assert "local stdio MCP server" in text
    assert "PDF2MD_MCP_ROOTS" in text
    assert 'PDF2MD_MCP_ROOTS="/path/to/project:/path/to/pdfs:/path/to/output"' in text
    assert "MCP_SERVER_INSTALL_USAGE_GUIDE.md" in text
    assert "Streamable HTTP Follow-up Plan" in text
    assert "pdf2md-mcp-http" in text


def test_mcp_install_usage_guide_documents_safe_client_setup() -> None:
    text = Path("docs/MCP_SERVER_INSTALL_USAGE_GUIDE.md").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert 'python -m pip install -e ".[mcp]"' in text
    assert "python3.14 -m venv .venv314" in text
    assert "py -3.14 -m venv .venv314" in text
    assert ".venv314\\\\Scripts\\\\pdf2md-mcp.exe" in text
    assert "Python 3.11 `.venv311`을 fallback" in text
    assert "$env:PDF2MD_MCP_ROOTS" in text
    assert "MCP client가 어떤 cwd에서 시작해도" in text
    assert "WINDOWS_INSTALL_RUN_QUICKSTART.md" in text
    assert "C:/Work/pdfs/nvme.pdf" in text
    assert "forward slash" in text
    assert "PDF2MD_MCP_ROOTS" in text
    assert "mcpServers" in text
    assert "pdf2md_validate_output" in text
    assert "report_summaries" in text
    assert "manual_domain_adapter_keywords" in text
    assert "Streamable HTTP server" in text
    assert "docs/MCP_SERVER_INSTALL_USAGE_GUIDE.md" in readme
