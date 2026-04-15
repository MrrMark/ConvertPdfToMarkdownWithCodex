from __future__ import annotations

import json
from pathlib import Path

from pdf2md.config import default_output_dir_for_input
from pdf2md.utils.io import validate_output_bundle


def test_default_output_dir_for_input_uses_pdf_stem_suffix(tmp_path: Path) -> None:
    input_pdf = tmp_path / "demo.pdf"
    assert default_output_dir_for_input(input_pdf) == tmp_path / "demo_output"


def test_validate_output_bundle_accepts_minimum_valid_outputs(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (output_dir / "document.md").write_text("# ok\n", encoding="utf-8")
    (output_dir / "manifest.json").write_text(
        json.dumps({"schema_version": "1.0"}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.json").write_text(
        json.dumps({"schema_version": "1.0"}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    assert validate_output_bundle(output_dir) == []


def test_validate_output_bundle_reports_missing_required_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "out-missing"
    output_dir.mkdir()

    errors = validate_output_bundle(output_dir)

    assert "Missing required output: document.md" in errors
    assert "Missing required output: manifest.json" in errors
    assert "Missing required output: report.json" in errors
