#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pdf2md.config import SUPPORTED_FIGURE_DESCRIPTION_BACKENDS
from pdf2md.utils.io import write_text

try:
    from scripts.benchmark_docling_comparison import (
        COMPARISON_FILENAME,
        REPORT_FILENAME,
        run_docling_comparison,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from benchmark_docling_comparison import (  # type: ignore[no-redef]
        COMPARISON_FILENAME,
        REPORT_FILENAME,
        run_docling_comparison,
    )


DEFAULT_DOCUMENT_LABEL = "nvme-nvm-command-set-rev-1.2-2025-08-01"
OFFICIAL_SOURCE_URL = (
    "https://nvmexpress.org/wp-content/uploads/"
    "NVM-Express-NVM-Command-Set-Specification-Revision-1.2-2025.08.01-Ratified.pdf"
)
EXPECTED_SPEC_TITLE = "NVM Express NVM Command Set Specification"
EXPECTED_REVISION = "1.2"
EXPECTED_RELEASE_DATE = "2025-08-01"
SCORECARD_FILENAME = "latest_nvme_command_set_scorecard.md"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _tool_run(report: dict[str, Any], tool: str) -> dict[str, Any]:
    for run in report.get("runs", []):
        if isinstance(run, dict) and run.get("tool") == tool:
            return run
    return {}


def _metrics(run: dict[str, Any]) -> dict[str, Any]:
    value = run.get("metrics")
    return value if isinstance(value, dict) else {}


def _bool_status(value: Any) -> str:
    if value is True:
        return "pass"
    if value is False:
        return "fail"
    return "n/a"


def _current_tool_advisory_score(current_run: dict[str, Any]) -> int:
    metrics = _metrics(current_run)
    score = 100
    status = str(current_run.get("status") or "")
    if status == "failed":
        score -= 40
    elif status == "partial_success":
        score -= 5
    warning_count = int(metrics.get("actionable_warning_count") or metrics.get("warning_count") or 0)
    score -= min(6, warning_count)
    for key in ("artifact_integrity_passed", "index_contract_passed", "provenance_integrity_passed"):
        if metrics.get(key) is not True:
            score -= 5
    if int(metrics.get("retrieval_chunk_record_count") or 0) == 0:
        score -= 8
    if int(metrics.get("domain_unit_record_count") or 0) == 0:
        score -= 6
    if int(metrics.get("figure_text_chunk_record_count") or 0) == 0:
        score -= 4
    if int(metrics.get("table_total") or 0) == 0:
        score -= 4
    return max(0, score)


def render_latest_nvme_scorecard(
    *,
    report: dict[str, Any],
    comparison: dict[str, Any],
    document_label: str,
    official_source_url: str,
    pages: str | None,
    figure_semantics_mode: str,
) -> str:
    current_run = _tool_run(report, "pdf2md")
    docling_run = _tool_run(report, "docling")
    current_metrics = _metrics(current_run)
    docling_metrics = _metrics(docling_run)
    stage_durations = current_metrics.get("stage_durations_ms")
    stage_durations_json = json.dumps(stage_durations, ensure_ascii=False, sort_keys=True) if stage_durations else "{}"
    score = _current_tool_advisory_score(current_run)

    lines = [
        "# Latest NVMe Command Set Evaluation Scorecard",
        "",
        f"- Document label: `{document_label}`",
        f"- Expected spec: `{EXPECTED_SPEC_TITLE} Revision {EXPECTED_REVISION} ({EXPECTED_RELEASE_DATE})`",
        f"- Official source: <{official_source_url}>",
        f"- Page range: `{pages or 'all'}`",
        f"- Current-tool profile: `technical_spec_rag + domain_adapter=nvme + image_mode=placeholder`",
        f"- Figure semantics mode: `{figure_semantics_mode}`",
        "- Raw PDF text, raw Markdown body, image bytes, and customer paths are not embedded in this scorecard.",
        "",
        "## Summary",
        "",
        "| Tool | Status | Duration ms | Pages/sec |",
        "| --- | --- | ---: | ---: |",
        "| pdf2md | {status} | {duration} | {pps} |".format(
            status=current_run.get("status", ""),
            duration=current_run.get("duration_ms", 0),
            pps=current_run.get("pages_per_second") or "",
        ),
        "| docling | {status} | {duration} | {pps} |".format(
            status=docling_run.get("status", ""),
            duration=docling_run.get("duration_ms", 0),
            pps=docling_run.get("pages_per_second") or "",
        ),
        "",
        f"Current-tool advisory score: **{score}/100**",
        "",
        "## Current Tool Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| processed_pages | {current_metrics.get('processed_pages', 0)} |",
        f"| warning_count | {current_metrics.get('warning_count', 0)} |",
        f"| actionable_warning_count | {current_metrics.get('actionable_warning_count', 0)} |",
        f"| table_total | {current_metrics.get('table_total', 0)} |",
        f"| table_gfm_count | {current_metrics.get('table_gfm_count', 0)} |",
        f"| table_html_count | {current_metrics.get('table_html_count', 0)} |",
        f"| table_low_quality_count | {current_metrics.get('table_low_quality_count', 0)} |",
        f"| retrieval_chunk_record_count | {current_metrics.get('retrieval_chunk_record_count', 0)} |",
        f"| domain_unit_record_count | {current_metrics.get('domain_unit_record_count', 0)} |",
        f"| figure_rag_record_count | {current_metrics.get('figure_rag_record_count', 0)} |",
        f"| figure_text_chunk_record_count | {current_metrics.get('figure_text_chunk_record_count', 0)} |",
        f"| figure_description_chunk_record_count | {current_metrics.get('figure_description_chunk_record_count', 0)} |",
        f"| figure_structure_chunk_record_count | {current_metrics.get('figure_structure_chunk_record_count', 0)} |",
        f"| artifact_integrity | {_bool_status(current_metrics.get('artifact_integrity_passed'))} |",
        f"| index_contract | {_bool_status(current_metrics.get('index_contract_passed'))} |",
        f"| provenance_integrity | {_bool_status(current_metrics.get('provenance_integrity_passed'))} |",
        "",
        "## Stage Durations",
        "",
        f"`{stage_durations_json}`",
        "",
        "## Docling Probe",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| docling_available | `{report.get('summary', {}).get('docling_available')}` |",
        f"| table_like_node_count | `{docling_metrics.get('table_like_node_count')}` |",
        f"| figure_like_node_count | `{docling_metrics.get('figure_like_node_count')}` |",
        f"| backend_availability | `{json.dumps(docling_metrics.get('backend_availability', {}), sort_keys=True)}` |",
        "",
        "## Sanitization Contract",
        "",
        f"- benchmark raw_content_included: `{report.get('raw_content_included')}`",
        f"- benchmark image_bytes_included: `{report.get('image_bytes_included')}`",
        f"- benchmark customer_paths_included: `{report.get('customer_paths_included')}`",
        f"- comparison raw_content_included: `{comparison.get('raw_content_included')}`",
        f"- comparison image_bytes_included: `{comparison.get('image_bytes_included')}`",
        f"- comparison customer_paths_included: `{comparison.get('customer_paths_included')}`",
    ]
    findings = report.get("findings", [])
    if findings:
        lines.extend(["", "## Findings"])
        for finding in findings:
            lines.append(f"- `{finding.get('severity')}` `{finding.get('code')}`: {finding.get('message')}")
    return "\n".join(lines) + "\n"


def run_latest_nvme_command_set_eval(
    *,
    input_pdf: Path,
    output_dir: Path,
    pages: str | None = None,
    document_label: str = DEFAULT_DOCUMENT_LABEL,
    official_source_url: str = OFFICIAL_SOURCE_URL,
    figure_semantics_mode: str = "visual",
    figure_description_backend: str = "local-vlm",
) -> dict[str, Any]:
    """Run the latest NVMe Command Set current-tool/Docling comparison pack."""
    output_dir.mkdir(parents=True, exist_ok=True)
    include_visual_semantics = figure_semantics_mode == "visual"
    report = run_docling_comparison(
        input_pdf=input_pdf,
        output_dir=output_dir,
        document_label=document_label,
        pages=pages,
        rag_profile="technical_spec_rag",
        domain_adapter="nvme",
        image_mode="placeholder",
        rag_figure_text_chunks=True,
        figure_region_ocr=include_visual_semantics,
        rag_generated_figure_descriptions=include_visual_semantics,
        figure_description_backend=figure_description_backend,
        figure_structure_extraction=include_visual_semantics,
    )
    comparison = _read_json(output_dir / COMPARISON_FILENAME)
    scorecard = render_latest_nvme_scorecard(
        report=report,
        comparison=comparison,
        document_label=document_label,
        official_source_url=official_source_url,
        pages=pages,
        figure_semantics_mode=figure_semantics_mode,
    )
    write_text(output_dir / SCORECARD_FILENAME, scorecard)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the current-tool/Docling comparison pack for the latest NVMe NVM Command Set spec."
    )
    parser.add_argument("--input-pdf", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pages", default=None)
    parser.add_argument("--document-label", default=DEFAULT_DOCUMENT_LABEL)
    parser.add_argument("--official-source-url", default=OFFICIAL_SOURCE_URL)
    parser.add_argument(
        "--figure-semantics-mode",
        choices=("assetless", "visual"),
        default="visual",
        help="assetless keeps figure_text chunks only; visual also enables Q107 description/structure sidecars.",
    )
    parser.add_argument(
        "--figure-description-backend",
        choices=SUPPORTED_FIGURE_DESCRIPTION_BACKENDS,
        default="local-vlm",
    )
    parser.add_argument("--fail-on-current-tool-failure", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = run_latest_nvme_command_set_eval(
        input_pdf=args.input_pdf,
        output_dir=args.output_dir,
        pages=args.pages,
        document_label=args.document_label,
        official_source_url=args.official_source_url,
        figure_semantics_mode=args.figure_semantics_mode,
        figure_description_backend=args.figure_description_backend,
    )
    print(f"Wrote {args.output_dir / REPORT_FILENAME}")
    print(f"Wrote {args.output_dir / COMPARISON_FILENAME}")
    print(f"Wrote {args.output_dir / SCORECARD_FILENAME}")
    if args.fail_on_current_tool_failure and report.get("summary", {}).get("current_tool_status") == "failed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
