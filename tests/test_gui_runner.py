from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from pdf2md.config import Config
from pdf2md.gui_runner import (
    GuiDiagnosticError,
    GuiConversionOptions,
    GuiConversionRequest,
    build_batch_config,
    build_single_config,
    check_gui_runtime,
    format_gui_summary,
    run_gui_conversion,
    validate_gui_request,
)
from pdf2md.models import (
    ConversionStatus,
    DomainAdapterMode,
    ImageMode,
    RagTableOutputMode,
    TableMode,
    WarningEntry,
)
from pdf2md.pipeline import ConversionResult, run_conversion
from helpers.normalize_outputs import normalize_manifest, normalize_report


def test_gui_module_help_does_not_launch_window() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "pdf2md.gui", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "minimal desktop GUI wrapper" in completed.stdout


def test_gui_request_builds_single_config_from_cli_options(sample_pdf: Path, tmp_path: Path) -> None:
    request = GuiConversionRequest(
        input_mode="file",
        input_path=sample_pdf,
        output_dir=tmp_path / "gui-out",
        options=GuiConversionOptions(
            pages="1",
            image_mode=ImageMode.PLACEHOLDER.value,
            table_mode=TableMode.HTML.value,
            rag_table_output=RagTableOutputMode.BOTH.value,
            domain_adapter=DomainAdapterMode.NVME.value,
            confidential_safe_mode=True,
            force_ocr=True,
            ocr_lang="kor+eng",
            keep_page_markers=True,
            remove_header_footer=True,
            dedupe_images=True,
            repair_hyphenation=True,
            figure_crop_fallback=True,
        ),
    )

    config = build_single_config(request)

    assert config.input_pdf == sample_pdf
    assert config.output_dir == tmp_path / "gui-out"
    assert config.pages == "1"
    assert config.image_mode == ImageMode.PLACEHOLDER.value
    assert config.table_mode == TableMode.HTML.value
    assert config.rag_table_output == RagTableOutputMode.BOTH.value
    assert config.domain_adapter == DomainAdapterMode.NVME.value
    assert config.confidential_safe_mode is True
    assert config.force_ocr is True
    assert config.ocr_lang == "kor+eng"
    assert config.keep_page_markers is True
    assert config.remove_header_footer is True
    assert config.dedupe_images is True
    assert config.repair_hyphenation is True
    assert config.figure_crop_fallback is True


def test_gui_runtime_diagnostics_detects_missing_tkinter() -> None:
    def fake_import(name: str) -> object:
        if name == "tkinter":
            raise ModuleNotFoundError("No module named 'tkinter'")
        return object()

    report = check_gui_runtime(
        python_version=(3, 11, 0),
        import_module=fake_import,
        entry_point_names=(),
    )

    assert report.has_errors is True
    assert [diagnostic.code for diagnostic in report.errors] == ["tkinter_unavailable"]
    assert "Tkinter is not available" in report.user_message()


def test_gui_runtime_diagnostics_flags_unsupported_python() -> None:
    report = check_gui_runtime(
        python_version=(3, 10, 9),
        import_module=lambda name: object(),
        entry_point_names=(),
    )

    assert report.has_errors is True
    assert report.errors[0].code == "python_version_unsupported"
    assert "Python 3.11 or newer" in report.user_message()


def test_gui_request_diagnostics_reject_output_file(sample_pdf: Path, tmp_path: Path) -> None:
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("already a file", encoding="utf-8")
    request = GuiConversionRequest(
        input_mode="file",
        input_path=sample_pdf,
        output_dir=output_file,
    )

    report = validate_gui_request(request)

    assert report.has_errors is True
    assert [diagnostic.code for diagnostic in report.errors] == ["output_not_directory"]
    with pytest.raises(GuiDiagnosticError) as exc_info:
        run_gui_conversion(request)
    assert "Output path exists but is not a directory" in str(exc_info.value)


