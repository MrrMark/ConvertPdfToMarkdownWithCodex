from __future__ import annotations

import json
from pathlib import Path

from pdf2md.config import Config
from pdf2md.pipeline import EXIT_SUCCESS, ConversionProgressEvent, run_conversion
from tests.fixtures.pdf_builder import build_multi_page_text_pdf


def test_pipeline_generates_outputs(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    config = Config(
        input_pdf=sample_pdf,
        output_dir=output_dir,
        keep_page_markers=True,
    )

    result = run_conversion(config)
    assert result.exit_code == EXIT_SUCCESS

    document_path = output_dir / "document.md"
    manifest_path = output_dir / "manifest.json"
    report_path = output_dir / "report.json"

    assert document_path.exists()
    assert manifest_path.exists()
    assert report_path.exists()

    golden = Path("tests/golden/document_with_markers.md").read_text(encoding="utf-8")
    assert document_path.read_text(encoding="utf-8") == golden

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert manifest["input_file"] == "sample.pdf"
    assert manifest["selected_pages"] == [1, 2]
    assert report["status"] == "success"


def test_pipeline_uses_custom_output_filenames(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "custom-out"
    config = Config(
        input_pdf=sample_pdf,
        output_dir=output_dir,
        markdown_filename="sample.md",
        manifest_filename="sample_manifest.json",
        report_filename="sample_report.json",
        assets_dirname="sample_assets",
    )

    result = run_conversion(config)
    assert result.exit_code == EXIT_SUCCESS
    assert (output_dir / "sample.md").exists()
    assert (output_dir / "sample_manifest.json").exists()
    assert (output_dir / "sample_report.json").exists()
    assert (output_dir / "sample_assets" / "images").exists()


def test_pipeline_writes_debug_artifacts(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "debug-out"
    config = Config(
        input_pdf=sample_pdf,
        output_dir=output_dir,
        pages="1",
        debug=True,
    )

    result = run_conversion(config)

    assert result.exit_code == EXIT_SUCCESS
    debug_dir = output_dir / "debug"
    assert (debug_dir / "page-0001-raw-lines.json").exists()
    assert (debug_dir / "page-0001-ordered-lines.json").exists()
    assert (debug_dir / "page-0001-normalized-lines.json").exists()
    assert (debug_dir / "page-0001-table-candidates.json").exists()
    assert (debug_dir / "page-0001-image-candidates.json").exists()
    assert (debug_dir / "table-quality-review-pack.json").exists()
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["options"]["debug"] is True


def test_pipeline_emits_observer_only_page_progress(tmp_path: Path) -> None:
    pdf_path = tmp_path / "multi.pdf"
    build_multi_page_text_pdf(pdf_path, page_count=3)
    events: list[ConversionProgressEvent] = []

    result = run_conversion(Config(input_pdf=pdf_path, output_dir=tmp_path / "out"), progress=events.append)

    assert result.exit_code == EXIT_SUCCESS
    assert [(event.status, event.current, event.total, event.page) for event in events] == [
        ("pages_selected", 0, 3, None),
        ("image_extraction_page_started", 0, 3, 1),
        ("image_extraction_page_finished", 1, 3, 1),
        ("image_extraction_page_started", 1, 3, 2),
        ("image_extraction_page_finished", 2, 3, 2),
        ("image_extraction_page_started", 2, 3, 3),
        ("image_extraction_page_finished", 3, 3, 3),
        ("page_started", 0, 3, 1),
        ("page_finished", 1, 3, 1),
        ("page_started", 1, 3, 2),
        ("page_finished", 2, 3, 2),
        ("page_started", 2, 3, 3),
        ("page_finished", 3, 3, 3),
    ]
    assert all(event.stage in {"page_selection", "image_extraction", "normalization"} for event in events)
    image_events = [event for event in events if event.stage == "image_extraction"]
    assert all(event.image_count == 0 for event in image_events)
    assert all(event.elapsed_ms is not None for event in image_events)
