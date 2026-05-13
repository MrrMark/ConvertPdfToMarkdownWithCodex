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


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _allowed_increase(baseline: float, max_regression: float) -> float:
    return baseline * (1.0 + max_regression)


def _allowed_decrease(baseline: float, max_regression: float) -> float:
    return baseline * max(0.0, 1.0 - max_regression)


def _append_relative_increase_regression(
    regressions: list[dict[str, Any]],
    *,
    page_count: int,
    metric: str,
    current: Any,
    baseline: Any,
    max_regression: float,
) -> None:
    current_number = _as_number(current)
    baseline_number = _as_number(baseline)
    if current_number is None or baseline_number is None:
        return
    limit = _allowed_increase(baseline_number, max_regression)
    if current_number > limit:
        regressions.append(
            {
                "type": "baseline_regression",
                "page_count": page_count,
                "metric": metric,
                "baseline": baseline,
                "current": current,
                "limit": round(limit, 6),
                "max_regression": max_regression,
                "direction": "increase",
            }
        )


def _append_relative_decrease_regression(
    regressions: list[dict[str, Any]],
    *,
    page_count: int,
    metric: str,
    current: Any,
    baseline: Any,
    max_regression: float,
) -> None:
    current_number = _as_number(current)
    baseline_number = _as_number(baseline)
    if current_number is None or baseline_number is None:
        return
    limit = _allowed_decrease(baseline_number, max_regression)
    if current_number < limit:
        regressions.append(
            {
                "type": "baseline_regression",
                "page_count": page_count,
                "metric": metric,
                "baseline": baseline,
                "current": current,
                "limit": round(limit, 6),
                "max_regression": max_regression,
                "direction": "decrease",
            }
        )


def _append_count_increase_regression(
    regressions: list[dict[str, Any]],
    *,
    page_count: int,
    metric: str,
    current: Any,
    baseline: Any,
) -> None:
    current_number = _as_number(current)
    baseline_number = _as_number(baseline)
    if current_number is None or baseline_number is None:
        return
    if current_number > baseline_number:
        regressions.append(
            {
                "type": "baseline_regression",
                "page_count": page_count,
                "metric": metric,
                "baseline": baseline,
                "current": current,
                "direction": "increase",
            }
        )


def apply_performance_gate(
    payload: dict[str, Any],
    *,
    baseline_report: dict[str, Any] | None = None,
    baseline_report_path: Path | None = None,
    max_duration_regression: float = 0.2,
    max_memory_regression: float = 0.2,
    min_pages_per_second: float | None = None,
) -> dict[str, Any]:
    """Add deterministic performance gate diagnostics to a benchmark payload."""
    thresholds = {
        "max_duration_regression": max_duration_regression,
        "max_memory_regression": max_memory_regression,
        "min_pages_per_second": min_pages_per_second,
    }
    regressions: list[dict[str, Any]] = []
    current_runs = payload.get("runs", [])

    if baseline_report is not None:
        baseline_by_page_count = {
            int(run["page_count"]): run
            for run in baseline_report.get("runs", [])
            if isinstance(run.get("page_count"), int)
        }
        for current_run in sorted(current_runs, key=lambda run: int(run.get("page_count", 0))):
            page_count = int(current_run.get("page_count", 0))
            baseline_run = baseline_by_page_count.get(page_count)
            if baseline_run is None:
                continue
            current_duration = current_run.get("total_duration_ms", current_run.get("elapsed_ms"))
            baseline_duration = baseline_run.get("total_duration_ms", baseline_run.get("elapsed_ms"))
            _append_relative_increase_regression(
                regressions,
                page_count=page_count,
                metric="total_duration_ms",
                current=current_duration,
                baseline=baseline_duration,
                max_regression=max_duration_regression,
            )
            _append_relative_increase_regression(
                regressions,
                page_count=page_count,
                metric="peak_memory_bytes",
                current=current_run.get("peak_memory_bytes"),
                baseline=baseline_run.get("peak_memory_bytes"),
                max_regression=max_memory_regression,
            )
            _append_relative_decrease_regression(
                regressions,
                page_count=page_count,
                metric="pages_per_second",
                current=current_run.get("pages_per_second"),
                baseline=baseline_run.get("pages_per_second"),
                max_regression=max_duration_regression,
            )
            current_stages = current_run.get("stage_durations_ms", {})
            baseline_stages = baseline_run.get("stage_durations_ms", {})
            for stage in sorted(set(current_stages) | set(baseline_stages)):
                _append_relative_increase_regression(
                    regressions,
                    page_count=page_count,
                    metric=f"stage_durations_ms.{stage}",
                    current=current_stages.get(stage, 0),
                    baseline=baseline_stages.get(stage, 0),
                    max_regression=max_duration_regression,
                )
            for metric in ("pdf_open_count", "text_line_extract_count"):
                _append_count_increase_regression(
                    regressions,
                    page_count=page_count,
                    metric=metric,
                    current=current_run.get(metric),
                    baseline=baseline_run.get(metric),
                )

    if min_pages_per_second is not None:
        for current_run in sorted(current_runs, key=lambda run: int(run.get("page_count", 0))):
            pages_per_second = _as_number(current_run.get("pages_per_second"))
            if pages_per_second is None or pages_per_second >= min_pages_per_second:
                continue
            regressions.append(
                {
                    "type": "threshold_failure",
                    "page_count": int(current_run.get("page_count", 0)),
                    "metric": "pages_per_second",
                    "limit": min_pages_per_second,
                    "current": pages_per_second,
                }
            )

    payload["baseline_report"] = str(baseline_report_path) if baseline_report_path else None
    payload["thresholds"] = thresholds
    payload["regressions"] = regressions
    payload["passed_performance_gate"] = len(regressions) == 0
    return payload


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
                "total_duration_ms": elapsed_ms,
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
    parser.add_argument("--baseline-report", type=Path, help="Previous benchmark_report.json to compare against.")
    parser.add_argument("--fail-on-regression", action="store_true", help="Return non-zero when the performance gate fails.")
    parser.add_argument(
        "--max-duration-regression",
        type=float,
        default=0.2,
        help="Allowed relative duration regression versus baseline. Default: 0.2.",
    )
    parser.add_argument(
        "--max-memory-regression",
        type=float,
        default=0.2,
        help="Allowed relative peak memory regression versus baseline. Default: 0.2.",
    )
    parser.add_argument("--min-pages-per-second", type=float, help="Minimum allowed pages/sec for each run.")
    args = parser.parse_args()
    page_counts = [int(value) for value in args.page_counts.split(",") if value.strip()]
    payload = run_benchmark(Path(args.output_dir), page_counts)
    baseline_report = _read_json(args.baseline_report) if args.baseline_report else None
    payload = apply_performance_gate(
        payload,
        baseline_report=baseline_report,
        baseline_report_path=args.baseline_report,
        max_duration_regression=args.max_duration_regression,
        max_memory_regression=args.max_memory_regression,
        min_pages_per_second=args.min_pages_per_second,
    )
    report_path = Path(args.output_dir) / "benchmark_report.json"
    write_json(report_path, payload)
    print(f"Wrote {report_path}")
    if args.fail_on_regression and not payload["passed_performance_gate"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
