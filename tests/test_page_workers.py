from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fixtures.pdf_builder import (
    PageSpec,
    PositionedText,
    TableSpec,
    build_complex_table_pdf,
    build_continued_table_pdf,
    build_multi_page_text_pdf,
    build_repeated_template_table_pdf,
    build_simple_table_pdf,
    write_pdf,
)
from pdf2md.cli import build_parser
from pdf2md.config import Config
from pdf2md.extractors.page_worker import PageWorkerInput
from pdf2md.models import RagTableOutputMode
from pdf2md.pipeline import run_conversion
from pdf2md.utils.page_executor import _chunk_page_worker_inputs, effective_page_worker_count, run_page_workers
from helpers.normalize_outputs import normalize_manifest, normalize_report


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_report_for_worker_equivalence(payload: dict) -> dict:
    normalized = normalize_report(payload)
    summary = normalized.get("summary", {})
    for key in ("pdf_open_count", "page_cache_hits", "page_cache_misses", "text_line_extract_count"):
        summary.pop(key, None)
    return normalized


def _assert_table_outputs_match(single_output: Path, parallel_output: Path) -> None:
    for filename in ("document.md", "rag_tables.md", "tables_rag.jsonl", "technical_tables_rag.jsonl"):
        assert (single_output / filename).read_text(encoding="utf-8") == (
            parallel_output / filename
        ).read_text(encoding="utf-8")

    assert normalize_manifest(_read_json(single_output / "manifest.json")) == normalize_manifest(
        _read_json(parallel_output / "manifest.json")
    )
    assert _normalize_report_for_worker_equivalence(_read_json(single_output / "report.json")) == (
        _normalize_report_for_worker_equivalence(_read_json(parallel_output / "report.json"))
    )


def test_page_workers_cli_and_config_validation(tmp_path: Path) -> None:
    args = build_parser().parse_args(["input.pdf", "--page-workers", "2"])
    assert args.page_workers == 2

    with pytest.raises(ValidationError):
        Config(input_pdf=tmp_path / "input.pdf", output_dir=tmp_path / "out", page_workers=0)


def test_effective_page_worker_count_is_capped() -> None:
    assert effective_page_worker_count(1, 10) == 1
    assert effective_page_worker_count(8, 1) == 1
    assert effective_page_worker_count(4, 3) <= 3


def test_page_worker_inputs_are_chunked_by_effective_worker_count(tmp_path: Path) -> None:
    inputs = [PageWorkerInput(pdf_path=tmp_path / "input.pdf", page=page) for page in range(1, 6)]

    chunks = _chunk_page_worker_inputs(inputs, worker_count=3)

    assert [[worker_input.page for worker_input in chunk] for chunk in chunks] == [[1, 2], [3, 4], [5]]


def test_run_page_workers_accepts_empty_input() -> None:
    assert run_page_workers([], worker_count=4) == []


def test_page_workers_preserve_deterministic_outputs(tmp_path: Path) -> None:
    pdf_path = tmp_path / "multi.pdf"
    build_multi_page_text_pdf(pdf_path, page_count=3)
    single_output = tmp_path / "single"
    parallel_output = tmp_path / "parallel"

    single = run_conversion(
        Config(
            input_pdf=pdf_path,
            output_dir=single_output,
            keep_page_markers=True,
            page_workers=1,
        )
    )
    parallel = run_conversion(
        Config(
            input_pdf=pdf_path,
            output_dir=parallel_output,
            keep_page_markers=True,
            page_workers=2,
        )
    )

    assert single.exit_code == parallel.exit_code == 0
    assert (single_output / "document.md").read_text(encoding="utf-8") == (
        parallel_output / "document.md"
    ).read_text(encoding="utf-8")
    assert (single_output / "text_blocks_rag.jsonl").read_text(encoding="utf-8") == (
        parallel_output / "text_blocks_rag.jsonl"
    ).read_text(encoding="utf-8")
    assert (single_output / "retrieval_chunks_rag.jsonl").read_text(encoding="utf-8") == (
        parallel_output / "retrieval_chunks_rag.jsonl"
    ).read_text(encoding="utf-8")

    single_report = json.loads((single_output / "report.json").read_text(encoding="utf-8"))
    parallel_report = json.loads((parallel_output / "report.json").read_text(encoding="utf-8"))
    parallel_manifest = json.loads((parallel_output / "manifest.json").read_text(encoding="utf-8"))
    assert single_report["summary"]["page_worker_count"] == 1
    assert single_report["summary"]["page_parallel_enabled"] is False
    assert parallel_report["summary"]["page_worker_count"] == 2
    assert parallel_report["summary"]["page_parallel_enabled"] is True
    assert parallel_report["summary"]["page_worker_effective_count"] == 2
    assert parallel_report["summary"]["pdf_open_count"] == parallel_report["summary"]["page_worker_effective_count"] + 2
    assert parallel_manifest["options"]["page_workers"] == 2
    assert parallel_manifest["options"]["page_parallel_enabled"] is True


