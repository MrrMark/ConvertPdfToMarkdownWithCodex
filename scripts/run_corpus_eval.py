#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pdf2md.config import Config
from pdf2md.models import RagTableOutputMode
from pdf2md.pipeline import run_conversion
from pdf2md.utils.io import write_json


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _merge_counts(target: dict[str, int], source: dict[str, int]) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0) + int(value)


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _append_increase_regression(
    regressions: list[dict[str, Any]],
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
                "metric": metric,
                "baseline": baseline,
                "current": current,
                "direction": "increase",
            }
        )


def _append_decrease_regression(
    regressions: list[dict[str, Any]],
    metric: str,
    current: Any,
    baseline: Any,
) -> None:
    current_number = _as_number(current)
    baseline_number = _as_number(baseline)
    if current_number is None or baseline_number is None:
        return
    if current_number < baseline_number:
        regressions.append(
            {
                "type": "baseline_regression",
                "metric": metric,
                "baseline": baseline,
                "current": current,
                "direction": "decrease",
            }
        )


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def _compare_reason_counts(
    regressions: list[dict[str, Any]],
    current_counts: dict[str, Any],
    baseline_counts: dict[str, Any],
) -> None:
    for reason in sorted(set(current_counts) | set(baseline_counts)):
        _append_increase_regression(
            regressions,
            f"summary.table_fallback_reason_counts.{reason}",
            current_counts.get(reason, 0),
            baseline_counts.get(reason, 0),
        )


def apply_quality_gate(
    payload: dict[str, Any],
    *,
    baseline_report: dict[str, Any] | None = None,
    baseline_report_path: Path | None = None,
    max_partial_rate: float | None = None,
    max_low_quality_table_rate: float | None = None,
    min_pages_per_second: float | None = None,
) -> dict[str, Any]:
    """Add deterministic quality gate diagnostics to a corpus evaluation payload."""
    summary = payload.setdefault("summary", {})
    total_documents = int(summary.get("total_documents", 0))
    total_tables = int(summary.get("table_total", 0))
    partial_rate = _rate(int(summary.get("partial_success_count", 0)), total_documents)
    low_quality_table_rate = _rate(int(summary.get("table_low_quality_count", 0)), total_tables)
    summary["partial_success_rate"] = partial_rate
    summary["low_quality_table_rate"] = low_quality_table_rate

    thresholds = {
        "max_partial_rate": max_partial_rate,
        "max_low_quality_table_rate": max_low_quality_table_rate,
        "min_pages_per_second": min_pages_per_second,
    }
    regressions: list[dict[str, Any]] = []

    if baseline_report is not None:
        baseline_summary = baseline_report.get("summary", {})
        _append_decrease_regression(
            regressions,
            "summary.success_count",
            summary.get("success_count", 0),
            baseline_summary.get("success_count", 0),
        )
        for metric in (
            "partial_success_count",
            "failed_count",
            "skipped_count",
            "table_low_quality_count",
            "total_suppressed_lines",
            "pdf_open_count",
            "text_line_extract_count",
        ):
            _append_increase_regression(
                regressions,
                f"summary.{metric}",
                summary.get(metric, 0),
                baseline_summary.get(metric, 0),
            )
        _append_decrease_regression(
            regressions,
            "summary.pages_per_second_min",
            summary.get("pages_per_second_min"),
            baseline_summary.get("pages_per_second_min"),
        )
        _append_decrease_regression(
            regressions,
            "summary.pages_per_second_mean",
            summary.get("pages_per_second_mean"),
            baseline_summary.get("pages_per_second_mean"),
        )
        _compare_reason_counts(
            regressions,
            summary.get("table_fallback_reason_counts", {}),
            baseline_summary.get("table_fallback_reason_counts", {}),
        )

    if max_partial_rate is not None and partial_rate > max_partial_rate:
        regressions.append(
            {
                "type": "threshold_failure",
                "metric": "summary.partial_success_rate",
                "limit": max_partial_rate,
                "current": partial_rate,
            }
        )
    if max_low_quality_table_rate is not None and low_quality_table_rate > max_low_quality_table_rate:
        regressions.append(
            {
                "type": "threshold_failure",
                "metric": "summary.low_quality_table_rate",
                "limit": max_low_quality_table_rate,
                "current": low_quality_table_rate,
            }
        )
    pages_per_second_min = _as_number(summary.get("pages_per_second_min"))
    if min_pages_per_second is not None and pages_per_second_min is not None and pages_per_second_min < min_pages_per_second:
        regressions.append(
            {
                "type": "threshold_failure",
                "metric": "summary.pages_per_second_min",
                "limit": min_pages_per_second,
                "current": pages_per_second_min,
            }
        )

    payload["baseline_report"] = str(baseline_report_path) if baseline_report_path else None
    payload["thresholds"] = thresholds
    payload["regressions"] = regressions
    payload["passed_quality_gate"] = len(regressions) == 0
    return payload


