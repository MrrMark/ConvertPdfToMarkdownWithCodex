#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pdf2md.utils.io import write_json


DEFAULT_GATES = ("ocr", "corpus", "benchmark", "schema", "packaging")


@dataclass(frozen=True)
class ReleaseGateConfig:
    output_dir: Path
    gates: list[str]
    ocr_lang: str = "eng"
    corpus_input_dir: Path = Path("pdf")
    corpus_baseline_report: Path | None = None
    benchmark_baseline_report: Path | None = None
    benchmark_page_counts: str = "10,50,100"
    max_partial_rate: float | None = None
    max_low_quality_table_rate: float | None = None
    corpus_min_pages_per_second: float | None = None
    max_duration_regression: float = 0.2
    max_memory_regression: float = 0.2
    benchmark_min_pages_per_second: float | None = None


def _split_gates(raw_gates: str) -> list[str]:
    gates: list[str] = []
    seen: set[str] = set()
    for raw_gate in raw_gates.split(","):
        gate = raw_gate.strip()
        if not gate or gate in seen:
            continue
        if gate not in DEFAULT_GATES:
            raise ValueError(f"Unknown release gate: {gate}")
        gates.append(gate)
        seen.add(gate)
    return gates


def _tail(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _run_command(
    *,
    gate: str,
    command: list[str],
    report_path: Path | None = None,
    cwd: Path = Path("."),
) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "gate": gate,
        "command": command,
        "exit_code": completed.returncode,
        "status": "passed" if completed.returncode == 0 else "failed",
        "report_path": str(report_path) if report_path is not None else None,
        "stdout_tail": _tail(completed.stdout or ""),
        "stderr_tail": _tail(completed.stderr or ""),
    }


def _write_ocr_report(record: dict[str, Any], report_path: Path) -> None:
    try:
        payload = json.loads(record.get("stdout_tail") or "{}")
    except json.JSONDecodeError:
        payload = {
            "ready": False,
            "raw_stdout": record.get("stdout_tail", ""),
            "raw_stderr": record.get("stderr_tail", ""),
        }
    write_json(report_path, payload)


def _ocr_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    report_path = config.output_dir / "ocr_runtime_report.json"
    record = _run_command(
        gate="ocr",
        command=[
            sys.executable,
            "scripts/check_ocr_runtime.py",
            "--ocr-lang",
            config.ocr_lang,
            "--json",
        ],
        report_path=report_path,
    )
    _write_ocr_report(record, report_path)
    return [record]


def _corpus_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    output_dir = config.output_dir / "corpus"
    report_path = output_dir / "corpus_eval_report.json"
    command = [
        sys.executable,
        "scripts/run_corpus_eval.py",
        "--input-dir",
        str(config.corpus_input_dir),
        "--output-dir",
        str(output_dir),
        "--fail-on-regression",
    ]
    if config.corpus_baseline_report is not None:
        command.extend(["--baseline-report", str(config.corpus_baseline_report)])
    if config.max_partial_rate is not None:
        command.extend(["--max-partial-rate", str(config.max_partial_rate)])
    if config.max_low_quality_table_rate is not None:
        command.extend(["--max-low-quality-table-rate", str(config.max_low_quality_table_rate)])
    if config.corpus_min_pages_per_second is not None:
        command.extend(["--min-pages-per-second", str(config.corpus_min_pages_per_second)])
    return [_run_command(gate="corpus", command=command, report_path=report_path)]


def _benchmark_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    output_dir = config.output_dir / "benchmark"
    report_path = output_dir / "benchmark_report.json"
    command = [
        sys.executable,
        "scripts/benchmark_conversion.py",
        "--output-dir",
        str(output_dir),
        "--page-counts",
        config.benchmark_page_counts,
        "--fail-on-regression",
        "--max-duration-regression",
        str(config.max_duration_regression),
        "--max-memory-regression",
        str(config.max_memory_regression),
    ]
    if config.benchmark_baseline_report is not None:
        command.extend(["--baseline-report", str(config.benchmark_baseline_report)])
    if config.benchmark_min_pages_per_second is not None:
        command.extend(["--min-pages-per-second", str(config.benchmark_min_pages_per_second)])
    return [_run_command(gate="benchmark", command=command, report_path=report_path)]


