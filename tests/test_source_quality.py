from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fixtures.pdf_builder import PageSpec, PositionedText, TableSpec, build_nested_cell_table_pdf, write_pdf
from pdf2md.config import Config
from pdf2md.pipeline import run_conversion
from pdf2md.quality_eval import SourceTruth, evaluate_source_quality
from scripts.evaluate_source_quality import main


def _case(tmp_path: Path, markdown: str, checks: list[dict]) -> tuple[Path, Path, Path]:
    source = tmp_path / "source.pdf"
    write_pdf(source, [PageSpec(texts=[PositionedText("Fixture source", 40, 700)])])
    output = tmp_path / "converted"
    output.mkdir()
    (output / "document.md").write_text("<!-- page: 1 -->\n" + markdown, encoding="utf-8")
    (output / "manifest.json").write_text('{"tables": []}', encoding="utf-8")
    for name in ["figures_rag.jsonl", "figure_ocr_evidence_rag.jsonl"]:
        (output / name).write_text("", encoding="utf-8")
    truth = tmp_path / "truth.json"
    truth.write_text(json.dumps({
        "case_id": "synthetic", "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "reviewed_from": "synthetic_source_definition", "review_note": "Hand-authored assertions",
        "pages": [{"page": 1, "physical_page": 25, "printed_page": "1"}], "checks": checks,
    }), encoding="utf-8")
    return output, source, truth


def _evaluate(case: tuple[Path, Path, Path]):
    return evaluate_source_quality(output_dir=case[0], input_pdf=case[1], truth_path=case[2])


def _jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


def test_empty_table_known_failure_is_not_quality_success(tmp_path: Path) -> None:
    case = _case(tmp_path, '<!-- table: page=1 index=1 mode=html -->\n<table><tr><th> </th></tr></table>', [{
        "check_id": "empty", "kind": "no_empty_tables", "page": 1,
        "known_failure_records": ["page-0001-table-0001"],
    }])
    report = _evaluate(case)
    assert report.gate_passed and not report.quality_passed
    assert report.results[0].status == "known_failure"
    assert report.results[0].physical_page == 25
    assert report.results[0].printed_page == "1"

    with (case[0] / "document.md").open("a") as file:
        file.write('\n<!-- table: page=1 index=2 mode=html -->\n<table><tr><td></td></tr></table>')
    assert not _evaluate(case).gate_passed  # Same check, additional defect cannot be allowlisted implicitly.


def test_stale_allowlist_fails_after_fix(tmp_path: Path) -> None:
    case = _case(tmp_path, "Normal text.", [{
        "check_id": "empty", "kind": "no_empty_tables", "page": 1,
        "known_failure_records": ["page-0001-table-0001"],
    }])
    report = _evaluate(case)
    assert report.quality_passed and not report.gate_passed
    assert report.results[0].status == "stale_allowlist"


@pytest.mark.parametrize("body", [
    '<tr><td colspan="2">Merged source cell</td></tr>',
    '<tr><td><img src="scanned-cell.png"></td></tr>',
    '<tr><td><table><tr><td>Nested content</td></tr></table></td></tr>',
])
def test_nonempty_complex_cells_are_not_reported_as_empty(tmp_path: Path, body: str) -> None:
    case = _case(tmp_path, f'<!-- table: page=1 index=1 mode=html -->\n<table>{body}</table>', [
        {"check_id": "empty", "kind": "no_empty_tables", "page": 1},
    ])
    assert _evaluate(case).quality_passed


@pytest.mark.parametrize("nested,correct_parent,expected", [(False, True, False), (True, False, False), (True, True, True)])
def test_nested_table_requires_child_inside_correct_parent_cell(
    tmp_path: Path, nested: bool, correct_parent: bool, expected: bool,
) -> None:
    child = '<table><tr><th>Bits</th><th>Description</th></tr><tr><td>07:04</td><td>Type</td></tr><tr><td>03:00</td><td>Subtype</td></tr></table>'
    value = child if nested else "Bits Description 07:04 Type 03:00 Subtype"
    row_label = "15" if correct_parent else "14:12"
    markdown = f'<!-- table: page=1 index=1 mode=html -->\n<table><tr><td>{row_label}</td><td>{value}</td></tr></table>'
    case = _case(tmp_path, markdown, [{
        "check_id": "nested", "kind": "nested_table", "page": 1, "record_id": "page-0001-table-0001",
        "row_label": "15", "column": 1, "tokens": ["Bits", "07:04", "Type", "03:00", "Subtype"],
    }])
    assert _evaluate(case).quality_passed is expected


