from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from pdf2md import mcp_server
from pdf2md.models import ConversionStatus
from tests.fixtures.pdf_builder import PageSpec, PositionedText, write_pdf


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _valid_retrieval_chunk(*, page: int, source_sha256: str) -> dict:
    text = f"Chunk page {page}"
    block_id = f"page-{page:04d}-block-0001"
    bbox = [72.0, 80.0, 180.0, 92.0]
    return {
        "chunk_id": "chunk-000001",
        "schema_version": "1.0",
        "chunk_index": 1,
        "chunk_type": "text_block",
        "text": text,
        "source_sha256": source_sha256,
        "source_refs": [{"source_type": "text_block", "source_id": block_id, "page": page, "bbox": bbox}],
        "page_range": [page, page],
        "bbox": bbox,
        "heading_path": [],
        "semantic_types": ["paragraph"],
        "normative_strength": None,
        "retrieval_priority": 50,
        "char_count": len(text),
        "token_estimate": 3,
        "section_path": "",
        "chunk_group_id": f"text-page-{page:04d}",
        "source_record_count": 1,
        "source_dedupe_key": block_id,
        "chunk_boundary_policy": "source_record",
        "chunk_boundary_reasons": ["text_block_boundary"],
    }


def _write_window_output(
    *,
    output_root: Path,
    window_id: str,
    page: int,
    source_sha256: str,
    input_pdf: Path,
) -> None:
    window_dir = output_root / "windows" / window_id
    window_dir.mkdir(parents=True)
    block_id = f"page-{page:04d}-block-0001"
    bbox = [72.0, 80.0, 180.0, 92.0]
    (window_dir / "document.md").write_text(f"Window page {page}\n", encoding="utf-8")
    _write_json(
        window_dir / "manifest.json",
        {
            "schema_version": "1.0",
            "input_file": str(input_pdf),
            "total_pages": 2,
            "selected_pages": [page],
            "options": {"image_mode": "none"},
            "images": [],
            "excluded_images": [],
            "tables": [],
            "ocr_pages": [],
            "warnings": [],
        },
    )
    _write_json(
        window_dir / "report.json",
        {
            "schema_version": "1.0",
            "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:00:01+00:00",
            "duration_ms": 1000,
            "status": "success",
            "engine_usage": {"pypdf": True, "pdfplumber": True, "ocr": False, "tables": False, "images": False},
            "failed_pages": [],
            "warnings": [],
            "page_results": [{"page": page, "status": "success"}],
            "summary": {
                "processed_pages": 1,
                "warning_count": 0,
                "failed_page_count": 0,
                "partial_success": False,
                "stage_durations_ms": {},
                "rag_text_block_record_count": 1,
                "retrieval_chunk_record_count": 1,
                "domain_unit_record_count": 1,
            },
        },
    )
    _write_jsonl(
        window_dir / "text_blocks_rag.jsonl",
        [
            {
                "block_id": block_id,
                "page": page,
                "block_index": 1,
                "text": f"Block page {page}",
                "bbox": bbox,
            }
        ],
    )
    _write_jsonl(
        window_dir / "retrieval_chunks_rag.jsonl",
        [_valid_retrieval_chunk(page=page, source_sha256=source_sha256)],
    )
    _write_jsonl(
        window_dir / "domain_units_rag.jsonl",
        [
            {
                "domain_unit_id": "domain-unit-000001",
                "unit_type": "synthetic",
                "page": page,
                "text": f"Domain page {page}",
                "bbox": bbox,
                "source_refs": [{"source_type": "text_block", "source_id": block_id, "page": page, "bbox": bbox}],
            }
        ],
    )


def test_pyproject_declares_mcp_extra_and_entry_point() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["optional-dependencies"]["mcp"] == ["mcp>=1.27,<2"]
    assert pyproject["project"]["scripts"]["pdf2md-mcp"] == "pdf2md.mcp_server:main"


def test_list_profiles_exposes_agent_selectable_modes() -> None:
    payload = mcp_server.list_profiles()

    assert payload["profiles"]["technical_spec_rag"]["rag_table_output"] == "both"
    visual = payload["profiles"]["technical_spec_rag_visual"]
    assert visual["rag_table_output"] == "both"
    assert visual["rag_figure_text_chunks"] is True
    assert visual["figure_region_ocr"] is True
    assert visual["rag_generated_figure_descriptions"] is True
    assert visual["figure_structure_extraction"] is True
    assert "nvme" in payload["domain_adapters"]
    assert "placeholder" in payload["image_modes"]
    assert "none" in payload["image_modes"]
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


