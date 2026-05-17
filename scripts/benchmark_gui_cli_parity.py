#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import zlib
from pathlib import Path
from typing import Any

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, NumberObject, StreamObject

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pdf2md.gui_runner import GuiConversionOptions, GuiConversionRequest, run_gui_conversion
from pdf2md.utils.io import write_json
from scripts.run_gui_cli_parity import PARITY_ARTIFACTS, compare_artifacts


BENCHMARK_REPORT = "gui_cli_benchmark_report.json"
DEFAULT_PAGE_COUNT = 3


def write_benchmark_fixture(path: Path, *, page_count: int = DEFAULT_PAGE_COUNT) -> None:
    """Write a deterministic multi-page PDF fixture for CLI/GUI benchmark checks."""
    if page_count < 1:
        raise ValueError("page_count must be greater than or equal to 1.")
    path.parent.mkdir(parents=True, exist_ok=True)
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
        text = (
            "BT /F1 12 Tf 72 760 Td "
            f"(Q76 GUI CLI benchmark fixture page {page_number} shall preserve text.) Tj ET"
        )
        content = StreamObject()
        content._data = zlib.compress(text.encode("utf-8"))  # noqa: SLF001
        content[NameObject("/Filter")] = NameObject("/FlateDecode")
        content[NameObject("/Length")] = NumberObject(len(content._data))  # noqa: SLF001
        page[NameObject("/Contents")] = writer._add_object(content)  # noqa: SLF001
    with path.open("wb") as handle:
        writer.write(handle)


def apply_benchmark_policy(
    *,
    cli_elapsed_ms: int,
    gui_elapsed_ms: int,
    max_gui_duration_ratio: float | None = None,
    fail_on_regression: bool = False,
) -> dict[str, Any]:
    """Return advisory/fail performance policy results without requiring a baseline file."""
    ratio = round(gui_elapsed_ms / cli_elapsed_ms, 4) if cli_elapsed_ms > 0 else None
    threshold_status = "not_configured"
    regressions: list[dict[str, Any]] = []
    if max_gui_duration_ratio is not None and ratio is not None:
        threshold_status = "passed"
        if ratio > max_gui_duration_ratio:
            threshold_status = "failed" if fail_on_regression else "advisory"
            regressions.append(
                {
                    "metric": "gui_duration_ratio",
                    "cli_elapsed_ms": cli_elapsed_ms,
                    "gui_elapsed_ms": gui_elapsed_ms,
                    "actual": ratio,
                    "max_allowed": max_gui_duration_ratio,
                    "severity": threshold_status,
                }
            )
    return {
        "gui_duration_ratio": ratio,
        "duration_delta_ms": gui_elapsed_ms - cli_elapsed_ms,
        "max_gui_duration_ratio": max_gui_duration_ratio,
        "threshold_status": threshold_status,
        "fail_on_regression": fail_on_regression,
        "regressions": regressions,
        "passed": threshold_status != "failed",
    }


def run_benchmark(
    *,
    output_dir: Path,
    page_count: int = DEFAULT_PAGE_COUNT,
    max_gui_duration_ratio: float | None = None,
    fail_on_regression: bool = False,
) -> dict[str, Any]:
    """Run CLI and GUI headless conversions and write a local-only benchmark report."""
    fixture_path = output_dir / "fixture" / "q76_gui_cli_benchmark.pdf"
    cli_output_dir = output_dir / "cli"
    gui_output_dir = output_dir / "gui"
    report_path = output_dir / BENCHMARK_REPORT
    write_benchmark_fixture(fixture_path, page_count=page_count)
    page_range = "1" if page_count == 1 else f"1-{page_count}"
    cli_command = [
        sys.executable,
        "-m",
        "pdf2md",
        str(fixture_path),
        "-o",
        str(cli_output_dir),
        "--pages",
        page_range,
        "--keep-page-markers",
    ]

    cli_started = time.perf_counter()
    completed = subprocess.run(cli_command, check=False, capture_output=True, text=True)
    cli_elapsed_ms = _elapsed_ms(cli_started)

    gui_summary = None
    gui_elapsed_ms = 0
    if completed.returncode == 0:
        gui_started = time.perf_counter()
        gui_summary = run_gui_conversion(
            GuiConversionRequest(
                input_mode="file",
                input_path=fixture_path,
                output_dir=gui_output_dir,
                options=GuiConversionOptions(pages=page_range, keep_page_markers=True),
            )
        )
        gui_elapsed_ms = _elapsed_ms(gui_started)

    comparison = (
        compare_artifacts(cli_output_dir, gui_output_dir, artifact_names=PARITY_ARTIFACTS)
        if completed.returncode == 0 and gui_summary is not None
        else {
            "artifacts": [],
            "summary": {"checked_count": 0, "matched_count": 0, "mismatched_count": 0},
            "passed": False,
        }
    )
    performance = apply_benchmark_policy(
        cli_elapsed_ms=cli_elapsed_ms,
        gui_elapsed_ms=gui_elapsed_ms,
        max_gui_duration_ratio=max_gui_duration_ratio,
        fail_on_regression=fail_on_regression,
    )
    passed = (
        completed.returncode == 0
        and gui_summary is not None
        and gui_summary.exit_code == 0
        and comparison["passed"]
        and performance["passed"]
    )
    payload = {
        "schema_version": "1.0",
        "kind": "gui_cli_benchmark_report",
        "local_only": True,
        "status": "passed" if passed else "failed",
        "passed": passed,
        "output_dir": str(output_dir),
        "fixture_label": fixture_path.name,
        "page_count": page_count,
        "runs": [
            {
                "runner": "cli",
                "command": cli_command,
                "exit_code": completed.returncode,
                "elapsed_ms": cli_elapsed_ms,
                "pages_per_second": _pages_per_second(page_count, cli_elapsed_ms),
                "stdout_tail": _tail(completed.stdout or ""),
                "stderr_tail": _tail(completed.stderr or ""),
            },
            {
                "runner": "gui_headless",
                "exit_code": gui_summary.exit_code if gui_summary is not None else None,
                "document_count": len(gui_summary.documents) if gui_summary is not None else 0,
                "elapsed_ms": gui_elapsed_ms,
                "pages_per_second": _pages_per_second(page_count, gui_elapsed_ms),
            },
        ],
        "comparison": comparison,
        "performance": performance,
    }
    write_json(report_path, payload)
    return payload


def _elapsed_ms(started: float) -> int:
    return max(int((time.perf_counter() - started) * 1000), 0)


def _pages_per_second(page_count: int, elapsed_ms: int) -> float | None:
    if elapsed_ms <= 0:
        return None
    return round(page_count / (elapsed_ms / 1000), 4)


def _tail(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local-only CLI/GUI headless benchmark.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--page-count", type=int, default=DEFAULT_PAGE_COUNT)
    parser.add_argument("--max-gui-duration-ratio", type=float)
    parser.add_argument("--fail-on-regression", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        payload = run_benchmark(
            output_dir=args.output_dir,
            page_count=args.page_count,
            max_gui_duration_ratio=args.max_gui_duration_ratio,
            fail_on_regression=args.fail_on_regression,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"Wrote {args.output_dir / BENCHMARK_REPORT}")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
