from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pdf2md.config import Config
from pdf2md.gui_runner import (
    GuiConversionOptions,
    GuiConversionRequest,
    build_batch_config,
    build_single_config,
    run_gui_conversion,
)
from pdf2md.models import DomainAdapterMode, ImageMode, RagTableOutputMode, TableMode
from pdf2md.pipeline import run_conversion
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
