"""Run the pinned Q157 corpus sequentially and retain local source-token smoke evidence."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.benchmark_fair_comparison import file_hash, run_benchmark

CASES = {
    "front_matter": ("front_matter_p001_005.pdf", "9c5ef8a735d30ad7017d88658dc2454e4b47b1da173bad53da38fcdb450f46e5"),
    "controller_tables": ("controller_tables_p696_700.pdf", "5a6aa491db9dbcb46b21a1bcf901cc03e1ffd927dc57a6011d5e904551992185"),
    "sgl_figures_tables": ("sgl_figures_tables_p181_184.pdf", "1fefe74693a264aa1134ed217d40d4630cb0100347f471613307cd397dca0749"),
}


def token_smoke(markdown: str, truth: dict) -> dict:
    """Check selected source tokens document-wide; this does not score structure or order."""
    text = re.sub(r"\s+", " ", html.unescape(markdown))
    checks = []
    for check in truth["checks"]:
        tokens = check.get("tokens")
        if tokens:
            checks.append({
                "check_id": check["check_id"],
                "expected_token_count": len(tokens),
                "found_token_count": sum(re.sub(r"\s+", " ", token) in text for token in tokens),
            })
    return {
        "scope": "selected_tokens_document_wide_only",
        "page_cell_order_and_geometry": "not_evaluated",
        "checks": checks,
        "all_selected_tokens_present": all(c["found_token_count"] == c["expected_token_count"] for c in checks),
    }


def collect_case(path: Path, truth: dict) -> dict:
    """Attach source-token evidence separately from timing and feature support."""
    report = json.loads((path / "fair_benchmark_report.json").read_text())
    if report["source_sha256"] != truth["input_sha256"]:
        raise ValueError("source truth hash mismatch")
    for engine in report["engines"]:
        markdown = path / engine["engine"] / "cold/document.md"
        if engine["status"] == "success" and markdown.is_file():
            engine["source_token_smoke"] = token_smoke(markdown.read_text(), truth)
    return report


def public_summary(summary: dict) -> dict:
    """Keep timings and identities without source text, truth tokens or local paths."""
    cases = {}
    keys = ("engine", "status", "version_check", "packages", "models", "source_code_identity",
            "runtime", "import_seconds", "setup_seconds", "process_wall_seconds", "peak_rss",
            "summary", "unavailable_reason", "error", "input_identity_verified", "source_token_smoke")
    for name, case in summary["cases"].items():
        engines = []
        for engine in case["engines"]:
            record = {key: engine[key] for key in keys if key in engine}
            record["samples"] = [{key: run[key] for key in
                                  ("phase", "index", "status", "convert_export_write_seconds", "counts", "error_type")
                                  if key in run} for run in engine.get("runs", [])]
            engines.append(record)
        cases[name] = {key: case[key] for key in
                       ("source_sha256", "slice_sha256", "source_pages", "method", "timing_samples_complete")}
        cases[name]["engines"] = engines
    return {"purpose": summary["purpose"], "quality_scope": summary["quality_scope"], "cases": cases}


def main() -> int:
    """Run new experiments, or collect completed reports without repeating timings."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, default=ROOT / "output/docling_nvme_base_slices")
    parser.add_argument("--truth-dir", type=Path, default=ROOT / "output/q155_validation")
    parser.add_argument("--env-dir", type=Path, default=ROOT / "output/q157_envs")
    parser.add_argument("--models", type=Path, default=ROOT / "output/q157_models/docling")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--public-report", type=Path)
    args = parser.parse_args()
    # Validate the entire corpus before any expensive conversion.
    for filename, expected in CASES.values():
        if file_hash(args.corpus_dir / filename) != expected:
            raise ValueError(f"Unexpected corpus bytes: {filename}")
    if not args.collect_only:
        args.output_dir.mkdir(parents=True, exist_ok=False)
        for engine in ("native", "docling", "marker", "pymupdf"):
            python = sys.executable if engine == "native" else str(args.env_dir / engine / "bin/python")
            frozen = subprocess.run([python, "-m", "pip", "freeze", "--all"], capture_output=True, text=True, check=True)
            (args.output_dir / f"{engine}.freeze.txt").write_text(frozen.stdout, encoding="utf-8")
        for case, (filename, _) in CASES.items():
            run_benchmark(argparse.Namespace(
                input_pdf=args.corpus_dir / filename, output_dir=args.output_dir / case, pages=None,
                engines=["native", "docling", "pymupdf", "marker"],
                native_profile="technical_spec_rag_visual", domain_adapter="none", threads=4,
                fixed_external_versions=True, timeout=1800, docling_models=args.models,
                **{f"{engine}_python": str(args.env_dir / engine / "bin/python") for engine in ("docling", "pymupdf", "marker")},
            ))
    summary = {
        "purpose": "q157_fixed_version_cpu_experiment",
        "quality_scope": "source_token_smoke_only; full structural and retrieval quality not measured",
        "cases": {case: collect_case(args.output_dir / case, json.loads((args.truth_dir / f"{case}.truth.json").read_text())) for case in CASES},
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if args.public_report:
        args.public_report.parent.mkdir(parents=True, exist_ok=True)
        args.public_report.write_text(json.dumps(public_summary(summary), indent=2) + "\n", encoding="utf-8")
    return 0 if all(case["timing_samples_complete"] for case in summary["cases"].values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
