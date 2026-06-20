#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from pdf2md.models import ArtifactIntegrityReport


SCHEMA_VERSION = "1.0"
REPORT_FILENAME = "artifact_integrity_report.json"
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
IMAGE_LINK_PATTERN = re.compile(r"!\[[^\]]*]\((?P<target>[^)]+)\)")
SIDECAR_COUNT_FIELDS = {
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
    "tables_rag.jsonl": "rag_table_record_count",
    "page_layout_rag.jsonl": "page_layout_record_count",
}


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
    path: str | None = None,
) -> None:
    findings.append(
        {
            "severity": severity,
            "code": code,
            "file": file,
            "line": line,
            "record_id": record_id,
            "field": field,
            "path": path,
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
            str(item.get("field") or ""),
            str(item.get("code") or ""),
            str(item.get("path") or ""),
        ),
    )


def _read_json(path: Path, *, file_name: str, findings: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not path.exists():
        _add_finding(
            findings,
            severity="error",
            code="missing_required_file",
            file=file_name,
            path=str(path),
            message=f"Required file is missing: {file_name}.",
        )
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
            path=str(path),
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
            path=str(path),
            message="JSON document must be an object.",
        )
        return None
    return payload


def _read_optional_json(path: Path, *, file_name: str, findings: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _read_json(path, file_name=file_name, findings=findings)


def _read_jsonl_count(path: Path, *, file_name: str, findings: list[dict[str, Any]]) -> int | None:
    if not path.exists():
        return None
    count = 0
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
                path=str(path),
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
                path=str(path),
                message="JSONL record must be an object.",
            )
            continue
        count += 1
    return count


def _is_external_link(target: str) -> bool:
    parsed = urlparse(target)
    return parsed.scheme in {"http", "https", "data", "mailto"}


def _clean_markdown_target(target: str) -> str:
    return unquote(target.split("#", 1)[0].split("?", 1)[0].strip().strip("<>"))


