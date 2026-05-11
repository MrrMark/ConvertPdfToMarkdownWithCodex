#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import tracemalloc
from pathlib import Path
from typing import Any

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject

from pdf2md.config import Config
from pdf2md.pipeline import run_conversion
from pdf2md.utils.io import write_json


def _text_operand(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return f"({escaped})"


def _write_benchmark_pdf(path: Path, page_count: int) -> None:
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)  # noqa: SLF001
    for page_number in range(1, page_count + 1):
        page = writer.add_blank_page(width=595, height=842)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
        )
        lines = [
            f"BT /F1 12 Tf 72 760 Td {_text_operand(f'Benchmark page {page_number}')} Tj ET",
            f"BT /F1 10 Tf 72 730 Td {_text_operand('Alpha beta gamma delta')} Tj ET",
        ]
        content = StreamObject()
        content._data = "\n".join(lines).encode("utf-8")  # noqa: SLF001
        page[NameObject("/Contents")] = writer._add_object(content)  # noqa: SLF001
    with path.open("wb") as fp:
        writer.write(fp)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_benchmark(output_dir: Path, page_counts: list[int]) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    for page_count in page_counts:
        pdf_path = output_dir / f"benchmark-{page_count}.pdf"
        document_output = output_dir / f"benchmark-{page_count}-output"
        _write_benchmark_pdf(pdf_path, page_count)
        tracemalloc.start()
        started = time.perf_counter()
        result = run_conversion(Config(input_pdf=pdf_path, output_dir=document_output, keep_page_markers=True))
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        report = _read_json(document_output / "report.json")
        summary = report.get("summary", {})
        runs.append(
            {
                "page_count": page_count,
                "status": getattr(result.status, "value", str(result.status)),
                "exit_code": result.exit_code,
                "elapsed_ms": elapsed_ms,
                "peak_memory_bytes": peak,
                "stage_durations_ms": summary.get("stage_durations_ms", {}),
                "pages_per_second": summary.get("pages_per_second"),
                "pdf_open_count": summary.get("pdf_open_count"),
                "text_line_extract_count": summary.get("text_line_extract_count"),
            }
        )
    return {"runs": runs}


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark pdf2md conversion with synthetic PDFs.")
    parser.add_argument("--output-dir", default="benchmark_output")
    parser.add_argument("--page-counts", default="10,50,100")
    args = parser.parse_args()
    page_counts = [int(value) for value in args.page_counts.split(",") if value.strip()]
    payload = run_benchmark(Path(args.output_dir), page_counts)
    report_path = Path(args.output_dir) / "benchmark_report.json"
    write_json(report_path, payload)
    print(f"Wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
