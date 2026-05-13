from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from pdf2md.config import Config
from pdf2md.models import Manifest, Report
from pdf2md.pipeline import run_conversion
from helpers.normalize_outputs import normalize_manifest, normalize_report


def test_generated_manifest_and_report_match_current_models(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "schema-contract"
    result = run_conversion(Config(input_pdf=sample_pdf, output_dir=output_dir, pages="1", keep_page_markers=True))

    assert result.exit_code == 0
    manifest_payload = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report_payload = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))

    manifest = Manifest.model_validate(manifest_payload)
    report = Report.model_validate(report_payload)

    assert manifest.schema_version == "1.0"
    assert report.schema_version == "1.0"
    assert report.summary.text_line_extract_count >= 1


def test_additive_optional_fields_do_not_change_normalized_contract(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "schema-additive"
    result = run_conversion(Config(input_pdf=sample_pdf, output_dir=output_dir, pages="1", keep_page_markers=True))
    assert result.exit_code == 0

    manifest_payload = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report_payload = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    manifest_with_extra = deepcopy(manifest_payload)
    report_with_extra = deepcopy(report_payload)
    manifest_with_extra["future_optional_field"] = {"ignored": True}
    report_with_extra["future_optional_field"] = {"ignored": True}
    report_with_extra["summary"]["future_optional_metric"] = 1

    Manifest.model_validate(manifest_with_extra)
    Report.model_validate(report_with_extra)

    assert normalize_manifest(manifest_payload) == normalize_manifest(manifest_with_extra)
    assert normalize_report(report_payload) == normalize_report(report_with_extra)
