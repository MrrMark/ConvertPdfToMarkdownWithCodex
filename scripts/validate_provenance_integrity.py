#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pdf2md.models import ProvenanceIntegrityReport


SCHEMA_VERSION = "1.0"
REPORT_FILENAME = "provenance_integrity_report.json"
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}

SIDECAR_SPECS = {
    "text_blocks_rag.jsonl": {"source_types": ("text_block",), "id_fields": ("block_id",)},
    "semantic_units_rag.jsonl": {"source_types": ("semantic_unit",), "id_fields": ("semantic_id",)},
    "requirements_rag.jsonl": {"source_types": ("requirement",), "id_fields": ("semantic_id",)},
    "requirement_traceability_rag.jsonl": {
        "source_types": ("requirement_trace",),
        "id_fields": ("trace_id",),
    },
    "technical_tables_rag.jsonl": {
        "source_types": ("technical_table_unit", "technical_table"),
        "id_fields": ("technical_table_unit_id",),
    },
    "tables_rag.jsonl": {"source_types": ("table_row",), "id_fields": ("table_row_id",)},
    "figures_rag.jsonl": {"source_types": ("figure", "excluded_figure"), "id_fields": ("figure_id",)},
    "figure_ocr_evidence_rag.jsonl": {
        "source_types": ("ocr_evidence",),
        "id_fields": ("evidence_id",),
    },
    "figure_descriptions_rag.jsonl": {
        "source_types": ("figure_description",),
        "id_fields": ("description_id",),
    },
    "figure_structures_rag.jsonl": {"source_types": ("figure_structure",), "id_fields": ("structure_id",)},
    "domain_units_rag.jsonl": {"source_types": ("domain_unit",), "id_fields": ("domain_unit_id",)},
    "cross_refs_rag.jsonl": {"source_types": ("cross_ref",), "id_fields": ("ref_id",)},
    "retrieval_chunks_rag.jsonl": {"source_types": ("retrieval_chunk",), "id_fields": ("chunk_id",)},
    "page_layout_rag.jsonl": {"source_types": ("page_layout",), "id_fields": ("layout_id",)},
}
SUPPORTED_SOURCE_TYPES = {
    source_type
    for spec in SIDECAR_SPECS.values()
    for source_type in spec["source_types"]
} | {"table"}
REPORT_COUNT_FIELDS = {
    "text_blocks_rag.jsonl": "rag_text_block_record_count",
    "semantic_units_rag.jsonl": "semantic_unit_record_count",
    "requirements_rag.jsonl": "requirement_record_count",
    "cross_refs_rag.jsonl": "cross_ref_record_count",
    "requirement_traceability_rag.jsonl": "requirement_traceability_record_count",
    "technical_tables_rag.jsonl": "technical_table_record_count",
    "figures_rag.jsonl": "figure_rag_record_count",
    "figure_ocr_evidence_rag.jsonl": "figure_ocr_evidence_record_count",
    "figure_descriptions_rag.jsonl": "figure_description_record_count",
    "figure_structures_rag.jsonl": "figure_structure_record_count",
    "domain_units_rag.jsonl": "domain_unit_record_count",
    "retrieval_chunks_rag.jsonl": "retrieval_chunk_record_count",
    "page_layout_rag.jsonl": "page_layout_record_count",
}
RAG_TABLE_COUNT_FIELD = "rag_table_record_count"


@dataclass(frozen=True)
class RecordLocator:
    file_name: str
    line: int
    record_id: str
    record: dict[str, Any]


def _is_missing(value: Any) -> bool:
    return value is None or value == ""


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _record_id(record: dict[str, Any]) -> str | None:
    for field in (
        "chunk_id",
        "block_id",
        "semantic_id",
        "trace_id",
        "technical_table_unit_id",
        "table_row_id",
        "table_id",
        "figure_id",
        "description_id",
        "structure_id",
        "domain_unit_id",
        "ref_id",
        "layout_id",
    ):
        value = record.get(field)
        if not _is_missing(value):
            return str(value)
    return None


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
    source_type: str | None = None,
    source_id: str | None = None,
) -> None:
    findings.append(
        {
            "severity": severity,
            "code": code,
            "file": file,
            "line": line,
            "record_id": record_id,
            "field": field,
            "source_type": source_type,
            "source_id": source_id,
            "message": message,
        }
    )


