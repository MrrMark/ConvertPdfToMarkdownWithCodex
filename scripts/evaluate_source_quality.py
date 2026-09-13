"""Run the local source-quality gate without changing conversion artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pypdf.errors import PdfReadError

from pdf2md.quality_eval import evaluate_source_quality


def main(argv: list[str] | None = None) -> int:
    """Return 0 for a stable baseline, 1 for regression, 2 for invalid inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--input-pdf", type=Path, required=True)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    # Never let a report overwrite a PDF, truth or an existing conversion artifact.
    report_path = args.report.resolve()
    if report_path in {args.input_pdf.resolve(), args.truth.resolve()} or report_path.is_relative_to(args.output_dir.resolve()):
        print("Report must be outside the conversion output and separate from input/truth.", file=sys.stderr)
        return 2
    try:
        report = evaluate_source_quality(output_dir=args.output_dir, input_pdf=args.input_pdf, truth_path=args.truth)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report.model_dump(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, PdfReadError) as exc:
        print(f"Source quality evaluation failed: {exc}", file=sys.stderr)
        return 2
    print(f"quality_passed={report.quality_passed} gate_passed={report.gate_passed}")
    return 0 if report.gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
