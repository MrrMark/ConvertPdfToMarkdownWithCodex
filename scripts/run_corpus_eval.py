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


def run_eval(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    pdf_paths = sorted(path for path in input_dir.glob("*.pdf") if path.is_file())
    output_dir.mkdir(parents=True, exist_ok=True)
    documents: list[dict[str, Any]] = []
    summary = {
        "total_documents": len(pdf_paths),
        "success_count": 0,
        "partial_success_count": 0,
        "failed_count": 0,
        "table_fallback_reason_counts": {},
        "total_suppressed_lines": 0,
        "table_low_quality_count": 0,
        "pages_per_second_values": [],
        "pdf_open_count": 0,
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
        summary["pdf_open_count"] += int(report_summary.get("pdf_open_count", 0))
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
    args = parser.parse_args()

    payload = run_eval(Path(args.input_dir), Path(args.output_dir))
    report_path = Path(args.output_dir) / "corpus_eval_report.json"
    write_json(report_path, payload)
    print(f"Wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