def _read_jsonl(
    path: Path,
    *,
    file_name: str,
    findings: list[dict[str, Any]],
) -> tuple[list[tuple[int, dict[str, Any]]], dict[str, Any]]:
    summary = {"file": file_name, "exists": path.exists(), "record_count": 0}
    if not path.exists():
        return [], summary
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
    summary["record_count"] = len(records)
    return records, summary


def _read_json(path: Path, *, file_name: str, findings: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _add_finding(
            findings,
            severity="error",
            code="invalid_json",
            file=file_name,
            field="$",
            message=f"Invalid JSON document: {exc.msg}.",
        )
        return None
    if not isinstance(payload, dict):
        _add_finding(
            findings,
            severity="error",
            code="json_document_not_object",
            file=file_name,
            field="$",
            message="JSON document must be an object.",
        )
        return None
    return payload


def _page_set(record: dict[str, Any]) -> set[int]:
    pages: set[int] = set()
    page = record.get("page")
    if _is_int(page) and page >= 1:
        pages.add(page)
    page_range = record.get("page_range")
    if (
        isinstance(page_range, list)
        and len(page_range) == 2
        and all(_is_int(value) and value >= 1 for value in page_range)
        and page_range[0] <= page_range[1]
    ):
        pages.update(range(page_range[0], page_range[1] + 1))
    return pages


def _bbox(value: Any) -> list[float] | None:
    if isinstance(value, list) and len(value) == 4 and all(_is_number(item) for item in value):
        return [float(item) for item in value]
    return None


def _bbox_close(left: list[float], right: list[float], *, tolerance: float = 0.05) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(left, right))


def _source_ids(source_refs: Any) -> list[str]:
    if not isinstance(source_refs, list):
        return []
    ids: list[str] = []
    for ref in source_refs:
        if isinstance(ref, dict) and not _is_missing(ref.get("source_id")):
            ids.append(str(ref["source_id"]))
    return ids


def _expected_dedupe_key(record: dict[str, Any]) -> str | None:
    ids = sorted(_source_ids(record.get("source_refs")))
    if not ids:
        return None
    return "|".join(ids)


def _dedupe_key_matches(actual: Any, expected: str | None) -> bool:
    if expected is None:
        return actual in {None, ""}
    if not isinstance(actual, str):
        return False
    return actual == expected or actual.startswith(f"{expected}|part-")


def _sort_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        findings,
        key=lambda item: (
            SEVERITY_ORDER.get(str(item.get("severity")), 99),
            str(item.get("file") or ""),
            int(item.get("line") or 0),
            str(item.get("field") or ""),
            str(item.get("code") or ""),
            str(item.get("source_type") or ""),
            str(item.get("source_id") or ""),
        ),
    )