def test_convert_pdf_accepts_no_image_mode_override(
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
        rag_profile="technical_spec_rag_visual",
        domain_adapter="nvme",
        image_mode="none",
        image_extraction_page_timeout_seconds=10,
        image_extraction_stage_timeout_seconds=20,
        figure_semantics_stage_timeout_seconds=30,
        roots=[tmp_path],
    )

    config = captured["config"]
    assert config.image_mode == "none"
    assert config.rag_profile == "technical_spec_rag_visual"
    assert config.rag_figure_text_chunks is True
    assert config.figure_region_ocr is True
    assert config.rag_generated_figure_descriptions is True
    assert config.figure_structure_extraction is True
    assert config.image_extraction_page_timeout_seconds == 10
    assert config.image_extraction_stage_timeout_seconds == 20
    assert config.figure_semantics_stage_timeout_seconds == 30
    assert result["options"]["image_mode"] == "none"
    assert result["options"]["image_extraction_page_timeout_seconds"] == 10
    assert result["options"]["image_extraction_stage_timeout_seconds"] == 20
    assert result["options"]["figure_semantics_stage_timeout_seconds"] == 30


def test_plan_page_windows_returns_deterministic_contract(tmp_path: Path) -> None:
    input_pdf = tmp_path / "spec.pdf"
    write_pdf(
        input_pdf,
        [
            PageSpec(texts=[PositionedText(f"Page {page}", 72, 760)])
            for page in range(1, 6)
        ],
    )
    output_dir = tmp_path / "out"

    result = mcp_server.plan_page_windows(
        input_pdf=str(input_pdf),
        output_dir=str(output_dir),
        pages="1-3,5",
        window_size=2,
        roots=[tmp_path],
    )

    source_sha256 = hashlib.sha256(input_pdf.read_bytes()).hexdigest()
    assert result["purpose"] == "page_window_plan"
    assert result["source_sha256"] == source_sha256
    assert result["total_pages"] == 5
    assert result["selected_pages"] == [1, 2, 3, 5]
    assert result["window_count"] == 2
    assert result["windows"] == [
        {
            "window_index": 1,
            "window_id": "pages-0001-0002",
            "page_range": "1-2",
            "start_page": 1,
            "end_page": 2,
            "selected_pages": [1, 2],
            "selected_page_count": 2,
            "source_sha256": source_sha256,
            "output_subdir": "windows/pages-0001-0002",
            "output_dir": str(output_dir / "windows" / "pages-0001-0002"),
        },
        {
            "window_index": 2,
            "window_id": "pages-0003-0005",
            "page_range": "3,5",
            "start_page": 3,
            "end_page": 5,
            "selected_pages": [3, 5],
            "selected_page_count": 2,
            "source_sha256": source_sha256,
            "output_subdir": "windows/pages-0003-0005",
            "output_dir": str(output_dir / "windows" / "pages-0003-0005"),
        },
    ]
    assert "Page 1" not in json.dumps(result, ensure_ascii=False, sort_keys=True)


def test_convert_page_window_uses_planned_page_range_and_output_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_pdf = tmp_path / "spec.pdf"
    write_pdf(
        input_pdf,
        [
            PageSpec(texts=[PositionedText(f"Page {page}", 72, 760)])
            for page in range(1, 6)
        ],
    )
    output_root = tmp_path / "out"
    captured = {}

    def fake_run_conversion(config):  # noqa: ANN001
        captured["config"] = config
        config.output_dir.mkdir(parents=True)
        markdown_path = config.output_dir / "document.md"
        manifest_path = config.output_dir / "manifest.json"
        report_path = config.output_dir / "report.json"
        markdown_path.write_text("# Window\n", encoding="utf-8")
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

    result = mcp_server.convert_page_window(
        input_pdf=str(input_pdf),
        output_dir=str(output_root),
        pages="1-3,5",
        window_size=2,
        window_id="pages-0003-0005",
        rag_profile="technical_spec_rag",
        domain_adapter="nvme",
        image_mode="none",
        roots=[tmp_path],
    )

    config = captured["config"]
    assert config.output_dir == output_root / "windows" / "pages-0003-0005"
    assert config.pages == "3,5"
    assert config.image_mode == "none"
    assert config.rag_profile == "technical_spec_rag"
    assert config.domain_adapter == "nvme"
    assert result["purpose"] == "page_window_conversion"
    assert result["window"]["page_range"] == "3,5"
    assert result["window"]["selected_pages"] == [3, 5]
    assert result["conversion"]["output_dir"] == str(output_root / "windows" / "pages-0003-0005")
    assert result["conversion"]["artifact_uris"]["document.md"].startswith("file://")