@pytest.mark.parametrize("text,expected", [
    ("장치 규칙 NVMe-oF 1_00000000_00000000h shall", True),
    ("장치 규칙 NVMe-of 1_00000000_00000000h shall", False),
    ("shall 장치 규칙 NVMe-oF 1_00000000_00000000h", False),
    ("장치 규칙 NVMe-oF 1_00000000_00000000 shall", False),
])
def test_korean_identifiers_and_reading_order_are_not_rewritten(tmp_path: Path, text: str, expected: bool) -> None:
    case = _case(tmp_path, text, [{
        "check_id": "text", "kind": "text_sequence", "page": 1,
        "tokens": ["장치 규칙", "NVMe-oF", "1_00000000_00000000h", "shall"],
    }])
    assert _evaluate(case).quality_passed is expected


@pytest.mark.parametrize("status,reason,expected", [
    ("accepted", None, False), ("rejected", "empty_result", False),
    ("runtime_unavailable", "runtime_unavailable", False), ("not_attempted", "tiny_decorative", True),
])
def test_decorative_ocr_requires_explicit_skip_evidence(tmp_path: Path, status: str, reason: str, expected: bool) -> None:
    case = _case(tmp_path, "", [{"check_id": "ocr", "kind": "no_decorative_ocr", "page": 1, "count": 1}])
    _jsonl(case[0] / "figures_rag.jsonl", [{
        "figure_id": "decorative", "page": 1, "status": "excluded", "classification_reasons": ["TINY_DECORATIVE"],
    }])
    _jsonl(case[0] / "figure_ocr_evidence_rag.jsonl", [{
        "target_id": "decorative", "target_type": "figure", "status": status, "rejected_reason": reason,
    }])
    assert _evaluate(case).quality_passed is expected
    (case[0] / "figure_ocr_evidence_rag.jsonl").write_text("")
    assert not _evaluate(case).quality_passed
    (case[0] / "figures_rag.jsonl").write_text("")
    assert not _evaluate(case).quality_passed  # Missing candidates cannot masquerade as an optimization.


def test_vector_figure_requires_caption_position_and_asset(tmp_path: Path) -> None:
    case = _case(tmp_path, "Figure 1: Network", [{
        "check_id": "figure", "kind": "figure_region", "page": 1, "record_id": "figure-1",
        "tokens": ["Figure 1:", "Network"], "bbox": [10, 20, 110, 120],
    }])
    record = {"figure_id": "one", "page": 1, "status": "available", "path": "image.png",
              "caption_text": "Figure 1: Network", "bbox": [10, 20, 110, 120]}
    _jsonl(case[0] / "figures_rag.jsonl", [record])
    assert not _evaluate(case).quality_passed
    from PIL import Image
    Image.new("RGB", (10, 10), "white").save(case[0] / "image.png")
    assert _evaluate(case).quality_passed
    record["bbox"] = [200, 200, 300, 300]
    _jsonl(case[0] / "figures_rag.jsonl", [record])
    assert not _evaluate(case).quality_passed


def test_invalid_truth_and_identity_do_not_pass(tmp_path: Path) -> None:
    case = _case(tmp_path, "text", [{"check_id": "text", "kind": "text_sequence", "page": 1, "tokens": ["text"]}])
    payload = json.loads(case[2].read_text())
    payload["input_sha256"] = "0" * 64
    case[2].write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="input_sha256"):
        _evaluate(case)
    payload["checks"][0]["tokens"] = []
    with pytest.raises(ValidationError):
        SourceTruth.model_validate(payload)
    payload["checks"][0]["tokens"] = ["text"]
    payload["checks"].append(payload["checks"][0])
    with pytest.raises(ValidationError, match="duplicate check_id"):
        SourceTruth.model_validate(payload)


