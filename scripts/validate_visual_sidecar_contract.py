#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
REPORT_FILENAME = "visual_sidecar_contract_report.json"
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
VISUAL_SIDECARS = (
    "page_layout_rag.jsonl",
    "figures_rag.jsonl",
    "figure_ocr_evidence_rag.jsonl",
    "figure_descriptions_rag.jsonl",
    "figure_structures_rag.jsonl",
)


def _add_finding(
    findings: list[dict[str, Any]],
    *,
    severity: str,
    code: str,
    message: str,
    file: str | None = None,
    line: int | None = None,
    record_id: str | None = None,
    field: str | None = None,
) -> None:
    findings.append(
        {
            "severity": severity,
            "code": code,
            "file": file,
            "line": line,
            "record_id": record_id,
            "field": field,
            "message": message,
        }
    )


def _sort_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        findings,
        key=lambda item: (
            SEVERITY_ORDER.get(str(item.get("severity")), 99),
            str(item.get("file") or ""),
            int(item.get("line") or 0),
            str(item.get("record_id") or ""),
            str(item.get("field") or ""),
            str(item.get("code") or ""),
        ),
    )


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _read_jsonl(path: Path, *, findings: list[dict[str, Any]], file_name: str) -> list[tuple[int, dict[str, Any]]]:
    if not path.exists():
        return []
    records: list[tuple[int, dict[str, Any]]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            _add_finding(
                findings,
                severity="error",
                code="invalid_jsonl",
                file=file_name,
                line=line_number,
                field="$",
                message=f"Invalid JSONL record: {exc.msg}.",
            )
            continue
        if not isinstance(payload, dict):
            _add_finding(
                findings,
                severity="error",
                code="jsonl_record_not_object",
                file=file_name,
                line=line_number,
                field="$",
                message="JSONL record must be an object.",
            )
            continue
        records.append((line_number, payload))
    return records


def _record_id(record: dict[str, Any], fields: tuple[str, ...]) -> str | None:
    for field in fields:
        value = record.get(field)
        if isinstance(value, str) and value:
            return value
    return None


def _has_source_ref(record: dict[str, Any], *, source_type: str, source_id: str) -> bool:
    refs = record.get("source_refs")
    if not isinstance(refs, list):
        return False
    for ref in refs:
        if isinstance(ref, dict) and ref.get("source_type") == source_type and ref.get("source_id") == source_id:
            return True
    return False


def _index_records(records: list[tuple[int, dict[str, Any]]], id_fields: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for _, record in records:
        record_id = _record_id(record, id_fields)
        if record_id is not None:
            indexed[record_id] = record
    return indexed


def _validate_page_layout(
    records: list[tuple[int, dict[str, Any]]],
    *,
    findings: list[dict[str, Any]],
) -> None:
    for line, record in records:
        layout_id = _record_id(record, ("layout_id",))
        if layout_id is None:
            _add_finding(findings, severity="error", code="missing_layout_id", file="page_layout_rag.jsonl", line=line, field="layout_id", message="Missing layout_id.")
        if not isinstance(record.get("page"), int):
            _add_finding(findings, severity="error", code="invalid_layout_page", file="page_layout_rag.jsonl", line=line, record_id=layout_id, field="page", message="page must be an integer.")
        region_refs = record.get("region_refs")
        if not isinstance(region_refs, list):
            _add_finding(findings, severity="error", code="invalid_layout_region_refs", file="page_layout_rag.jsonl", line=line, record_id=layout_id, field="region_refs", message="region_refs must be a list.")
            continue
        declared_count = record.get("region_ref_count")
        if isinstance(declared_count, int) and declared_count != len(region_refs):
            _add_finding(findings, severity="error", code="layout_region_ref_count_mismatch", file="page_layout_rag.jsonl", line=line, record_id=layout_id, field="region_ref_count", message="region_ref_count does not match region_refs length.")


def _validate_ocr_evidence(
    records: list[tuple[int, dict[str, Any]]],
    *,
    figure_ids: set[str],
    findings: list[dict[str, Any]],
) -> None:
    for line, record in records:
        evidence_id = _record_id(record, ("evidence_id",))
        target_id = record.get("target_id")
        target_type = record.get("target_type")
        if evidence_id is None:
            _add_finding(findings, severity="error", code="missing_evidence_id", file="figure_ocr_evidence_rag.jsonl", line=line, field="evidence_id", message="Missing evidence_id.")
        if target_type == "figure" and isinstance(target_id, str) and figure_ids and target_id not in figure_ids:
            _add_finding(findings, severity="error", code="ocr_evidence_unresolved_figure", file="figure_ocr_evidence_rag.jsonl", line=line, record_id=evidence_id, field="target_id", message="OCR evidence target figure_id is not present in figures_rag.jsonl.")
        if target_type == "figure" and isinstance(target_id, str) and not _has_source_ref(record, source_type="figure", source_id=target_id):
            _add_finding(findings, severity="error", code="ocr_evidence_missing_figure_source_ref", file="figure_ocr_evidence_rag.jsonl", line=line, record_id=evidence_id, field="source_refs", message="OCR evidence must cite its target figure in source_refs.")
        if record.get("text_replaced") is True or record.get("markdown_inserted") is True:
            _add_finding(findings, severity="error", code="ocr_evidence_replaced_source_text", file="figure_ocr_evidence_rag.jsonl", line=line, record_id=evidence_id, message="Figure OCR evidence must not replace Markdown/source text.")


def _validate_description_records(
    records: list[tuple[int, dict[str, Any]]],
    *,
    figure_ids: set[str],
    findings: list[dict[str, Any]],
) -> None:
    for line, record in records:
        description_id = _record_id(record, ("description_id",))
        figure_id = record.get("figure_id")
        if not isinstance(figure_id, str):
            _add_finding(findings, severity="error", code="missing_description_figure_id", file="figure_descriptions_rag.jsonl", line=line, record_id=description_id, field="figure_id", message="Missing figure_id.")
        elif figure_ids and figure_id not in figure_ids:
            _add_finding(findings, severity="error", code="description_unresolved_figure", file="figure_descriptions_rag.jsonl", line=line, record_id=description_id, field="figure_id", message="Description figure_id is not present in figures_rag.jsonl.")
        elif not _has_source_ref(record, source_type="figure", source_id=figure_id):
            _add_finding(findings, severity="error", code="description_missing_figure_source_ref", file="figure_descriptions_rag.jsonl", line=line, record_id=description_id, field="source_refs", message="Description must cite its figure in source_refs.")
        if record.get("generated_text") is not True:
            _add_finding(findings, severity="error", code="description_missing_generated_text_flag", file="figure_descriptions_rag.jsonl", line=line, record_id=description_id, field="generated_text", message="Generated descriptions must set generated_text=true.")
        if record.get("generated_content_scope") != "sidecar_only" or record.get("markdown_inserted") is not False:
            _add_finding(findings, severity="error", code="description_generated_content_scope_violation", file="figure_descriptions_rag.jsonl", line=line, record_id=description_id, message="Generated descriptions must remain sidecar-only and not be inserted into Markdown.")


def _validate_structure_records(
    records: list[tuple[int, dict[str, Any]]],
    *,
    figure_ids: set[str],
    findings: list[dict[str, Any]],
) -> None:
    for line, record in records:
        structure_id = _record_id(record, ("structure_id",))
        figure_id = record.get("figure_id")
        if not isinstance(figure_id, str):
            _add_finding(findings, severity="error", code="missing_structure_figure_id", file="figure_structures_rag.jsonl", line=line, record_id=structure_id, field="figure_id", message="Missing figure_id.")
        elif figure_ids and figure_id not in figure_ids:
            _add_finding(findings, severity="error", code="structure_unresolved_figure", file="figure_structures_rag.jsonl", line=line, record_id=structure_id, field="figure_id", message="Structure figure_id is not present in figures_rag.jsonl.")
        elif not _has_source_ref(record, source_type="figure", source_id=figure_id):
            _add_finding(findings, severity="error", code="structure_missing_figure_source_ref", file="figure_structures_rag.jsonl", line=line, record_id=structure_id, field="source_refs", message="Structure must cite its figure in source_refs.")
        if record.get("generated_text") is True:
            _add_finding(findings, severity="warning", code="structure_generated_text_review_required", file="figure_structures_rag.jsonl", line=line, record_id=structure_id, field="generated_text", message="Structure records should distinguish generated content from observed/context-derived structure.")


def validate_visual_sidecar_contract(output_dir: Path, *, require_visual_sidecars: bool = False) -> dict[str, Any]:
    """Validate bundle-level visual sidecar linkage without returning raw visual text."""
    findings: list[dict[str, Any]] = []
    sidecars = {
        file_name: _read_jsonl(output_dir / file_name, findings=findings, file_name=file_name)
        for file_name in VISUAL_SIDECARS
    }
    manifest = _read_json(output_dir / "manifest.json")
    report = _read_json(output_dir / "report.json")
    if require_visual_sidecars:
        for file_name in ("figures_rag.jsonl", "page_layout_rag.jsonl"):
            if not (output_dir / file_name).exists():
                _add_finding(findings, severity="error", code="missing_required_visual_sidecar", file=file_name, message=f"Missing required visual sidecar: {file_name}.")

    figures = _index_records(sidecars["figures_rag.jsonl"], ("figure_id",))
    figure_ids = set(figures)
    _validate_page_layout(sidecars["page_layout_rag.jsonl"], findings=findings)
    _validate_ocr_evidence(sidecars["figure_ocr_evidence_rag.jsonl"], figure_ids=figure_ids, findings=findings)
    _validate_description_records(sidecars["figure_descriptions_rag.jsonl"], figure_ids=figure_ids, findings=findings)
    _validate_structure_records(sidecars["figure_structures_rag.jsonl"], figure_ids=figure_ids, findings=findings)

    summary = {
        "visual_sidecar_file_count": sum(1 for file_name in VISUAL_SIDECARS if (output_dir / file_name).exists()),
        "figure_record_count": len(sidecars["figures_rag.jsonl"]),
        "page_layout_record_count": len(sidecars["page_layout_rag.jsonl"]),
        "figure_ocr_evidence_record_count": len(sidecars["figure_ocr_evidence_rag.jsonl"]),
        "figure_description_record_count": len(sidecars["figure_descriptions_rag.jsonl"]),
        "figure_structure_record_count": len(sidecars["figure_structures_rag.jsonl"]),
        "error_count": sum(1 for finding in findings if finding["severity"] == "error"),
        "warning_count": sum(1 for finding in findings if finding["severity"] == "warning"),
    }
    sorted_findings = _sort_findings(findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "purpose": "visual_sidecar_contract_validation",
        "output_dir": str(output_dir),
        "status": "passed" if summary["error_count"] == 0 else "failed",
        "passed": summary["error_count"] == 0,
        "manifest_options": manifest.get("options") if isinstance(manifest, dict) else None,
        "report_summary": report.get("summary") if isinstance(report, dict) else None,
        "summary": summary,
        "findings": sorted_findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate pdf2md visual sidecar bundle contracts.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report-file", type=Path, default=None)
    parser.add_argument("--require-visual-sidecars", action="store_true")
    parser.add_argument("--fail-on-warning", action="store_true")
    args = parser.parse_args(argv)

    report = validate_visual_sidecar_contract(
        args.output_dir,
        require_visual_sidecars=args.require_visual_sidecars,
    )
    report_path = args.report_file or args.output_dir / REPORT_FILENAME
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "Visual sidecar contract validation: "
        f"passed={report['passed']} errors={report['summary']['error_count']} "
        f"warnings={report['summary']['warning_count']} report={report_path}"
    )
    if report["summary"]["error_count"] or (args.fail_on_warning and report["summary"]["warning_count"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