def test_merge_window_outputs_rewrites_collisions_and_validates(tmp_path: Path) -> None:
    input_pdf = tmp_path / "spec.pdf"
    write_pdf(
        input_pdf,
        [
            PageSpec(texts=[PositionedText(f"Page {page}", 72, 760)])
            for page in range(1, 3)
        ],
    )
    source_sha256 = hashlib.sha256(input_pdf.read_bytes()).hexdigest()
    output_root = tmp_path / "out"
    _write_window_output(
        output_root=output_root,
        window_id="pages-0001-0001",
        page=1,
        source_sha256=source_sha256,
        input_pdf=input_pdf,
    )
    _write_window_output(
        output_root=output_root,
        window_id="pages-0002-0002",
        page=2,
        source_sha256=source_sha256,
        input_pdf=input_pdf,
    )

    result = mcp_server.merge_window_outputs(
        input_pdf=str(input_pdf),
        output_dir=str(output_root),
        window_size=1,
        validate_windows=False,
        validate_merged=True,
        roots=[tmp_path],
        project_root=Path.cwd(),
    )

    assert result["status"] == "success"
    assert result["source_pdf_sha256"] == source_sha256
    assert result["merged_record_counts"]["retrieval_chunks_rag.jsonl"] == 2
    assert result["id_collision_count"] >= 1
    chunks = [
        json.loads(line)
        for line in (output_root / "retrieval_chunks_rag.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [chunk["chunk_id"] for chunk in chunks] == ["chunk-000001", "chunk-000002"]
    assert [chunk["chunk_index"] for chunk in chunks] == [1, 2]
    assert {chunk["source_sha256"] for chunk in chunks} == {source_sha256}
    assert chunks[0]["source_window_id"] == "pages-0001-0001"
    domain_units = [
        json.loads(line)
        for line in (output_root / "domain_units_rag.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [record["domain_unit_id"] for record in domain_units] == [
        "pages-0001-0001__domain-unit-000001",
        "pages-0002-0002__domain-unit-000001",
    ]
    manifest = json.loads((output_root / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output_root / "report.json").read_text(encoding="utf-8"))
    merge_report = json.loads((output_root / "page_window_merge_report.json").read_text(encoding="utf-8"))
    assert manifest["selected_pages"] == [1, 2]
    assert report["summary"]["retrieval_chunk_record_count"] == 2
    assert report["summary"]["domain_unit_record_count"] == 2
    assert merge_report["purpose"] == "page_window_merge"
    assert "Chunk page" not in json.dumps(merge_report, ensure_ascii=False, sort_keys=True)


def test_convert_pdf_windowed_orchestrates_windows_and_merge(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_pdf = tmp_path / "spec.pdf"
    write_pdf(
        input_pdf,
        [
            PageSpec(texts=[PositionedText(f"Page {page}", 72, 760)])
            for page in range(1, 4)
        ],
    )
    output_root = tmp_path / "out"
    converted: list[str] = []

    def fake_convert_page_window(**kwargs):  # noqa: ANN003
        converted.append(kwargs["window_id"])
        return {
            "conversion": {
                "status": "success",
                "exit_code": 0,
                "output_dir": str(output_root / "windows" / kwargs["window_id"]),
                "warning_count": 0,
                "report_summary": {"processed_pages": len(kwargs["window_id"])},
            }
        }

    def fake_merge_window_outputs(**kwargs):  # noqa: ANN003
        assert kwargs["output_dir"] == str(output_root)
        assert kwargs["window_size"] == 2
        return {"status": "success", "merge_report_uri": "file:///tmp/page_window_merge_report.json"}

    monkeypatch.setattr(mcp_server, "convert_page_window", fake_convert_page_window)
    monkeypatch.setattr(mcp_server, "merge_window_outputs", fake_merge_window_outputs)

    result = mcp_server.convert_pdf_windowed(
        input_pdf=str(input_pdf),
        output_dir=str(output_root),
        pages="1-3",
        window_size=2,
        roots=[tmp_path],
    )

    assert converted == ["pages-0001-0002", "pages-0003-0003"]
    assert result["purpose"] == "page_windowed_conversion"
    assert result["status"] == "success"
    assert result["window_count"] == 2
    assert result["merge"]["merge_report_uri"].endswith("page_window_merge_report.json")


def test_convert_pdf_requires_domain_adapter_for_technical_profile(tmp_path: Path) -> None:
    input_pdf = tmp_path / "spec.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n% synthetic placeholder\n")

    with pytest.raises(ValueError, match="technical spec RAG profiles require"):
        mcp_server.convert_pdf(
            input_pdf=str(input_pdf),
            output_dir=str(tmp_path / "out"),
            rag_profile="technical_spec_rag",
            roots=[tmp_path],
        )

    with pytest.raises(ValueError, match="technical spec RAG profiles require"):
        mcp_server.convert_pdf(
            input_pdf=str(input_pdf),
            output_dir=str(tmp_path / "out-visual"),
            rag_profile="technical_spec_rag_visual",
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
