#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import time
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from pdf2md.config import Config, SUPPORTED_FIGURE_DESCRIPTION_BACKENDS
from pdf2md.models import (
    DoclingArtifactComparisonReport,
    DoclingBenchmarkReport,
    DomainAdapterMode,
    ImageMode,
    RagTableOutputMode,
)
from pdf2md.pipeline import run_conversion
from pdf2md.rag_profiles import SUPPORTED_RAG_PURPOSE_PROFILES
from pdf2md.utils.io import write_json, write_text

try:
    from scripts.validate_artifact_integrity import validate_artifact_integrity
    from scripts.validate_index_contract import validate_index_contract
    from scripts.validate_provenance_integrity import validate_provenance_integrity
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from validate_artifact_integrity import validate_artifact_integrity  # type: ignore[no-redef]
    from validate_index_contract import validate_index_contract  # type: ignore[no-redef]
    from validate_provenance_integrity import validate_provenance_integrity  # type: ignore[no-redef]


SCHEMA_VERSION = "1.0"
REPORT_FILENAME = "docling_benchmark_report.json"
COMPARISON_FILENAME = "docling_artifact_comparison.json"
SCORECARD_FILENAME = "docling_scorecard.md"
CURRENT_TOOL = "pdf2md"
DOCLING_TOOL = "docling"
OPTIONAL_BACKEND_MODULES = {
    "tesseract": "pytesseract",
    "rapidocr": "rapidocr_onnxruntime",
    "easyocr": "easyocr",
    "macos": "ocrmac",
}
SANITIZED_ARTIFACTS = (
    "document.md",
    "manifest.json",
    "report.json",
    "retrieval_chunks_rag.jsonl",
    "page_layout_rag.jsonl",
    "figures_rag.jsonl",
    "tables_rag.jsonl",
    "technical_tables_rag.jsonl",
)
LAYOUT_COMPARISON_MODES = ("off", "summary")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_sha256(path: Path) -> str:
    return _file_sha256(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _page_count(path: Path) -> int:
    try:
        return len(PdfReader(str(path)).pages)
    except Exception:
        return 0


def _artifact_hashes(output_dir: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for filename in SANITIZED_ARTIFACTS:
        path = output_dir / filename
        if path.exists():
            hashes[filename] = _file_sha256(path)
    return hashes


def _artifact_entries(tool: str, output_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for filename in SANITIZED_ARTIFACTS:
        path = output_dir / filename
        entries.append(
            {
                "tool": tool,
                "artifact": filename,
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "sha256": _file_sha256(path) if path.exists() else None,
            }
        )
    return entries


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False


def _backend_availability() -> dict[str, bool]:
    return {
        backend: _module_available(module_name)
        for backend, module_name in sorted(OPTIONAL_BACKEND_MODULES.items())
    }


def _count_key_occurrences(value: Any, tokens: tuple[str, ...]) -> int:
    count = 0
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in tokens):
                count += 1
            count += _count_key_occurrences(item, tokens)
    elif isinstance(value, list):
        for item in value:
            count += _count_key_occurrences(item, tokens)
    return count


def _current_layout_metrics(summary: dict[str, Any], mode: str) -> dict[str, Any]:
    if mode == "off":
        return {}
    return {
        "layout_comparison_mode": mode,
        "layout_table_candidate_count": summary.get("table_total", 0),
        "layout_figure_candidate_count": summary.get("figure_rag_record_count", 0),
        "layout_retrieval_chunk_count": summary.get("retrieval_chunk_record_count", 0),
    }


def _docling_layout_metrics(document_dict: dict[str, Any], mode: str) -> dict[str, Any]:
    if mode == "off":
        return {}
    return {
        "layout_comparison_mode": mode,
        "layout_top_level_key_count": len(document_dict),
        "layout_table_candidate_count": _count_key_occurrences(document_dict, ("table",)),
        "layout_figure_candidate_count": _count_key_occurrences(document_dict, ("picture", "figure", "image")),
        "layout_page_candidate_count": _count_key_occurrences(document_dict, ("page",)),
        "layout_text_container_key_count": _count_key_occurrences(
            document_dict,
            ("text", "paragraph", "section"),
        ),
    }


def _validator_status(output_dir: Path) -> dict[str, Any]:
    artifact = validate_artifact_integrity(output_dir=output_dir)
    index = validate_index_contract(output_dir=output_dir)
    provenance = validate_provenance_integrity(output_dir=output_dir)
    return {
        "artifact_integrity_passed": artifact.get("passed") is True,
        "index_contract_passed": index.get("passed") is True,
        "provenance_integrity_passed": provenance.get("passed") is True,
        "artifact_integrity_errors": artifact.get("summary", {}).get("error_count", 0),
        "index_contract_errors": index.get("summary", {}).get("error_count", 0),
        "provenance_integrity_errors": provenance.get("summary", {}).get("error_count", 0),
    }


def run_current_tool(
    *,
    input_pdf: Path,
    output_dir: Path,
    pages: str | None,
    rag_profile: str,
    domain_adapter: str,
    image_mode: str,
    rag_figure_text_chunks: bool,
    figure_region_ocr: bool,
    rag_generated_figure_descriptions: bool,
    figure_description_backend: str,
    figure_structure_extraction: bool,
    layout_comparison_mode: str,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    result = run_conversion(
        Config(
            input_pdf=input_pdf,
            output_dir=output_dir,
            pages=pages,
            image_mode=ImageMode(image_mode),
            rag_table_output=RagTableOutputMode.BOTH,
            rag_profile=rag_profile,
            domain_adapter=DomainAdapterMode(domain_adapter),
            rag_figure_text_chunks=rag_figure_text_chunks,
            figure_region_ocr=figure_region_ocr,
            rag_generated_figure_descriptions=rag_generated_figure_descriptions,
            figure_description_backend=figure_description_backend,
            figure_structure_extraction=figure_structure_extraction,
        )
    )
    duration_ms = int((time.perf_counter() - started) * 1000)
    report = _read_json(output_dir / "report.json")
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    validator_status = _validator_status(output_dir)
    metrics = {
        "exit_code": result.exit_code,
        "conversion_status": getattr(result.status, "value", str(result.status)),
        "processed_pages": summary.get("processed_pages", 0),
        "warning_count": summary.get("warning_count", 0),
        "actionable_warning_count": summary.get("actionable_warning_count", 0),
        "table_total": summary.get("table_total", 0),
        "table_html_count": summary.get("table_html_count", 0),
        "table_gfm_count": summary.get("table_gfm_count", 0),
        "table_low_quality_count": summary.get("table_low_quality_count", 0),
        "figure_rag_record_count": summary.get("figure_rag_record_count", 0),
        "figure_text_chunk_record_count": summary.get("figure_text_chunk_record_count", 0),
        "figure_region_ocr_attempted_count": summary.get("figure_region_ocr_attempted_count", 0),
        "figure_region_ocr_candidate_count": summary.get("figure_region_ocr_candidate_count", 0),
        "figure_region_ocr_promoted_label_count": summary.get("figure_region_ocr_promoted_label_count", 0),
        "figure_description_record_count": summary.get("figure_description_record_count", 0),
        "figure_description_chunk_record_count": summary.get("figure_description_chunk_record_count", 0),
        "figure_structure_record_count": summary.get("figure_structure_record_count", 0),
        "figure_structure_chunk_record_count": summary.get("figure_structure_chunk_record_count", 0),
        "retrieval_chunk_record_count": summary.get("retrieval_chunk_record_count", 0),
        "technical_table_record_count": summary.get("technical_table_record_count", 0),
        "domain_unit_record_count": summary.get("domain_unit_record_count", 0),
        "stage_durations_ms": summary.get("stage_durations_ms", {}),
        **_current_layout_metrics(summary, layout_comparison_mode),
        **validator_status,
    }
    return {
        "tool": CURRENT_TOOL,
        "status": "success" if result.exit_code == 0 else "partial_success" if result.exit_code == 2 else "failed",
        "output_dir": output_dir.name,
        "duration_ms": duration_ms,
        "pages_per_second": summary.get("pages_per_second"),
        "metrics": metrics,
        "artifact_hashes": _artifact_hashes(output_dir),
    }


def _docling_document_to_dict(document: Any) -> dict[str, Any]:
    for method_name in ("export_to_dict", "model_dump", "dict"):
        method = getattr(document, method_name, None)
        if callable(method):
            try:
                payload = method()
            except TypeError:
                continue
            if isinstance(payload, dict):
                return payload
    return {}


def run_docling_tool(
    *,
    input_pdf: Path,
    output_dir: Path,
    layout_comparison_mode: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    virtual_artifacts: list[dict[str, Any]] = []
    if not _module_available("docling"):
        advisory = "Docling is not installed in this environment; current-tool metrics were still generated."
        findings.append(
            {
                "severity": "warning",
                "code": "docling_not_installed",
                "tool": DOCLING_TOOL,
                "message": advisory,
                "details": {"install_required": True},
            }
        )
        return (
            {
                "tool": DOCLING_TOOL,
                "status": "skipped",
                "output_dir": None,
                "duration_ms": 0,
                "pages_per_second": None,
                "metrics": {"backend_availability": _backend_availability()},
                "artifact_hashes": {},
                "error_code": "docling_not_installed",
                "advisory": advisory,
            },
            findings,
            virtual_artifacts,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        module = importlib.import_module("docling.document_converter")
        converter_class = getattr(module, "DocumentConverter")
        converter = converter_class()
        started = time.perf_counter()
        result = converter.convert(str(input_pdf))
        duration_ms = int((time.perf_counter() - started) * 1000)
        document = getattr(result, "document", result)
        markdown_method = getattr(document, "export_to_markdown", None)
        markdown = markdown_method() if callable(markdown_method) else ""
        document_dict = _docling_document_to_dict(document)
        markdown_bytes = str(markdown or "").encode("utf-8")
        dict_bytes = json.dumps(document_dict, ensure_ascii=False, sort_keys=True).encode("utf-8")
        virtual_artifacts.extend(
            [
                {
                    "tool": DOCLING_TOOL,
                    "artifact": "docling_markdown",
                    "exists": bool(markdown),
                    "size_bytes": len(markdown_bytes),
                    "sha256": _sha256_bytes(markdown_bytes) if markdown else None,
                    "virtual": True,
                },
                {
                    "tool": DOCLING_TOOL,
                    "artifact": "docling_document_dict",
                    "exists": bool(document_dict),
                    "size_bytes": len(dict_bytes),
                    "sha256": _sha256_bytes(dict_bytes) if document_dict else None,
                    "virtual": True,
                },
            ]
        )
        page_count = _page_count(input_pdf)
        metrics = {
            "backend_availability": _backend_availability(),
            "markdown_char_count": len(str(markdown or "")),
            "document_dict_top_level_key_count": len(document_dict),
            "table_like_node_count": _count_key_occurrences(document_dict, ("table",)),
            "figure_like_node_count": _count_key_occurrences(document_dict, ("picture", "figure", "image")),
            **_docling_layout_metrics(document_dict, layout_comparison_mode),
        }
        return (
            {
                "tool": DOCLING_TOOL,
                "status": "success",
                "output_dir": output_dir.name,
                "duration_ms": duration_ms,
                "pages_per_second": round(page_count / (duration_ms / 1000), 4) if duration_ms > 0 and page_count else None,
                "metrics": metrics,
                "artifact_hashes": {
                    artifact["artifact"]: artifact["sha256"]
                    for artifact in virtual_artifacts
                    if artifact.get("sha256")
                },
            },
            findings,
            virtual_artifacts,
        )
    except Exception as exc:  # pragma: no cover - depends on optional external package behavior
        message = f"Docling benchmark run failed without affecting current-tool output: {type(exc).__name__}."
        findings.append(
            {
                "severity": "error",
                "code": "docling_run_failed",
                "tool": DOCLING_TOOL,
                "message": message,
                "details": {"exception_type": type(exc).__name__},
            }
        )
        return (
            {
                "tool": DOCLING_TOOL,
                "status": "failed",
                "output_dir": output_dir.name,
                "duration_ms": 0,
                "pages_per_second": None,
                "metrics": {"backend_availability": _backend_availability()},
                "artifact_hashes": {},
                "error_code": "docling_run_failed",
                "advisory": message,
            },
            findings,
            virtual_artifacts,
        )


def _numeric_metric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def build_metric_deltas(current_run: dict[str, Any], docling_run: dict[str, Any]) -> list[dict[str, Any]]:
    deltas: list[dict[str, Any]] = []
    current_metrics = current_run.get("metrics") if isinstance(current_run.get("metrics"), dict) else {}
    docling_metrics = docling_run.get("metrics") if isinstance(docling_run.get("metrics"), dict) else {}
    docling_comparable = docling_run.get("status") not in {"failed", "skipped"}
    for metric in sorted(set(current_metrics) | set(docling_metrics) | {"duration_ms", "pages_per_second"}):
        current_value = current_run.get(metric) if metric in {"duration_ms", "pages_per_second"} else current_metrics.get(metric)
        docling_value = docling_run.get(metric) if metric in {"duration_ms", "pages_per_second"} else docling_metrics.get(metric)
        current_number = _numeric_metric(current_value)
        docling_number = _numeric_metric(docling_value) if docling_comparable else None
        deltas.append(
            {
                "metric": metric,
                "current_tool": current_value,
                "docling": docling_value,
                "delta": round(docling_number - current_number, 4)
                if current_number is not None and docling_number is not None
                else None,
            }
        )
    return deltas


def build_comparison(
    *,
    document_label: str,
    source_sha256: str,
    current_run: dict[str, Any],
    docling_run: dict[str, Any],
    current_output_dir: Path,
    docling_virtual_artifacts: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    layout_comparison_mode: str,
) -> dict[str, Any]:
    current_artifacts = _artifact_entries(CURRENT_TOOL, current_output_dir)
    artifacts = current_artifacts + docling_virtual_artifacts
    metric_deltas = build_metric_deltas(current_run, docling_run)
    current_hashes = {item["artifact"]: item.get("sha256") for item in current_artifacts if item.get("sha256")}
    docling_hashes = {item["artifact"]: item.get("sha256") for item in docling_virtual_artifacts if item.get("sha256")}
    matching_names = sorted(set(current_hashes) & set(docling_hashes))
    hash_match_count = sum(1 for name in matching_names if current_hashes[name] == docling_hashes[name])
    summary = {
        "current_artifact_count": sum(1 for item in current_artifacts if item["exists"]),
        "docling_artifact_count": sum(1 for item in docling_virtual_artifacts if item["exists"]),
        "comparable_metric_count": len(metric_deltas),
        "hash_match_count": hash_match_count,
        "hash_mismatch_count": len(matching_names) - hash_match_count,
        "layout_comparison_mode": layout_comparison_mode,
        "layout_comparable": docling_run.get("status") == "success" and layout_comparison_mode != "off",
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "purpose": "docling_sanitized_artifact_comparison",
        "document_label": document_label,
        "source_sha256": source_sha256,
        "local_only": True,
        "raw_content_included": False,
        "image_bytes_included": False,
        "customer_paths_included": False,
        "summary": summary,
        "artifacts": artifacts,
        "metric_deltas": metric_deltas,
        "findings": findings,
    }
    return DoclingArtifactComparisonReport.model_validate(payload).model_dump(mode="json")


def render_scorecard(report: dict[str, Any]) -> str:
    lines = [
        "# Docling Benchmark Scorecard",
        "",
        f"- Document label: `{report.get('document_label')}`",
        f"- Compared: `{report.get('summary', {}).get('compared')}`",
        f"- Docling available: `{report.get('summary', {}).get('docling_available')}`",
        "",
        "| Tool | Status | Duration ms | Pages/sec | Key metrics |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for run in report.get("runs", []):
        metrics = run.get("metrics") if isinstance(run.get("metrics"), dict) else {}
        key_metrics = {
            key: metrics.get(key)
            for key in (
                "retrieval_chunk_record_count",
                "figure_text_chunk_record_count",
                "figure_description_chunk_record_count",
                "figure_structure_chunk_record_count",
                "table_total",
                "table_like_node_count",
                "figure_like_node_count",
                "layout_table_candidate_count",
                "layout_figure_candidate_count",
                "layout_page_candidate_count",
            )
            if key in metrics
        }
        lines.append(
            "| {tool} | {status} | {duration} | {pps} | `{metrics}` |".format(
                tool=run.get("tool", ""),
                status=run.get("status", ""),
                duration=run.get("duration_ms", 0),
                pps=run.get("pages_per_second") or "",
                metrics=json.dumps(key_metrics, ensure_ascii=False, sort_keys=True),
            )
        )
    findings = report.get("findings", [])
    if findings:
        lines.extend(["", "## Findings"])
        for finding in findings:
            lines.append(f"- `{finding.get('severity')}` `{finding.get('code')}`: {finding.get('message')}")
    return "\n".join(lines) + "\n"


def run_docling_comparison(
    *,
    input_pdf: Path,
    output_dir: Path,
    document_label: str = "doc-0001",
    pages: str | None = None,
    rag_profile: str = "technical_spec_rag",
    domain_adapter: str = DomainAdapterMode.NONE.value,
    image_mode: str = ImageMode.PLACEHOLDER.value,
    rag_figure_text_chunks: bool = True,
    figure_region_ocr: bool = False,
    rag_generated_figure_descriptions: bool = False,
    figure_description_backend: str = "local-vlm",
    figure_structure_extraction: bool = False,
    require_docling: bool = False,
    layout_comparison_mode: str = "off",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_sha256 = _source_sha256(input_pdf)
    current_output_dir = output_dir / "current_tool"
    docling_output_dir = output_dir / "docling"
    current_run = run_current_tool(
        input_pdf=input_pdf,
        output_dir=current_output_dir,
        pages=pages,
        rag_profile=rag_profile,
        domain_adapter=domain_adapter,
        image_mode=image_mode,
        rag_figure_text_chunks=rag_figure_text_chunks,
        figure_region_ocr=figure_region_ocr,
        rag_generated_figure_descriptions=rag_generated_figure_descriptions,
        figure_description_backend=figure_description_backend,
        figure_structure_extraction=figure_structure_extraction,
        layout_comparison_mode=layout_comparison_mode,
    )
    docling_run, findings, docling_virtual_artifacts = run_docling_tool(
        input_pdf=input_pdf,
        output_dir=docling_output_dir,
        layout_comparison_mode=layout_comparison_mode,
    )
    all_findings = list(findings)
    if require_docling and docling_run["status"] == "skipped":
        all_findings.append(
            {
                "severity": "error",
                "code": "docling_required_not_available",
                "tool": DOCLING_TOOL,
                "message": "Docling is required for this benchmark gate but is not installed.",
                "details": {"install_required": True},
            }
        )
    compared = current_run["status"] in {"success", "partial_success"} and docling_run["status"] == "success"
    error_count = sum(1 for finding in all_findings if finding["severity"] == "error")
    warning_count = sum(1 for finding in all_findings if finding["severity"] == "warning")
    report_payload = {
        "schema_version": SCHEMA_VERSION,
        "purpose": "docling_benchmark_comparison",
        "document_label": document_label,
        "source_sha256": source_sha256,
        "local_only": True,
        "raw_content_included": False,
        "image_bytes_included": False,
        "customer_paths_included": False,
        "summary": {
            "compared": compared,
            "current_tool_status": current_run["status"],
            "docling_status": docling_run["status"],
            "docling_available": docling_run["status"] != "skipped",
            "finding_count": len(all_findings),
            "error_count": error_count,
            "warning_count": warning_count,
            "layout_comparison_mode": layout_comparison_mode,
            "layout_comparison_enabled": layout_comparison_mode != "off",
        },
        "runs": [current_run, docling_run],
        "findings": all_findings,
    }
    report = DoclingBenchmarkReport.model_validate(report_payload).model_dump(mode="json")
    comparison = build_comparison(
        document_label=document_label,
        source_sha256=source_sha256,
        current_run=current_run,
        docling_run=docling_run,
        current_output_dir=current_output_dir,
        docling_virtual_artifacts=docling_virtual_artifacts,
        findings=all_findings,
        layout_comparison_mode=layout_comparison_mode,
    )
    write_json(output_dir / REPORT_FILENAME, report)
    write_json(output_dir / COMPARISON_FILENAME, comparison)
    write_text(output_dir / SCORECARD_FILENAME, render_scorecard(report))
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a sanitized Docling/current-tool comparison pack.")
    parser.add_argument("--input-pdf", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--document-label", default="doc-0001")
    parser.add_argument("--pages", default=None)
    parser.add_argument("--rag-profile", choices=SUPPORTED_RAG_PURPOSE_PROFILES, default="technical_spec_rag")
    parser.add_argument(
        "--domain-adapter",
        choices=[mode.value for mode in DomainAdapterMode],
        default=DomainAdapterMode.NONE.value,
    )
    parser.add_argument("--image-mode", choices=[mode.value for mode in ImageMode], default=ImageMode.PLACEHOLDER.value)
    parser.add_argument("--no-rag-figure-text-chunks", dest="rag_figure_text_chunks", action="store_false")
    parser.add_argument(
        "--figure-region-ocr",
        action="store_true",
        default=False,
        help="Include opt-in deterministic figure region OCR diagnostics in the current-tool run.",
    )
    parser.add_argument(
        "--rag-generated-figure-descriptions",
        action="store_true",
        default=False,
        help="Include opt-in generated figure description sidecars/chunks in the current-tool run.",
    )
    parser.add_argument(
        "--figure-description-backend",
        choices=SUPPORTED_FIGURE_DESCRIPTION_BACKENDS,
        default="local-vlm",
        help="Backend label recorded for generated figure description records.",
    )
    parser.add_argument(
        "--figure-structure-extraction",
        action="store_true",
        default=False,
        help="Include opt-in conservative figure structure sidecars/chunks in the current-tool run.",
    )
    parser.add_argument(
        "--require-docling",
        action="store_true",
        default=False,
        help="Treat a missing Docling installation as an error instead of an advisory skip.",
    )
    parser.add_argument(
        "--layout-comparison-mode",
        choices=LAYOUT_COMPARISON_MODES,
        default="off",
        help="Comparison-only sanitized layout metrics to collect from current-tool and Docling outputs.",
    )
    parser.add_argument("--fail-on-error", action="store_true")
    parser.set_defaults(rag_figure_text_chunks=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = run_docling_comparison(
        input_pdf=args.input_pdf,
        output_dir=args.output_dir,
        document_label=args.document_label,
        pages=args.pages,
        rag_profile=args.rag_profile,
        domain_adapter=args.domain_adapter,
        image_mode=args.image_mode,
        rag_figure_text_chunks=args.rag_figure_text_chunks,
        figure_region_ocr=args.figure_region_ocr,
        rag_generated_figure_descriptions=args.rag_generated_figure_descriptions,
        figure_description_backend=args.figure_description_backend,
        figure_structure_extraction=args.figure_structure_extraction,
        require_docling=args.require_docling,
        layout_comparison_mode=args.layout_comparison_mode,
    )
    print(f"Wrote {args.output_dir / REPORT_FILENAME}")
    if args.fail_on_error and report.get("summary", {}).get("error_count", 0):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
