from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pdf2md.pipeline as pipeline_module
from pdf2md.config import Config
from pdf2md.extractors.images import ImageExtractionResult
from pdf2md.extractors.ocr import OcrResult
from pdf2md.extractors.tables import TableExtractionResult
from pdf2md.models import ImageMode, TableAsset, TableMode, WarningEntry
from pdf2md.pipeline import EXIT_PARTIAL, EXIT_SUCCESS, run_conversion


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return cls(2024, 1, 2, 3, 4, 5, tzinfo=tz or timezone.utc)


def test_pipeline_report_schema_and_partial_status(sample_pdf: Path, tmp_path: Path, monkeypatch) -> None:
    def fake_run_ocr(*args, **kwargs) -> OcrResult:
        return OcrResult(
            warnings=[WarningEntry(code="OCR_CONFIDENCE_WARN", message="warn", page=1)],
            page_texts={},
            ocr_pages=[],
            used_ocr=False,
        )

    def fake_extract_tables(*args, **kwargs) -> TableExtractionResult:
        result = TableExtractionResult(
            warnings=[
                WarningEntry(
                    code="TABLE_COMPLEXITY_HTML_FALLBACK",
                    message="fallback",
                    page=1,
                    details={"table_index": 1, "reasons": ["AMBIGUOUS_GRID"]},
                )
            ],
            assets=[TableAsset(page=1, index=1, mode="html", bbox=[10.0, 20.0, 30.0, 40.0])],
            fallbacks=[
                {
                    "page": 1,
                    "table_index": 1,
                    "mode": "html",
                    "reasons": ["AMBIGUOUS_GRID"],
                    "selected_strategy": "default",
                    "quality_score": 0.42,
                }
            ],
            table_quality=[],
            table_counts={
                "table_total": 1,
                "table_html_count": 1,
                "table_gfm_count": 0,
                "table_recovered_count": 0,
                "table_unresolved_count": 1,
            },
        )
        return result

    monkeypatch.setattr(pipeline_module, "run_ocr", fake_run_ocr)
    monkeypatch.setattr(pipeline_module, "extract_tables", fake_extract_tables)
    monkeypatch.setattr(pipeline_module, "extract_images", lambda *args, **kwargs: ImageExtractionResult())

    output_dir = tmp_path / "reporting"
    result = run_conversion(
        Config(
            input_pdf=sample_pdf,
            output_dir=output_dir,
            image_mode=ImageMode.REFERENCED,
            table_mode=TableMode.AUTO,
        )
    )

    assert result.exit_code == EXIT_PARTIAL
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert report["schema_version"] == "1.0"
    assert manifest["schema_version"] == "1.0"
    assert report["status"] == "partial_success"
    assert report["summary"]["table_fallback_count"] == 1
    assert report["summary"]["page_status_counts"]["partial_success"] == 1
    assert report["summary"]["page_status_counts"]["success"] == 1


def test_pipeline_outputs_are_deterministic_with_fixed_clock(sample_pdf: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(pipeline_module, "datetime", _FixedDateTime)

    first = tmp_path / "first"
    second = tmp_path / "second"
    config_first = Config(input_pdf=sample_pdf, output_dir=first)
    config_second = Config(input_pdf=sample_pdf, output_dir=second)

    result_first = run_conversion(config_first)
    result_second = run_conversion(config_second)

    assert result_first.exit_code == EXIT_SUCCESS
    assert result_second.exit_code == EXIT_SUCCESS
    assert (first / "document.md").read_text(encoding="utf-8") == (second / "document.md").read_text(encoding="utf-8")
    assert (first / "manifest.json").read_text(encoding="utf-8") == (second / "manifest.json").read_text(encoding="utf-8")
    assert (first / "report.json").read_text(encoding="utf-8") == (second / "report.json").read_text(encoding="utf-8")