def run_eval(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    pdf_paths = sorted(path for path in input_dir.glob("*.pdf") if path.is_file())
    output_dir.mkdir(parents=True, exist_ok=True)
    documents: list[dict[str, Any]] = []
    summary = {
        "total_documents": len(pdf_paths),
        "success_count": 0,
        "partial_success_count": 0,
        "failed_count": 0,
        "skipped_count": 0,
        "table_fallback_reason_counts": {},
        "total_suppressed_lines": 0,
        "table_low_quality_count": 0,
        "table_total": 0,
        "pages_per_second_values": [],
        "pdf_open_count": 0,
        "text_line_extract_count": 0,
    }

    for pdf_path in pdf_paths:
        document_output = output_dir / pdf_path.stem
        result = run_conversion(
            Config(
                input_pdf=pdf_path,
                output_dir=document_output,
                keep_page_markers=True,
                rag_table_output=RagTableOutputMode.BOTH,
            )
        )
        report_path = document_output / "report.json"
        report = _read_json(report_path) if report_path.exists() else {}
        report_summary = report.get("summary", {})
        status = getattr(result.status, "value", str(result.status))
        if status == "success":
            summary["success_count"] += 1
        elif status == "partial_success":
            summary["partial_success_count"] += 1
        else:
            summary["failed_count"] += 1
        _merge_counts(summary["table_fallback_reason_counts"], report_summary.get("table_fallback_reason_counts", {}))
        summary["total_suppressed_lines"] += int(report_summary.get("total_suppressed_lines", 0))
        summary["table_low_quality_count"] += int(report_summary.get("table_low_quality_count", 0))
        summary["table_total"] += int(report_summary.get("table_total", 0))
        summary["pdf_open_count"] += int(report_summary.get("pdf_open_count", 0))
        summary["text_line_extract_count"] += int(report_summary.get("text_line_extract_count", 0))
        pages_per_second = report_summary.get("pages_per_second")
        if isinstance(pages_per_second, (int, float)):
            summary["pages_per_second_values"].append(float(pages_per_second))
        documents.append(
            {
                "input_pdf": str(pdf_path),
                "output_dir": str(document_output),
                "status": status,
                "exit_code": result.exit_code,
                "warning_count": len(report.get("warnings", [])),
                "table_fallback_count": int(report_summary.get("table_fallback_count", 0)),
                "table_low_quality_count": int(report_summary.get("table_low_quality_count", 0)),
                "text_line_extract_count": int(report_summary.get("text_line_extract_count", 0)),
                "pages_per_second": pages_per_second,
                "pdf_open_count": int(report_summary.get("pdf_open_count", 0)),
            }
        )

    values = summary.pop("pages_per_second_values")
    summary["pages_per_second_min"] = min(values) if values else None
    summary["pages_per_second_mean"] = round(sum(values) / len(values), 4) if values else None
    return {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "documents": documents,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local PDF corpus evaluation.")
    parser.add_argument("--input-dir", default="pdf", help="Directory containing local PDF files.")
    parser.add_argument("--output-dir", default="pdf/eval_output", help="Directory for evaluation outputs.")
    parser.add_argument("--baseline-report", type=Path, help="Previous corpus_eval_report.json to compare against.")
    parser.add_argument("--fail-on-regression", action="store_true", help="Return non-zero when the quality gate fails.")
    parser.add_argument("--max-partial-rate", type=float, help="Maximum allowed partial_success_count / total_documents.")
    parser.add_argument(
        "--max-low-quality-table-rate",
        type=float,
        help="Maximum allowed table_low_quality_count / table_total.",
    )
    parser.add_argument("--min-pages-per-second", type=float, help="Minimum allowed pages/sec for the slowest document.")
    args = parser.parse_args()

    payload = run_eval(Path(args.input_dir), Path(args.output_dir))
    baseline_report = _read_json(args.baseline_report) if args.baseline_report else None
    payload = apply_quality_gate(
        payload,
        baseline_report=baseline_report,
        baseline_report_path=args.baseline_report,
        max_partial_rate=args.max_partial_rate,
        max_low_quality_table_rate=args.max_low_quality_table_rate,
        min_pages_per_second=args.min_pages_per_second,
    )
    report_path = Path(args.output_dir) / "corpus_eval_report.json"
    write_json(report_path, payload)
    print(f"Wrote {report_path}")
    if args.fail_on_regression and not payload["passed_quality_gate"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
