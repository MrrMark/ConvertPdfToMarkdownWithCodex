from __future__ import annotations

import json
from pathlib import Path

import pdf2md.utils.pdf as pdf_utils
from pdf2md.config import Config
from pdf2md.pipeline import run_conversion


def test_pipeline_reuses_pdfplumber_context_and_reports_performance_metadata(
    sample_pdf: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    real_open = pdf_utils.pdfplumber.open
    open_calls = 0

    def counting_open(*args, **kwargs):  # noqa: ANN001, ANN202
        nonlocal open_calls
        open_calls += 1
        return real_open(*args, **kwargs)

    monkeypatch.setattr(pdf_utils.pdfplumber, "open", counting_open)

    output_dir = tmp_path / "performance"
    result = run_conversion(Config(input_pdf=sample_pdf, output_dir=output_dir))

    assert result.exit_code == 0
    assert open_calls == 1
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    summary = report["summary"]
    assert summary["pdf_open_count"] == 2
    assert isinstance(summary["stage_durations_ms"], dict)
    assert {"pdf_open", "text_extraction", "table_extraction", "image_extraction"}.issubset(
        summary["stage_durations_ms"]
    )
    assert summary["pages_per_second"] is None or isinstance(summary["pages_per_second"], float)
    assert summary["page_cache_misses"] == 2
    assert summary["text_line_extract_count"] == 2
    assert summary["page_cache_hits"] >= 2