def _file_summaries(file_summaries: list[dict[str, Any]], findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_file: dict[str, dict[str, int]] = {}
    for finding in findings:
        file_name = finding.get("file")
        if not file_name:
            continue
        bucket = by_file.setdefault(str(file_name), {"error_count": 0, "warning_count": 0, "info_count": 0})
        severity = str(finding.get("severity"))
        if severity == "error":
            bucket["error_count"] += 1
        elif severity == "warning":
            bucket["warning_count"] += 1
        elif severity == "info":
            bucket["info_count"] += 1
    result: list[dict[str, Any]] = []
    for summary in file_summaries:
        counts = by_file.get(str(summary["file"]), {})
        result.append(
            {
                **summary,
                "error_count": counts.get("error_count", 0),
                "warning_count": counts.get("warning_count", 0),
                "info_count": counts.get("info_count", 0),
            }
        )
    return result


def _index_records(
    *,
    all_records: dict[str, list[tuple[int, dict[str, Any]]]],
    findings: list[dict[str, Any]],
) -> dict[str, dict[str, RecordLocator]]:
    index: dict[str, dict[str, RecordLocator]] = {}
    for file_name, records in all_records.items():
        spec = SIDECAR_SPECS[file_name]
        for line, record in records:
            for id_field in spec["id_fields"]:
                value = record.get(id_field)
                if _is_missing(value):
                    continue
                record_id = str(value)
                for source_type in spec["source_types"]:
                    bucket = index.setdefault(source_type, {})
                    if record_id in bucket:
                        _add_finding(
                            findings,
                            severity="error",
                            code="duplicate_record_id",
                            file=file_name,
                            line=line,
                            record_id=record_id,
                            field=id_field,
                            source_type=source_type,
                            source_id=record_id,
                            message=f"Duplicate {source_type} id: {record_id}.",
                        )
                        continue
                    bucket[record_id] = RecordLocator(file_name, line, record_id, record)
            if file_name == "tables_rag.jsonl" and not _is_missing(record.get("table_id")):
                table_id = str(record["table_id"])
                bucket = index.setdefault("table", {})
                bucket.setdefault(table_id, RecordLocator(file_name, line, table_id, record))
    return index


def _validate_source_ref(
    *,
    file_name: str,
    line: int,
    record: dict[str, Any],
    ref: dict[str, Any],
    ref_index: int,
    index: dict[str, dict[str, RecordLocator]],
    findings: list[dict[str, Any]],
) -> bool:
    record_id = _record_id(record)
    field = f"source_refs[{ref_index}]"
    source_type = ref.get("source_type")
    source_id = ref.get("source_id")
    if _is_missing(source_type) or _is_missing(source_id):
        _add_finding(
            findings,
            severity="error",
            code="incomplete_source_ref",
            file=file_name,
            line=line,
            record_id=record_id,
            field=field,
            source_type=str(source_type) if source_type is not None else None,
            source_id=str(source_id) if source_id is not None else None,
            message="source_refs entries must include source_type and source_id.",
        )
        return False
    source_type = str(source_type)
    source_id = str(source_id)
    ref_page = ref.get("page")
    record_pages = _page_set(record)
    if _is_int(ref_page) and record_pages and ref_page not in record_pages:
        _add_finding(
            findings,
            severity="error",
            code="source_ref_outside_record_page_range",
            file=file_name,
            line=line,
            record_id=record_id,
            field=f"{field}.page",
            source_type=source_type,
            source_id=source_id,
            message=f"source_ref page {ref_page} is outside record page(s) {sorted(record_pages)}.",
        )
    if source_type not in SUPPORTED_SOURCE_TYPES:
        _add_finding(
            findings,
            severity="warning",
            code="unknown_source_type",
            file=file_name,
            line=line,
            record_id=record_id,
            field=f"{field}.source_type",
            source_type=source_type,
            source_id=source_id,
            message=f"No sidecar index is available for source_type={source_type}.",
        )
        return False
    locator = index.get(source_type, {}).get(source_id)
    if locator is None:
        _add_finding(
            findings,
            severity="error",
            code="unresolved_source_ref",
            file=file_name,
            line=line,
            record_id=record_id,
            field=f"{field}.source_id",
            source_type=source_type,
            source_id=source_id,
            message=f"source_ref {source_type}/{source_id} does not resolve to a sidecar record.",
        )
        return False

    referenced_pages = _page_set(locator.record)
    if _is_int(ref_page) and referenced_pages and ref_page not in referenced_pages:
        _add_finding(
            findings,
            severity="error",
            code="source_ref_page_mismatch",
            file=file_name,
            line=line,
            record_id=record_id,
            field=f"{field}.page",
            source_type=source_type,
            source_id=source_id,
            message=f"source_ref page {ref_page} does not match referenced record page(s) {sorted(referenced_pages)}.",
        )
    ref_bbox = _bbox(ref.get("bbox"))
    referenced_bbox = _bbox(locator.record.get("bbox"))
    if ref_bbox is not None and referenced_bbox is not None and not _bbox_close(ref_bbox, referenced_bbox):
        _add_finding(
            findings,
            severity="warning",
            code="source_ref_bbox_mismatch",
            file=file_name,
            line=line,
            record_id=record_id,
            field=f"{field}.bbox",
            source_type=source_type,
            source_id=source_id,
            message="source_ref bbox differs from referenced record bbox.",
        )
    return True


def _validate_record_source_refs(
    *,
    file_name: str,
    line: int,
    record: dict[str, Any],
    index: dict[str, dict[str, RecordLocator]],
    findings: list[dict[str, Any]],
) -> tuple[int, int]:
    source_refs = record.get("source_refs")
    if source_refs is None:
        return 0, 0
    record_id = _record_id(record)
    if not isinstance(source_refs, list):
        _add_finding(
            findings,
            severity="error",
            code="source_refs_not_list",
            file=file_name,
            line=line,
            record_id=record_id,
            field="source_refs",
            message="source_refs must be a list when present.",
        )
        return 0, 0
    checked = 0
    resolved = 0
    for ref_index, ref in enumerate(source_refs, start=1):
        if not isinstance(ref, dict):
            _add_finding(
                findings,
                severity="error",
                code="source_ref_not_object",
                file=file_name,
                line=line,
                record_id=record_id,
                field=f"source_refs[{ref_index}]",
                message="source_refs entries must be objects.",
            )
            checked += 1
            continue
        checked += 1
        resolved += int(
            _validate_source_ref(
                file_name=file_name,
                line=line,
                record=record,
                ref=ref,
                ref_index=ref_index,
                index=index,
                findings=findings,
            )
        )
    return checked, resolved


def _validate_retrieval_chunk(
    *,
    line: int,
    record: dict[str, Any],
    findings: list[dict[str, Any]],
) -> None:
    record_id = _record_id(record)
    source_refs = record.get("source_refs")
    if isinstance(source_refs, list):
        expected_count = len(source_refs)
        actual_count = record.get("source_record_count")
        if _is_int(actual_count) and actual_count != expected_count:
            _add_finding(
                findings,
                severity="error",
                code="source_record_count_mismatch",
                file="retrieval_chunks_rag.jsonl",
                line=line,
                record_id=record_id,
                field="source_record_count",
                message=f"source_record_count={actual_count} but source_refs has {expected_count} entries.",
            )
        expected_key = _expected_dedupe_key(record)
        if not _dedupe_key_matches(record.get("source_dedupe_key"), expected_key):
            _add_finding(
                findings,
                severity="warning",
                code="source_dedupe_key_mismatch",
                file="retrieval_chunks_rag.jsonl",
                line=line,
                record_id=record_id,
                field="source_dedupe_key",
                message=f"source_dedupe_key should be derived from source ids: {expected_key}.",
            )


def _actual_count_for_report(file_name: str, records: list[tuple[int, dict[str, Any]]]) -> int:
    if file_name != "tables_rag.jsonl":
        return len(records)
    return len(records)


def _validate_report_counts(
    *,
    report: dict[str, Any] | None,
    all_records: dict[str, list[tuple[int, dict[str, Any]]]],
    findings: list[dict[str, Any]],
) -> None:
    if not isinstance(report, dict):
        return
    summary = report.get("summary")
    if not isinstance(summary, dict):
        return
    for file_name, count_field in REPORT_COUNT_FIELDS.items():
        if count_field not in summary:
            continue
        expected = summary.get(count_field)
        actual = _actual_count_for_report(file_name, all_records.get(file_name, []))
        if _is_int(expected) and expected != actual:
            _add_finding(
                findings,
                severity="warning",
                code="report_record_count_mismatch",
                file="report.json",
                field=f"summary.{count_field}",
                message=f"report summary {count_field}={expected} but {file_name} has {actual} records.",
            )
    if RAG_TABLE_COUNT_FIELD in summary:
        expected = summary.get(RAG_TABLE_COUNT_FIELD)
        actual = len(all_records.get("tables_rag.jsonl", []))
        if _is_int(expected) and expected != actual:
            _add_finding(
                findings,
                severity="warning",
                code="report_record_count_mismatch",
                file="report.json",
                field=f"summary.{RAG_TABLE_COUNT_FIELD}",
                message=f"report summary {RAG_TABLE_COUNT_FIELD}={expected} but tables_rag.jsonl has {actual} records.",
            )


def validate_provenance_integrity(*, output_dir: Path) -> dict[str, Any]:
    """Validate that RAG sidecar source_refs resolve to local sidecar records."""
    findings: list[dict[str, Any]] = []
    file_summaries: list[dict[str, Any]] = []
    if not output_dir.exists():
        _add_finding(
            findings,
            severity="error",
            code="missing_output_dir",
            message=f"Output directory does not exist: {output_dir}.",
        )

    all_records: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for file_name in SIDECAR_SPECS:
        records, summary = _read_jsonl(output_dir / file_name, file_name=file_name, findings=findings)
        all_records[file_name] = records
        file_summaries.append(summary)

    report = _read_json(output_dir / "report.json", file_name="report.json", findings=findings)
    index = _index_records(all_records=all_records, findings=findings)
    checked_source_refs = 0
    resolved_source_refs = 0
    for file_name, records in all_records.items():
        for line, record in records:
            checked, resolved = _validate_record_source_refs(
                file_name=file_name,
                line=line,
                record=record,
                index=index,
                findings=findings,
            )
            checked_source_refs += checked
            resolved_source_refs += resolved
            if file_name == "retrieval_chunks_rag.jsonl":
                _validate_retrieval_chunk(line=line, record=record, findings=findings)
    _validate_report_counts(report=report, all_records=all_records, findings=findings)

    sorted_findings = _sort_findings(findings)
    error_count = sum(1 for finding in sorted_findings if finding["severity"] == "error")
    warning_count = sum(1 for finding in sorted_findings if finding["severity"] == "warning")
    info_count = sum(1 for finding in sorted_findings if finding["severity"] == "info")
    checked_files = sum(1 for summary in file_summaries if summary["exists"])
    checked_records = sum(int(summary["record_count"]) for summary in file_summaries)
    unresolved_source_refs = max(checked_source_refs - resolved_source_refs, 0)
    status = "failed" if error_count else ("warning" if warning_count else "passed")
    report_payload = {
        "schema_version": SCHEMA_VERSION,
        "purpose": "rag_provenance_integrity_validation",
        "status": status,
        "passed": error_count == 0,
        "output_dir": str(output_dir),
        "summary": {
            "checked_files": checked_files,
            "checked_records": checked_records,
            "checked_source_refs": checked_source_refs,
            "resolved_source_refs": resolved_source_refs,
            "unresolved_source_refs": unresolved_source_refs,
            "error_count": error_count,
            "warning_count": warning_count,
            "info_count": info_count,
        },
        "files": _file_summaries(file_summaries, sorted_findings),
        "findings": sorted_findings,
    }
    return ProvenanceIntegrityReport.model_validate(report_payload).model_dump(mode="json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate pdf2md RAG sidecar provenance integrity.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report-file", type=Path, default=None)
    parser.add_argument("--fail-on-warning", action="store_true")
    parser.add_argument("--fail-on-error", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_provenance_integrity(output_dir=args.output_dir)
    report_path = args.report_file or args.output_dir / REPORT_FILENAME
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = report["summary"]
    print(
        "Provenance integrity validation: "
        f"status={report['status']} errors={summary['error_count']} "
        f"warnings={summary['warning_count']} report={report_path}"
    )
    if args.fail_on_error and summary["error_count"]:
        return 1
    if args.fail_on_warning and (summary["error_count"] or summary["warning_count"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