def test_gui_single_conversion_uses_same_core_output_as_run_conversion(sample_pdf: Path, tmp_path: Path) -> None:
    options = GuiConversionOptions(pages="1", keep_page_markers=True)
    gui_output = tmp_path / "gui-output"
    direct_output = tmp_path / "direct-output"

    summary = run_gui_conversion(
        GuiConversionRequest(
            input_mode="file",
            input_path=sample_pdf,
            output_dir=gui_output,
            options=options,
        )
    )
    direct_result = run_conversion(
        Config(
            input_pdf=sample_pdf,
            output_dir=direct_output,
            pages="1",
            keep_page_markers=True,
        )
    )

    assert summary.exit_code == direct_result.exit_code == 0
    assert summary.success_count == 1
    assert summary.documents[0].markdown_path == gui_output / "document.md"
    assert summary.documents[0].manifest_path == gui_output / "manifest.json"
    assert summary.documents[0].report_path == gui_output / "report.json"
    assert summary.documents[0].assets_dir == gui_output / "assets"
    assert (gui_output / "document.md").read_text(encoding="utf-8") == (
        direct_output / "document.md"
    ).read_text(encoding="utf-8")
    assert normalize_manifest(json.loads((gui_output / "manifest.json").read_text(encoding="utf-8"))) == (
        normalize_manifest(json.loads((direct_output / "manifest.json").read_text(encoding="utf-8")))
    )
    assert normalize_report(json.loads((gui_output / "report.json").read_text(encoding="utf-8"))) == (
        normalize_report(json.loads((direct_output / "report.json").read_text(encoding="utf-8")))
    )


def test_gui_batch_conversion_uses_cli_batch_names_and_skip_existing(sample_pdf: Path, tmp_path: Path) -> None:
    input_dir = tmp_path / "pdfs"
    input_dir.mkdir()
    pdf_path = input_dir / "alpha.pdf"
    pdf_path.write_bytes(sample_pdf.read_bytes())
    output_root = tmp_path / "batch-output"
    request = GuiConversionRequest(
        input_mode="folder",
        input_path=input_dir,
        output_dir=output_root,
        options=GuiConversionOptions(pages="1"),
    )

    config = build_batch_config(request, pdf_path, output_root)
    assert config.output_dir == output_root / "alpha"
    assert config.markdown_filename == "alpha.md"
    assert config.manifest_filename == "alpha_manifest.json"
    assert config.report_filename == "alpha_report.json"
    first = run_gui_conversion(request)
    second = run_gui_conversion(
        GuiConversionRequest(
            input_mode="folder",
            input_path=input_dir,
            output_dir=output_root,
            options=GuiConversionOptions(pages="1", skip_existing=True),
        )
    )

    assert first.success_count == 1
    assert (output_root / "alpha" / "alpha.md").exists()
    assert (output_root / "alpha" / "alpha_manifest.json").exists()
    assert (output_root / "alpha" / "alpha_report.json").exists()
    assert second.skipped_count == 1
    assert second.documents[0].status == "skipped"
    assert second.documents[0].markdown_path == output_root / "alpha" / "alpha.md"
    assert second.documents[0].manifest_path == output_root / "alpha" / "alpha_manifest.json"
    assert second.documents[0].report_path == output_root / "alpha" / "alpha_report.json"


def test_gui_summary_uses_structured_warning_counts(monkeypatch: pytest.MonkeyPatch, sample_pdf: Path, tmp_path: Path) -> None:
    def fake_run_conversion(config) -> ConversionResult:  # noqa: ANN001
        return ConversionResult(
            exit_code=2,
            markdown_path=config.output_dir / config.markdown_filename,
            manifest_path=config.output_dir / config.manifest_filename,
            report_path=config.output_dir / config.report_filename,
            warnings=[
                WarningEntry(code="TABLE_FALLBACK", message="table fallback", page=2),
                WarningEntry(code="OCR_LOW_CONFIDENCE", message="low confidence", page=1),
                WarningEntry(code="TABLE_FALLBACK", message="table fallback duplicate", page=3),
            ],
            status=ConversionStatus.PARTIAL_SUCCESS,
        )

    monkeypatch.setattr("pdf2md.gui_runner.run_conversion", fake_run_conversion)
    output_dir = tmp_path / "partial-output"
    summary = run_gui_conversion(
        GuiConversionRequest(
            input_mode="file",
            input_path=sample_pdf,
            output_dir=output_dir,
        )
    )
    document = summary.documents[0]

    assert summary.partial_success_count == 1
    assert document.warning_count == 3
    assert document.warning_codes == ("OCR_LOW_CONFIDENCE", "TABLE_FALLBACK")
    text = format_gui_summary(summary)
    assert "warnings=3 (OCR_LOW_CONFIDENCE, TABLE_FALLBACK)" in text
    assert "table fallback duplicate" not in text
