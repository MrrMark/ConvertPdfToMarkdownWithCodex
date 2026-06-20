#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pdf2md.models import FigureDescriptionEvalReport
from pdf2md.utils.io import write_json

REPORT_FILENAME = "figure_description_eval_report.json"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            records.append({"_invalid_json": True, "_line_number": line_number, "_error": str(exc)})
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _finding(
    *,
    severity: str,
    code: str,
    message: str,
    record: dict[str, Any] | None = None,
    chunk_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "description_id": (record or {}).get("description_id"),
        "figure_id": (record or {}).get("figure_id"),
        "chunk_id": chunk_id,
        "message": message,
        "details": details or {},
    }


def _positive_intish(value: Any) -> bool:
    try:
        return int(value or 0) > 0
    except (TypeError, ValueError):
        return False


def _has_source_evidence(record: dict[str, Any]) -> bool:
    evidence = record.get("source_evidence")
    if not isinstance(evidence, dict):
        return False
    return bool(
        evidence.get("caption_present")
        or evidence.get("heading_path_present")
        or _positive_intish(evidence.get("detected_label_count"))
        or _positive_intish(evidence.get("nearby_text_count"))
        or _positive_intish(evidence.get("ocr_text_count"))
    )


def _description_chunk_refs(chunks: list[dict[str, Any]]) -> set[str]:
    refs: set[str] = set()
    for chunk in chunks:
        if chunk.get("chunk_type") != "figure_description":
            continue
        for ref in chunk.get("source_refs") or []:
            if isinstance(ref, dict) and ref.get("source_type") == "figure_description" and ref.get("source_id"):
                refs.add(str(ref["source_id"]))
    return refs


