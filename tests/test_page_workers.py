from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fixtures.pdf_builder import build_multi_page_text_pdf
from pdf2md.cli import build_parser
from pdf2md.config import Config
from pdf2md.pipeline import run_conversion
from pdf2md.utils.page_executor import effective_page_worker_count


def test_page_workers_cli_and_config_validation(tmp_path: Path) -> None:
    args = build_parser().parse_args(["input.pdf", "--page-workers", "2"])
    assert args.page_workers == 2

    with pytest.raises(ValidationError):
        Config(input_pdf=tmp_path / "input.pdf", output_dir=tmp_path / "out", page_workers=0)


def test_effective_page_worker_count_is_capped() -> None:
    assert effective_page_worker_count(1, 10) == 1
    assert effective_page_worker_count(8, 1) == 1
    assert effective_page_worker_count(4, 3) <= 3


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
    assert parallel_manifest["options"]["page_workers"] == 2
    assert parallel_manifest["options"]["page_parallel_enabled"] is True