def test_cli_exit_codes_report_and_input_protection(tmp_path: Path) -> None:
    case = _case(tmp_path, "text", [{"check_id": "text", "kind": "text_sequence", "page": 1, "tokens": ["text"]}])
    args = ["--output-dir", str(case[0]), "--input-pdf", str(case[1]), "--truth", str(case[2])]
    report = tmp_path / "report.json"
    assert main(args + ["--report", str(report)]) == 0
    assert json.loads(report.read_text())["quality_passed"] is True
    (case[0] / "document.md").write_text("<!-- page: 1 -->\nwrong")
    assert main(args + ["--report", str(report)]) == 1
    assert main(args + ["--report", str(case[2])]) == 2
    assert main(args + ["--report", str(case[0] / "document.md")]) == 2


def test_real_conversion_simple_table_has_no_false_positive(tmp_path: Path) -> None:
    case = _case(tmp_path, "", [
        {"check_id": "empty", "kind": "no_empty_tables", "page": 1},
        {"check_id": "tables", "kind": "table_count", "page": 1, "count": 1},
        {"check_id": "tokens", "kind": "text_sequence", "page": 1, "tokens": ["Command", "ABCD", "0001h"]},
    ])
    write_pdf(case[1], [PageSpec(tables=[TableSpec(
        rows=[["Command", "Value"], ["ABCD", "0001h"]], x=50, y=700, column_widths=[120, 120],
    )])])
    payload = json.loads(case[2].read_text())
    payload["input_sha256"] = hashlib.sha256(case[1].read_bytes()).hexdigest()
    case[2].write_text(json.dumps(payload))
    result = run_conversion(Config(input_pdf=case[1], output_dir=case[0], keep_page_markers=True))
    assert result.exit_code == 0
    assert _evaluate(case).quality_passed


def test_synthetic_pdf_preserves_nested_structure(tmp_path: Path) -> None:
    case = _case(tmp_path, "", [
        {"check_id": "parent", "kind": "table_count", "page": 1, "count": 1},
        {"check_id": "raw-cell", "kind": "table_cell", "page": 1,
         "record_id": "page-0001-table-0001", "row_label": "15", "column": 1,
         "tokens": ["Identifier", "07:04", "Type 0h", "03:00", "Subtype 1h"]},
        {"check_id": "nested", "kind": "nested_table", "page": 1,
         "record_id": "page-0001-table-0001", "row_label": "15", "column": 1,
         "tokens": ["Bits", "Meaning", "07:04", "Type 0h", "03:00", "Subtype 1h"]},
    ])
    build_nested_cell_table_pdf(case[1])
    payload = json.loads(case[2].read_text())
    payload["input_sha256"] = hashlib.sha256(case[1].read_bytes()).hexdigest()
    payload["review_note"] = "Parent cell 15 contains the child grid defined in build_nested_cell_table_pdf."
    case[2].write_text(json.dumps(payload))
    result = run_conversion(Config(input_pdf=case[1], output_dir=case[0], keep_page_markers=True))
    assert result.exit_code == 0
    report = _evaluate(case)
    assert report.gate_passed and report.quality_passed
    assert [result.status for result in report.results] == ["passed", "passed", "passed"]


def test_gfm_escaped_pipe_cell_and_html_entities(tmp_path: Path) -> None:
    case = _case(tmp_path, '<!-- table: page=1 index=1 mode=gfm -->\n| Label | Value |\n| --- | --- |\n| A | x\\|y &lt; 2 |\n', [{
        "check_id": "cell", "kind": "table_cell", "page": 1, "record_id": "page-0001-table-0001",
        "row_label": "A", "column": 1, "tokens": ["x|y < 2"],
    }])
    assert _evaluate(case).quality_passed


def test_report_is_deterministic_and_omits_source_tokens(tmp_path: Path) -> None:
    case = _case(tmp_path, "PRIVATE_SOURCE_TOKEN", [{
        "check_id": "text", "kind": "text_sequence", "page": 1, "tokens": ["PRIVATE_SOURCE_TOKEN"],
    }])
    report = _evaluate(case).model_dump_json()
    assert report == _evaluate(case).model_dump_json()
    assert "PRIVATE_SOURCE_TOKEN" not in report
    assert str(tmp_path) not in report
