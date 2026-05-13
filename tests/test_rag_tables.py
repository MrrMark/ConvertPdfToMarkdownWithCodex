from __future__ import annotations

import json
from pathlib import Path

import pdf2md.pipeline as pipeline_module
import pytest
from pdf2md.config import Config
from pdf2md.extractors.images import ImageExtractionResult
from pdf2md.extractors.ocr import OcrResult
from pdf2md.extractors.tables import TableExtractionResult
from pdf2md.models import RagTableOutputMode, TableMode, WarningEntry
from pdf2md.pipeline import run_conversion
from pdf2md.serializers.rag_tables import serialize_rag_tables_jsonl, serialize_rag_tables_markdown


def _rag_table_payload() -> list[dict]:
    return [
        {
            "page": 1,
            "table_index": 1,
            "source_mode": "html",
            "caption_text": "Table 1: Example",
            "headers": ["Field", "Value"],
            "bbox": [10.0, 20.0, 120.0, 80.0],
            "quality_score": 0.42,
            "fallback_reasons": ["AMBIGUOUS_GRID"],
            "records": [
                {
                    "page": 1,
                    "table_index": 1,
                    "source_mode": "html",
                    "caption_text": "Table 1: Example",
                    "headers": ["Field", "Value"],
                    "row_index": 1,
                    "cells": {"Field": "alpha", "Value": "beta"},
                    "row_text": "Field = alpha | Value = beta",
                    "bbox": [10.0, 20.0, 120.0, 80.0],
                    "quality_score": 0.42,
                    "fallback_reasons": ["AMBIGUOUS_GRID"],
                }
            ],
        }
    ]


def test_rag_table_serializers_preserve_row_text() -> None:
    payload = _rag_table_payload()

    markdown = serialize_rag_tables_markdown(payload)
    jsonl = serialize_rag_tables_jsonl(payload)

    assert "<!-- table-rag: page=1 index=1 source=html -->" in markdown
    assert "Caption: Table 1: Example" in markdown
    assert "Row 1: Field = alpha | Value = beta" in markdown
    record = json.loads(jsonl)
    assert record["table_id"] == "page-0001-table-0001"
    assert record["table_row_id"] == "page-0001-table-0001-row-0001"
    assert record["cells"] == {"Field": "alpha", "Value": "beta"}
    assert record["fallback_reasons"] == ["AMBIGUOUS_GRID"]


@pytest.mark.parametrize(
    ("mode", "markdown_expected", "jsonl_expected", "file_count"),
    [
        (RagTableOutputMode.MARKDOWN, True, False, 1),
        (RagTableOutputMode.JSONL, False, True, 1),
        (RagTableOutputMode.BOTH, True, True, 2),
    ],
)
def test_pipeline_writes_selected_rag_sidecar_outputs(
    sample_pdf: Path,
    tmp_path: Path,
    monkeypatch,
    mode: RagTableOutputMode,
    markdown_expected: bool,
    jsonl_expected: bool,
    file_count: int,
) -> None:
    def fake_extract_tables(*args, **kwargs) -> TableExtractionResult:
        return TableExtractionResult(
            warnings=[
                WarningEntry(
                    code="TABLE_COMPLEXITY_HTML_FALLBACK",
                    message="fallback",
                    page=1,
                    details={"table_index": 1, "reasons": ["AMBIGUOUS_GRID"]},
                )
            ],
            rag_tables=_rag_table_payload(),
            table_quality=[
                {
                    "page": 1,
                    "table_index": 1,
                    "quality_score": 0.42,
                    "caption_text": "Table 1: Example",
                }
            ],
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
            table_counts={
                "table_total": 1,
                "table_html_count": 1,
                "table_gfm_count": 0,
                "table_recovered_count": 0,
                "table_unresolved_count": 1,
                "table_markdown_forced_count": 0,
                "table_html_forced_count": 0,
            },
        )

    monkeypatch.setattr(pipeline_module, "extract_tables", fake_extract_tables)
    monkeypatch.setattr(pipeline_module, "extract_images", lambda *args, **kwargs: ImageExtractionResult())
    monkeypatch.setattr(pipeline_module, "run_ocr", lambda *args, **kwargs: OcrResult())

    output_dir = tmp_path / f"rag-sidecars-{mode.value}"
    result = run_conversion(
        Config(
            input_pdf=sample_pdf,
            output_dir=output_dir,
            table_mode=TableMode.AUTO,
            rag_table_output=mode,
        )
    )

    assert result.exit_code == 2
    assert (output_dir / "rag_tables.md").exists() is markdown_expected
    assert (output_dir / "tables_rag.jsonl").exists() is jsonl_expected
    if markdown_expected:
        assert (output_dir / "rag_tables.md").read_text(encoding="utf-8").startswith("<!-- table-rag")
    if jsonl_expected:
        records = (output_dir / "tables_rag.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(records) == 1
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["options"]["rag_table_output"] == mode.value
    assert report["summary"]["rag_table_output"] == mode.value
    assert report["summary"]["rag_table_record_count"] == 1
    assert report["summary"]["rag_table_file_count"] == file_count
    assert report["summary"]["table_fallback_reason_counts"] == {"AMBIGUOUS_GRID": 1}
    assert report["summary"]["table_low_quality_count"] == 1
    assert report["summary"]["table_caption_linked_count"] == 1
    assert report["summary"]["semantic_unit_file_count"] == 1
    assert report["summary"]["requirement_file_count"] == 1
    assert report["summary"]["cross_ref_file_count"] == 1
    assert (output_dir / "semantic_units_rag.jsonl").exists()
    assert (output_dir / "requirements_rag.jsonl").exists()
    assert (output_dir / "cross_refs_rag.jsonl").exists()


def test_pipeline_does_not_write_rag_sidecars_by_default(sample_pdf: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline_module,
        "extract_tables",
        lambda *args, **kwargs: TableExtractionResult(rag_tables=_rag_table_payload()),
    )
    monkeypatch.setattr(pipeline_module, "extract_images", lambda *args, **kwargs: ImageExtractionResult())
    monkeypatch.setattr(pipeline_module, "run_ocr", lambda *args, **kwargs: OcrResult())

    output_dir = tmp_path / "rag-none"
    result = run_conversion(Config(input_pdf=sample_pdf, output_dir=output_dir))

    assert result.exit_code == 0
    assert not (output_dir / "rag_tables.md").exists()
    assert not (output_dir / "tables_rag.jsonl").exists()
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["summary"]["rag_table_output"] == "none"
    assert report["summary"]["rag_table_record_count"] == 0