def _schema_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    return [
        _run_command(
            gate="schema",
            command=[sys.executable, "scripts/export_output_schema.py", "--check"],
            report_path=Path("docs/schema"),
        )
    ]


def _packaging_gate(config: ReleaseGateConfig) -> list[dict[str, Any]]:
    dist_dir = config.output_dir / "dist"
    return [
        _run_command(
            gate="packaging:build",
            command=[
                sys.executable,
                "-m",
                "pip",
                "wheel",
                ".",
                "--no-deps",
                "--no-build-isolation",
                "-w",
                str(dist_dir),
            ],
            report_path=dist_dir,
        ),
        _run_command(
            gate="packaging:module-help",
            command=[sys.executable, "-m", "pdf2md", "--help"],
            report_path=None,
        ),
    ]


def run_release_gates(config: ReleaseGateConfig) -> dict[str, Any]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for gate in config.gates:
        if gate == "ocr":
            records.extend(_ocr_gate(config))
        elif gate == "corpus":
            records.extend(_corpus_gate(config))
        elif gate == "benchmark":
            records.extend(_benchmark_gate(config))
        elif gate == "schema":
            records.extend(_schema_gate(config))
        elif gate == "packaging":
            records.extend(_packaging_gate(config))
    failed = [record for record in records if record["status"] != "passed"]
    payload = {
        "schema_version": "1.0",
        "output_dir": str(config.output_dir),
        "gates_requested": config.gates,
        "gates": records,
        "summary": {
            "total_gate_commands": len(records),
            "passed_count": len(records) - len(failed),
            "failed_count": len(failed),
        },
        "passed_release_gate": not failed,
    }
    write_json(config.output_dir / "release_gate_report.json", payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run pdf2md release gates and write a unified report.")
    parser.add_argument("--output-dir", type=Path, default=Path("release_gate_output"))
    parser.add_argument(
        "--gates",
        default=",".join(DEFAULT_GATES),
        help="Comma-separated gates: ocr,corpus,benchmark,schema,packaging.",
    )
    parser.add_argument("--ocr-lang", default="eng")
    parser.add_argument("--corpus-input-dir", type=Path, default=Path("pdf"))
    parser.add_argument("--corpus-baseline-report", type=Path)
    parser.add_argument("--benchmark-baseline-report", type=Path)
    parser.add_argument("--benchmark-page-counts", default="10,50,100")
    parser.add_argument("--max-partial-rate", type=float)
    parser.add_argument("--max-low-quality-table-rate", type=float)
    parser.add_argument("--corpus-min-pages-per-second", type=float)
    parser.add_argument("--max-duration-regression", type=float, default=0.2)
    parser.add_argument("--max-memory-regression", type=float, default=0.2)
    parser.add_argument("--benchmark-min-pages-per-second", type=float)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        gates = _split_gates(args.gates)
    except ValueError as exc:
        print(str(exc))
        return 2
    payload = run_release_gates(
        ReleaseGateConfig(
            output_dir=args.output_dir,
            gates=gates,
            ocr_lang=args.ocr_lang,
            corpus_input_dir=args.corpus_input_dir,
            corpus_baseline_report=args.corpus_baseline_report,
            benchmark_baseline_report=args.benchmark_baseline_report,
            benchmark_page_counts=args.benchmark_page_counts,
            max_partial_rate=args.max_partial_rate,
            max_low_quality_table_rate=args.max_low_quality_table_rate,
            corpus_min_pages_per_second=args.corpus_min_pages_per_second,
            max_duration_regression=args.max_duration_regression,
            max_memory_regression=args.max_memory_regression,
            benchmark_min_pages_per_second=args.benchmark_min_pages_per_second,
        )
    )
    print(f"Wrote {args.output_dir / 'release_gate_report.json'}")
    return 0 if payload["passed_release_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