def _resolve_output_path(output_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else output_dir / path


def _existing_relative_path(output_dir: Path, value: str) -> bool:
    return _resolve_output_path(output_dir, value).exists()


def _record_path(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _manifest_image_paths(manifest: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    images = manifest.get("images")
    if not isinstance(images, list):
        return paths
    for image in images:
        if isinstance(image, dict):
            path = _record_path(image.get("path"))
            if path is not None:
                paths.add(path)
    return paths


def _image_mode_omits_asset_files(manifest: dict[str, Any] | None) -> bool:
    if not isinstance(manifest, dict):
        return False
    options = manifest.get("options")
    if not isinstance(options, dict):
        return False
    return options.get("image_mode") in {"embedded", "placeholder"}


def _figure_paths(path: Path, *, findings: list[dict[str, Any]], allow_missing_assets: bool = False) -> set[str]:
    paths: set[str] = set()
    if not path.exists():
        return paths
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        figure_path = _record_path(record.get("path"))
        if figure_path is None:
            continue
        paths.add(figure_path)
        if not allow_missing_assets and not _existing_relative_path(path.parent, figure_path):
            _add_finding(
                findings,
                severity="error",
                code="missing_figure_asset",
                file="figures_rag.jsonl",
                line=line_number,
                record_id=str(record.get("figure_id") or ""),
                field="path",
                path=figure_path,
                message="Figure sidecar path does not exist.",
            )
    return paths


def _validate_markdown_links(output_dir: Path, findings: list[dict[str, Any]]) -> tuple[int, set[str]]:
    document_path = output_dir / "document.md"
    if not document_path.exists():
        _add_finding(
            findings,
            severity="error",
            code="missing_required_file",
            file="document.md",
            path=str(document_path),
            message="Required Markdown output is missing.",
        )
        return 0, set()
    text = document_path.read_text(encoding="utf-8")
    checked = 0
    paths: set[str] = set()
    line_starts = [0]
    for match in re.finditer(r"\n", text):
        line_starts.append(match.end())
    for match in IMAGE_LINK_PATTERN.finditer(text):
        raw_target = match.group("target")
        if _is_external_link(raw_target):
            continue
        checked += 1
        target = _clean_markdown_target(raw_target)
        paths.add(target.removeprefix("./"))
        line = sum(1 for start in line_starts if start <= match.start())
        if Path(target).is_absolute():
            _add_finding(
                findings,
                severity="warning",
                code="absolute_markdown_image_link",
                file="document.md",
                line=line,
                field="image_link",
                path=target,
                message="Markdown image link uses an absolute path.",
            )
        if not _resolve_output_path(output_dir, target).exists():
            _add_finding(
                findings,
                severity="error",
                code="missing_markdown_image_asset",
                file="document.md",
                line=line,
                field="image_link",
                path=target,
                message="Markdown image link points to a missing asset.",
            )
    return checked, paths


def _validate_manifest_assets(
    output_dir: Path,
    manifest: dict[str, Any] | None,
    findings: list[dict[str, Any]],
    *,
    allow_missing_assets: bool = False,
) -> tuple[int, set[str]]:
    if manifest is None:
        return 0, set()
    checked = 0
    paths: set[str] = set()
    images = manifest.get("images")
    if not isinstance(images, list):
        _add_finding(
            findings,
            severity="error",
            code="manifest_images_not_list",
            file="manifest.json",
            field="images",
            message="manifest.images must be a list.",
        )
        return checked, paths
    for index, image in enumerate(images):
        if not isinstance(image, dict):
            continue
        path = _record_path(image.get("path"))
        if path is None:
            continue
        checked += 1
        paths.add(path)
        if not allow_missing_assets and not _existing_relative_path(output_dir, path):
            _add_finding(
                findings,
                severity="error",
                code="missing_manifest_image_asset",
                file="manifest.json",
                field=f"images[{index}].path",
                path=path,
                message="Manifest image path does not exist.",
            )
    return checked, paths


def _validate_sidecar_counts(
    output_dir: Path,
    report: dict[str, Any] | None,
    findings: list[dict[str, Any]],
) -> tuple[int, int]:
    if report is None:
        return 0, 0
    summary = report.get("summary")
    if not isinstance(summary, dict):
        return 0, 0
    omitted_outputs = {
        str(item)
        for item in summary.get("rag_sidecar_omitted_outputs", [])
        if isinstance(item, str) and item.strip()
    }
    checked_records = 0
    mismatch_count = 0
    for file_name, summary_field in SIDECAR_COUNT_FIELDS.items():
        expected = summary.get(summary_field)
        if not isinstance(expected, int):
            continue
        path = output_dir / file_name
        actual = _read_jsonl_count(path, file_name=file_name, findings=findings)
        if file_name in omitted_outputs and actual is not None:
            _add_finding(
                findings,
                severity="warning",
                code="omitted_sidecar_present",
                file=file_name,
                field="report.summary.rag_sidecar_omitted_outputs",
                path=str(path),
                message="Sidecar file exists even though report marks it as omitted by scope.",
            )
        actual_count = 0 if actual is None else actual
        checked_records += actual_count
        if expected > 0 and actual is None:
            mismatch_count += 1
            _add_finding(
                findings,
                severity="error",
                code="missing_counted_sidecar",
                file=file_name,
                field=f"report.summary.{summary_field}",
                path=str(path),
                message=f"Report expects {expected} records but sidecar file is missing.",
            )
        elif actual_count != expected:
            mismatch_count += 1
            _add_finding(
                findings,
                severity="error",
                code="sidecar_record_count_mismatch",
                file=file_name,
                field=f"report.summary.{summary_field}",
                path=str(path),
                message=f"Report count {expected} does not match actual sidecar count {actual_count}.",
            )
    table_total = summary.get("table_total")
    manifest = _read_optional_json(output_dir / "manifest.json", file_name="manifest.json", findings=findings)
    if isinstance(table_total, int) and isinstance(manifest, dict):
        tables = manifest.get("tables")
        actual_tables = len(tables) if isinstance(tables, list) else 0
        if actual_tables != table_total:
            mismatch_count += 1
            _add_finding(
                findings,
                severity="error",
                code="manifest_table_count_mismatch",
                file="manifest.json",
                field="tables",
                message=f"Manifest table count {actual_tables} does not match report summary table_total {table_total}.",
            )
    return checked_records, mismatch_count


def _validate_orphan_assets(
    output_dir: Path,
    referenced_paths: set[str],
    findings: list[dict[str, Any]],
) -> int:
    images_dir = output_dir / "assets" / "images"
    if not images_dir.exists():
        return 0
    referenced = {path.removeprefix("./") for path in referenced_paths}
    orphan_count = 0
    for asset in sorted(path for path in images_dir.iterdir() if path.is_file()):
        rel_path = asset.relative_to(output_dir).as_posix()
        if rel_path in referenced:
            continue
        orphan_count += 1
        _add_finding(
            findings,
            severity="warning",
            code="orphan_image_asset",
            file=None,
            path=rel_path,
            message="Image asset exists on disk but is not referenced by Markdown, manifest, or figures sidecar.",
        )
    return orphan_count


def _resolve_file_map_path(root: Path, document_output_dir: Any, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    candidates = [root / path]
    if isinstance(document_output_dir, str) and document_output_dir:
        doc_dir = Path(document_output_dir)
        if not doc_dir.is_absolute():
            doc_dir = root / doc_dir
        candidates.extend([doc_dir / path, doc_dir.parent / path])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _validate_file_map(
    *,
    root: Path,
    payload: dict[str, Any] | None,
    file_name: str,
    findings: list[dict[str, Any]],
    confidential_safe: bool,
) -> int:
    if payload is None:
        return 0
    documents = payload.get("documents")
    if not isinstance(documents, list):
        return 0
    missing_count = 0
    for document_index, document in enumerate(documents):
        if not isinstance(document, dict):
            continue
        files = document.get("files")
        if not isinstance(files, dict):
            continue
        document_output_dir = document.get("output_dir")
        for field_name, raw_value in files.items():
            if not isinstance(raw_value, str) or not raw_value:
                continue
            if confidential_safe and Path(raw_value).is_absolute():
                _add_finding(
                    findings,
                    severity="warning",
                    code="confidential_absolute_path",
                    file=file_name,
                    field=f"documents[{document_index}].files.{field_name}",
                    path=raw_value,
                    message="Confidential-safe file map contains an absolute path.",
                )
            resolved = _resolve_file_map_path(root, document_output_dir, raw_value)
            if not resolved.exists():
                missing_count += 1
                _add_finding(
                    findings,
                    severity="error",
                    code="missing_file_map_path",
                    file=file_name,
                    field=f"documents[{document_index}].files.{field_name}",
                    path=raw_value,
                    message="Batch/corpus file map path does not exist.",
                )
    return missing_count


def _file_summaries(output_dir: Path, findings: list[dict[str, Any]], link_count: int) -> list[dict[str, Any]]:
    summaries = []
    for file_name in ["document.md", "manifest.json", "report.json", *SIDECAR_COUNT_FIELDS.keys()]:
        path = output_dir / file_name
        record_count = 0
        if file_name.endswith(".jsonl") and path.exists():
            record_count = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        summaries.append({"file": file_name, "exists": path.exists(), "record_count": record_count, "link_count": 0})
    summaries[0]["link_count"] = link_count
    counts_by_file: dict[str, dict[str, int]] = {}
    for finding in findings:
        file_name = str(finding.get("file") or "")
        counts_by_file.setdefault(file_name, {"error": 0, "warning": 0, "info": 0})
        severity = str(finding.get("severity") or "info")
        counts_by_file[file_name][severity] = counts_by_file[file_name].get(severity, 0) + 1
    for summary in summaries:
        counts = counts_by_file.get(summary["file"], {})
        summary["error_count"] = counts.get("error", 0)
        summary["warning_count"] = counts.get("warning", 0)
        summary["info_count"] = counts.get("info", 0)
    return summaries


def validate_artifact_integrity(
    *,
    output_dir: Path,
    confidential_safe: bool = False,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    output_dir = output_dir.resolve()
    markdown_link_count, markdown_paths = _validate_markdown_links(output_dir, findings)
    manifest = _read_json(output_dir / "manifest.json", file_name="manifest.json", findings=findings)
    report = _read_json(output_dir / "report.json", file_name="report.json", findings=findings)
    allow_missing_image_assets = _image_mode_omits_asset_files(manifest)
    manifest_asset_count, manifest_paths = _validate_manifest_assets(
        output_dir,
        manifest,
        findings,
        allow_missing_assets=allow_missing_image_assets,
    )
    figure_paths = _figure_paths(
        output_dir / "figures_rag.jsonl",
        findings=findings,
        allow_missing_assets=allow_missing_image_assets,
    )
    checked_records, mismatch_count = _validate_sidecar_counts(output_dir, report, findings)
    referenced_paths = markdown_paths | manifest_paths | figure_paths
    orphan_count = _validate_orphan_assets(output_dir, referenced_paths, findings)
    batch_missing = _validate_file_map(
        root=output_dir,
        payload=_read_optional_json(output_dir / "batch_report.json", file_name="batch_report.json", findings=findings),
        file_name="batch_report.json",
        findings=findings,
        confidential_safe=confidential_safe,
    )
    corpus_missing = _validate_file_map(
        root=output_dir,
        payload=_read_optional_json(
            output_dir / "corpus_manifest.json",
            file_name="corpus_manifest.json",
            findings=findings,
        ),
        file_name="corpus_manifest.json",
        findings=findings,
        confidential_safe=confidential_safe,
    )

    findings = _sort_findings(findings)
    error_count = sum(1 for finding in findings if finding["severity"] == "error")
    warning_count = sum(1 for finding in findings if finding["severity"] == "warning")
    info_count = sum(1 for finding in findings if finding["severity"] == "info")
    missing_asset_count = sum(
        1
        for finding in findings
        if finding["code"] in {"missing_markdown_image_asset", "missing_manifest_image_asset", "missing_figure_asset"}
    )
    report_payload = {
        "schema_version": SCHEMA_VERSION,
        "purpose": "output_artifact_integrity_validation",
        "status": "passed" if error_count == 0 else "failed",
        "passed": error_count == 0,
        "output_dir": str(output_dir),
        "summary": {
            "checked_files": sum(1 for summary in _file_summaries(output_dir, findings, markdown_link_count) if summary["exists"]),
            "checked_records": checked_records,
            "checked_links": markdown_link_count,
            "checked_assets": manifest_asset_count + len(figure_paths),
            "missing_assets": missing_asset_count,
            "orphan_assets": orphan_count,
            "sidecar_count_mismatches": mismatch_count,
            "file_map_missing_count": batch_missing + corpus_missing,
            "error_count": error_count,
            "warning_count": warning_count,
            "info_count": info_count,
        },
        "files": _file_summaries(output_dir, findings, markdown_link_count),
        "findings": findings,
    }
    ArtifactIntegrityReport.model_validate(report_payload)
    return report_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate output artifact links, files, and sidecar counts.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report-file", type=Path)
    parser.add_argument("--confidential-safe", action="store_true")
    parser.add_argument("--fail-on-warning", action="store_true")
    parser.add_argument("--fail-on-error", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_artifact_integrity(
        output_dir=args.output_dir,
        confidential_safe=args.confidential_safe,
    )
    report_path = args.report_file or (args.output_dir / REPORT_FILENAME)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {report_path}")
    if args.fail_on_error and report["summary"]["error_count"]:
        return 1
    if args.fail_on_warning and (report["summary"]["error_count"] or report["summary"]["warning_count"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
