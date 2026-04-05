from __future__ import annotations

import json
from pathlib import Path

from pdf2md.config import Config
from pdf2md.pipeline import EXIT_SUCCESS, run_conversion


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