@pytest.mark.parametrize(
    ("case_name", "builder"),
    [
        ("simple_gfm", build_simple_table_pdf),
        ("complex_html", build_complex_table_pdf),
        ("continued_table", build_continued_table_pdf),
        ("repeated_template_table", build_repeated_template_table_pdf),
    ],
)
def test_page_workers_preserve_table_candidate_outputs(tmp_path: Path, case_name: str, builder) -> None:  # noqa: ANN001
    pdf_path = tmp_path / f"{case_name}.pdf"
    single_output = tmp_path / f"{case_name}-single"
    parallel_output = tmp_path / f"{case_name}-parallel"
    builder(pdf_path)

    single = run_conversion(
        Config(
            input_pdf=pdf_path,
            output_dir=single_output,
            keep_page_markers=True,
            rag_table_output=RagTableOutputMode.BOTH,
            page_workers=1,
        )
    )
    parallel = run_conversion(
        Config(
            input_pdf=pdf_path,
            output_dir=parallel_output,
            keep_page_markers=True,
            rag_table_output=RagTableOutputMode.BOTH,
            page_workers=2,
        )
    )

    assert single.exit_code == parallel.exit_code
    _assert_table_outputs_match(single_output, parallel_output)

    parallel_report = _read_json(parallel_output / "report.json")
    parallel_manifest = _read_json(parallel_output / "manifest.json")
    assert parallel_report["summary"]["page_worker_count"] == 2
    assert parallel_report["summary"]["page_worker_effective_count"] == min(2, parallel_manifest["total_pages"])
    assert parallel_report["summary"]["page_parallel_enabled"] == (parallel_manifest["total_pages"] > 1)
    assert parallel_report["summary"]["pdf_open_count"] >= parallel_report["summary"]["page_worker_effective_count"]


def test_page_worker_table_candidate_failure_is_page_scoped_and_ordered(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    pdf_path = tmp_path / "table-worker-failure.pdf"
    output_dir = tmp_path / "out"
    write_pdf(
        pdf_path,
        [
            PageSpec(
                texts=[PositionedText("Table 1: Complex fields", 72, 760)],
                tables=[
                    TableSpec(
                        [
                            ["", "Latency", "Latency"],
                            ["Command", "Min", "Max"],
                            ["Read", "1", "3"],
                        ],
                        72,
                        730,
                        [120, 90, 90],
                    )
                ],
            ),
            PageSpec(tables=[TableSpec([["Field", "Value"], ["beta", "2"]], 72, 730, [120, 120])]),
        ],
    )

    from pdf2md.extractors import page_worker as page_worker_module

    original_collect = page_worker_module.collect_table_candidates_for_page

    def fail_second_page(page, page_number):  # noqa: ANN001, ANN202
        if page_number == 2:
            raise RuntimeError("synthetic table candidate failure")
        return original_collect(page, page_number)

    monkeypatch.setattr(page_worker_module, "collect_table_candidates_for_page", fail_second_page)

    result = run_conversion(
        Config(
            input_pdf=pdf_path,
            output_dir=output_dir,
            keep_page_markers=True,
            rag_table_output=RagTableOutputMode.BOTH,
            page_workers=2,
        )
    )

    assert result.exit_code == 2
    report = _read_json(output_dir / "report.json")
    table_warnings = [warning for warning in report["warnings"] if warning["code"].startswith("TABLE_")]
    assert [warning["page"] for warning in table_warnings] == [1, 2]
    assert table_warnings[0]["code"] == "TABLE_COMPLEXITY_HTML_FALLBACK"
    assert table_warnings[1]["code"] == "TABLE_EXTRACTION_FAILED"
    assert table_warnings[1]["details"] == {"phase": "table_candidate_collection"}
    assert "synthetic table candidate failure" in table_warnings[1]["message"]
    assert report["summary"]["failed_page_count"] == 0
    page_two = next(page for page in report["page_results"] if page["page"] == 2)
    assert page_two["status"] == "partial_success"
    assert page_two["warning_count"] == 1