def evaluate_figure_descriptions(
    *,
    output_dir: Path,
    min_confidence: float = 0.65,
) -> dict[str, Any]:
    """Evaluate local figure description sidecars without reading raw image/PDF content."""
    figure_records = _read_jsonl(output_dir / "figures_rag.jsonl")
    description_records = _read_jsonl(output_dir / "figure_descriptions_rag.jsonl")
    retrieval_chunks = _read_jsonl(output_dir / "retrieval_chunks_rag.jsonl")
    chunk_refs = _description_chunk_refs(retrieval_chunks)
    findings: list[dict[str, Any]] = []

    if not description_records:
        findings.append(
            _finding(
                severity="error",
                code="missing_figure_descriptions",
                message="figure_descriptions_rag.jsonl is missing or empty.",
            )
        )

    generated_text_record_count = 0
    evidence_backed_record_count = 0
    low_confidence_count = 0
    missing_source_ref_count = 0
    missing_source_evidence_count = 0
    visual_pixels_interpreted_count = 0
    backend_invoked_count = 0
    missing_retrieval_chunk_count = 0
    missing_review_metadata_count = 0
    markdown_inserted_count = 0
    invalid_generated_scope_count = 0

    for record in description_records:
        if record.get("_invalid_json"):
            findings.append(
                _finding(
                    severity="error",
                    code="invalid_jsonl_record",
                    message="Invalid JSONL record in figure_descriptions_rag.jsonl.",
                    details={"line_number": record.get("_line_number")},
                )
            )
            continue
        description_id = str(record.get("description_id") or "")
        if record.get("generated_text") is True:
            generated_text_record_count += 1
        else:
            findings.append(
                _finding(
                    severity="error",
                    code="missing_generated_text_flag",
                    message="Figure description record must set generated_text=true.",
                    record=record,
                )
            )
        if record.get("generated_description") != record.get("text"):
            missing_review_metadata_count += 1
            findings.append(
                _finding(
                    severity="error",
                    code="generated_description_mismatch",
                    message="generated_description must match the sidecar text field.",
                    record=record,
                )
            )
        observed_text = record.get("observed_text")
        if not isinstance(observed_text, dict) or observed_text.get("visual_pixels_interpreted") is not False:
            missing_review_metadata_count += 1
            findings.append(
                _finding(
                    severity="error",
                    code="invalid_observed_text_metadata",
                    message="observed_text must separate source evidence and set visual_pixels_interpreted=false.",
                    record=record,
                )
            )
        if record.get("review_required") is not True or not isinstance(record.get("review_reasons"), list):
            missing_review_metadata_count += 1
            findings.append(
                _finding(
                    severity="error",
                    code="missing_review_metadata",
                    message="Figure description records must include review_required=true and review_reasons[].",
                    record=record,
                )
            )
        if record.get("hallucination_risk") not in {"low", "medium", "high"}:
            missing_review_metadata_count += 1
            findings.append(
                _finding(
                    severity="error",
                    code="invalid_hallucination_risk",
                    message="Figure description records must classify hallucination_risk as low, medium, or high.",
                    record=record,
                )
            )
        if record.get("generated_content_scope") != "sidecar_only":
            invalid_generated_scope_count += 1
            findings.append(
                _finding(
                    severity="error",
                    code="invalid_generated_content_scope",
                    message="Figure description records must use generated_content_scope=sidecar_only.",
                    record=record,
                )
            )
        if record.get("markdown_inserted") is not False:
            markdown_inserted_count += 1
            findings.append(
                _finding(
                    severity="error",
                    code="figure_description_markdown_pollution",
                    message="Generated figure descriptions must not be inserted into Markdown.",
                    record=record,
                )
            )
        source_refs = record.get("source_refs")
        if not isinstance(source_refs, list) or not source_refs:
            missing_source_ref_count += 1
            findings.append(
                _finding(
                    severity="error",
                    code="missing_source_refs",
                    message="Figure description record must include source_refs.",
                    record=record,
                )
            )
        if not _has_source_evidence(record):
            missing_source_evidence_count += 1
            findings.append(
                _finding(
                    severity="error",
                    code="missing_source_evidence",
                    message="Figure description record lacks caption, heading, label, or nearby text evidence.",
                    record=record,
                )
            )
        else:
            evidence_backed_record_count += 1
        source_evidence = record.get("source_evidence") if isinstance(record.get("source_evidence"), dict) else {}
        if source_evidence.get("visual_pixels_interpreted") is True:
            visual_pixels_interpreted_count += 1
            findings.append(
                _finding(
                    severity="error",
                    code="visual_pixels_interpreted",
                    message="Local-only evaluation does not allow visual pixel interpretation claims.",
                    record=record,
                )
            )
        if record.get("backend_status") != "not_invoked_context_only":
            backend_invoked_count += 1
            findings.append(
                _finding(
                    severity="error",
                    code="backend_invoked",
                    message="Figure description backend must not be invoked in the local-only evaluation path.",
                    record=record,
                    details={"backend_status": record.get("backend_status")},
                )
            )
        try:
            confidence = float(record.get("classification_confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < min_confidence:
            low_confidence_count += 1
            findings.append(
                _finding(
                    severity="warning",
                    code="low_confidence",
                    message="Figure description confidence is below the configured threshold.",
                    record=record,
                    details={"classification_confidence": confidence, "min_confidence": min_confidence},
                )
            )
        if description_id and description_id not in chunk_refs:
            missing_retrieval_chunk_count += 1
            findings.append(
                _finding(
                    severity="warning",
                    code="missing_retrieval_chunk",
                    message="No retrieval chunk references this figure description.",
                    record=record,
                )
            )

    error_count = sum(1 for finding in findings if finding["severity"] == "error")
    warning_count = sum(1 for finding in findings if finding["severity"] == "warning")
    payload = {
        "schema_version": "1.0",
        "purpose": "local_figure_description_eval",
        "local_only": True,
        "raw_images_included": False,
        "raw_pdf_text_included": False,
        "customer_paths_included": False,
        "min_confidence": min_confidence,
        "summary": {
            "figure_record_count": len([record for record in figure_records if not record.get("_invalid_json")]),
            "description_record_count": len(
                [record for record in description_records if not record.get("_invalid_json")]
            ),
            "figure_description_chunk_count": sum(
                1 for chunk in retrieval_chunks if chunk.get("chunk_type") == "figure_description"
            ),
            "generated_text_record_count": generated_text_record_count,
            "evidence_backed_record_count": evidence_backed_record_count,
            "low_confidence_count": low_confidence_count,
            "missing_source_ref_count": missing_source_ref_count,
            "missing_source_evidence_count": missing_source_evidence_count,
            "visual_pixels_interpreted_count": visual_pixels_interpreted_count,
            "backend_invoked_count": backend_invoked_count,
            "missing_retrieval_chunk_count": missing_retrieval_chunk_count,
            "missing_review_metadata_count": missing_review_metadata_count,
            "markdown_inserted_count": markdown_inserted_count,
            "invalid_generated_scope_count": invalid_generated_scope_count,
            "error_count": error_count,
            "warning_count": warning_count,
            "passed": error_count == 0,
        },
        "findings": findings,
    }
    return FigureDescriptionEvalReport.model_validate(payload).model_dump(mode="json")


def format_text_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "Figure description evaluation",
        f"- Passed: {summary['passed']}",
        f"- Descriptions: {summary['description_record_count']}",
        f"- Figure description chunks: {summary['figure_description_chunk_count']}",
        f"- Errors: {summary['error_count']}",
        f"- Warnings: {summary['warning_count']}",
    ]
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate local-only figure description sidecars.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report-file", type=Path)
    parser.add_argument("--min-confidence", type=float, default=0.65)
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--fail-on-error", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = evaluate_figure_descriptions(output_dir=args.output_dir, min_confidence=args.min_confidence)
    report_file = args.report_file or args.output_dir / REPORT_FILENAME
    write_json(report_file, report)
    if args.json_output:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_text_report(report), end="")
        print(f"Wrote {report_file}")
    if args.fail_on_error and report["summary"]["error_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
