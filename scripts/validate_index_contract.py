#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from pdf2md.models import IndexContractReport


SCHEMA_VERSION = "1.0"
REPORT_FILENAME = "index_contract_report.json"
INDEX_TARGETS = ("openai", "azure-ai-search", "langchain", "llamaindex")
ALL_TARGETS = ("all",) + INDEX_TARGETS
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
POSIX_ABSOLUTE_PATH_RE = re.compile(r"^/(Users|private|tmp|var|home|Volumes|opt|Library|System|Applications)(/|$)")
WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")
PDF_FILENAME_RE = re.compile(r"(^|[/\\])[^/\\]+\.pdf$", re.IGNORECASE)
CUSTOMER_FIELD_RE = re.compile(r"(customer|product|codename|code_name)", re.IGNORECASE)

RETRIEVAL_CHUNKS = "retrieval_chunks_rag.jsonl"
SIDE_CAR_FILES = (
    "text_blocks_rag.jsonl",
    "semantic_units_rag.jsonl",
    "requirements_rag.jsonl",
    "cross_refs_rag.jsonl",
    "requirement_traceability_rag.jsonl",
    "technical_tables_rag.jsonl",
    "tables_rag.jsonl",
    "figures_rag.jsonl",
    "figure_descriptions_rag.jsonl",
    "figure_structures_rag.jsonl",
    "domain_units_rag.jsonl",
)
JSON_FILES = ("manifest.json", "report.json")
RETRIEVAL_REQUIRED_FIELDS = {
    "chunk_id",
    "schema_version",
    "chunk_index",
    "chunk_type",
    "text",
    "source_sha256",
    "source_refs",
    "page_range",
    "bbox",
    "heading_path",
    "semantic_types",
    "normative_strength",
    "retrieval_priority",
    "char_count",
    "token_estimate",
    "section_path",
    "chunk_group_id",
    "source_record_count",
    "source_dedupe_key",
    "chunk_boundary_policy",
    "chunk_boundary_reasons",
}
RELATIONSHIP_ID_FIELDS = (
    "previous_chunk_id",
    "next_chunk_id",
    "section_anchor_chunk_id",
)
VISUAL_CHUNK_TYPES = {"figure_text", "figure_description", "figure_structure"}
FIGURE_SOURCE_TYPES = {"figure", "excluded_figure"}
VISUAL_CHUNK_REQUIRED_SOURCE_TYPES = {
    "figure_text": FIGURE_SOURCE_TYPES,
    "figure_description": FIGURE_SOURCE_TYPES | {"figure_description"},
    "figure_structure": FIGURE_SOURCE_TYPES | {"figure_structure"},
}
FIGURE_DESCRIPTION_GENERATION_STRATEGY = "deterministic_context_summary"
SOURCE_REF_SIDECARS = {
    "semantic_units_rag.jsonl": "semantic_id",
    "requirements_rag.jsonl": "semantic_id",
    "cross_refs_rag.jsonl": "ref_id",
    "requirement_traceability_rag.jsonl": "trace_id",
    "technical_tables_rag.jsonl": "technical_table_unit_id",
    "figures_rag.jsonl": "figure_id",
    "figure_descriptions_rag.jsonl": "description_id",
    "figure_structures_rag.jsonl": "structure_id",
    "domain_units_rag.jsonl": "domain_unit_id",
}
FIGURE_DESCRIPTION_REQUIRED_FIELDS = {
    "description_id",
    "figure_id",
    "page",
    "text",
    "source_refs",
    "generated_text",
    "generation_strategy",
}
FIGURE_STRUCTURE_REQUIRED_FIELDS = {
    "structure_id",
    "figure_id",
    "page",
    "text",
    "source_refs",
    "generated_text",
    "derived_from_context",
}
TEXT_BLOCK_FIELDS = ("block_id", "page", "block_index", "text")
TABLE_ROW_REQUIRED_FIELDS = {
    "table_id",
    "table_row_id",
    "page",
    "table_index",
    "source_mode",
    "headers",
    "row_index",
    "cells",
    "row_text",
    "bbox",
    "quality_score",
    "fallback_reasons",
    "header_depth",
    "header_confidence",
    "rag_header_strategy",
}
REQUIREMENT_TRACE_REQUIRED_FIELDS = {
    "trace_id",
    "trace_index",
    "requirement_id",
    "normative_strength",
    "text",
    "condition",
    "applicability",
    "dependency_refs",
    "exception_text",
    "testability_hint",
    "page_range",
    "bbox",
    "heading_path",
    "source_refs",
    "classification_confidence",
    "classification_reasons",
}
TECHNICAL_TABLE_REQUIRED_FIELDS = {
    "technical_table_unit_id",
    "technical_table_unit_index",
    "unit_type",
    "page",
    "table_id",
    "table_row_id",
    "row_index",
    "text",
    "raw_cells",
    "bit_range",
    "field_name",
    "value",
    "meaning",
    "reset_default",
    "access",
    "requirement_ref",
    "opcode",
    "command",
    "log_identifier",
    "feature_identifier",
    "bbox",
    "source_refs",
    "classification_confidence",
    "classification_reasons",
}
DEFAULT_METADATA_LIMITS = {
    "openai": 16 * 1024,
    "azure-ai-search": 32 * 1024,
    "langchain": 64 * 1024,
    "llamaindex": 64 * 1024,
}
NULLABLE_STRING_FIELDS = {
    "requirement_id",
    "condition",
    "applicability",
    "exception_text",
    "bit_range",
    "field_name",
    "value",
    "meaning",
    "reset_default",
    "access",
    "requirement_ref",
    "opcode",
    "command",
    "log_identifier",
    "feature_identifier",
}


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_missing(value: Any) -> bool:
    return value is None or value == ""


def _record_id(record: dict[str, Any]) -> str | None:
    for field in (
        "chunk_id",
        "semantic_id",
        "trace_id",
        "ref_id",
        "technical_table_unit_id",
        "table_row_id",
        "figure_id",
        "description_id",
        "structure_id",
        "domain_unit_id",
        "block_id",
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
    target: str,
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
            "target": target,
            "file": file,
            "line": line,
            "record_id": record_id,
            "field": field,
            "message": message,
        }
    )


def _read_jsonl(
    path: Path,
    *,
    file_name: str,
    findings: list[dict[str, Any]],
    required: bool = False,
) -> tuple[list[tuple[int, dict[str, Any]]], dict[str, Any]]:
    summary = {"file": file_name, "exists": path.exists(), "record_count": 0}
    if not path.exists():
        if required:
            _add_finding(
                findings,
                severity="error",
                code="missing_required_file",
                target="common",
                file=file_name,
                message=f"Missing required file: {file_name}.",
            )
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
                target="common",
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
                target="common",
                file=file_name,
                line=line_number,
                field="$",
                message="JSONL record must be an object.",
            )
            continue
        records.append((line_number, payload))
    summary["record_count"] = len(records)
    return records, summary


def _read_json(
    path: Path,
    *,
    file_name: str,
    findings: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    summary = {"file": file_name, "exists": path.exists(), "record_count": 0}
    if not path.exists():
        return None, summary
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _add_finding(
            findings,
            severity="error",
            code="invalid_json",
            target="common",
            file=file_name,
            field="$",
            message=f"Invalid JSON document: {exc.msg}.",
        )
        return None, summary
    if not isinstance(payload, dict):
        _add_finding(
            findings,
            severity="error",
            code="json_document_not_object",
            target="common",
            file=file_name,
            field="$",
            message="JSON document must be an object.",
        )
        return None, summary
    summary["record_count"] = 1
    return payload, summary


def _validate_bbox(
    value: Any,
    *,
    findings: list[dict[str, Any]],
    file_name: str,
    line: int,
    record_id: str | None,
    field: str,
    required: bool,
) -> None:
    if value is None and not required:
        return
    if not isinstance(value, list) or len(value) != 4 or not all(_is_number(item) for item in value):
        _add_finding(
            findings,
            severity="error",
            code="invalid_bbox",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field=field,
            message=f"{field} must be a four-number list or null when optional.",
        )


def _validate_required_fields(
    record: dict[str, Any],
    *,
    required_fields: set[str],
    findings: list[dict[str, Any]],
    file_name: str,
    line: int,
    record_id: str | None,
) -> None:
    missing = sorted(field for field in required_fields if field not in record)
    if missing:
        _add_finding(
            findings,
            severity="error",
            code="missing_required_field",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field=",".join(missing),
            message=f"Missing required {file_name} fields: {', '.join(missing)}.",
        )


def _validate_string_value(
    value: Any,
    *,
    findings: list[dict[str, Any]],
    file_name: str,
    line: int,
    record_id: str | None,
    field: str,
    required: bool = True,
) -> None:
    if value is None and not required:
        return
    if not isinstance(value, str) or (required and not value.strip()):
        _add_finding(
            findings,
            severity="error",
            code="invalid_string_field",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field=field,
            message=f"{field} must be a {'non-empty ' if required else ''}string.",
        )


def _validate_string_list_value(
    value: Any,
    *,
    findings: list[dict[str, Any]],
    file_name: str,
    line: int,
    record_id: str | None,
    field: str,
) -> None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _add_finding(
            findings,
            severity="error",
            code="invalid_string_list_field",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field=field,
            message=f"{field} must be a list of strings.",
        )


def _validate_int_value(
    value: Any,
    *,
    findings: list[dict[str, Any]],
    file_name: str,
    line: int,
    record_id: str | None,
    field: str,
    positive: bool = False,
) -> None:
    if not _is_int(value) or (positive and value < 1):
        _add_finding(
            findings,
            severity="error",
            code="invalid_integer_field",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field=field,
            message=f"{field} must be {'a positive ' if positive else 'an '}integer.",
        )


def _validate_page_range_value(
    value: Any,
    *,
    findings: list[dict[str, Any]],
    file_name: str,
    line: int,
    record_id: str | None,
    field: str = "page_range",
) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(_is_int(page) and page >= 1 for page in value)
        or (isinstance(value, list) and len(value) == 2 and value[0] > value[1])
    ):
        _add_finding(
            findings,
            severity="error",
            code="invalid_page_range",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field=field,
            message=f"{field} must be [start, end] positive integers with start <= end.",
        )


def _validate_source_refs(
    value: Any,
    *,
    findings: list[dict[str, Any]],
    file_name: str,
    line: int,
    record_id: str | None,
    field: str = "source_refs",
) -> None:
    if not isinstance(value, list) or not value:
        _add_finding(
            findings,
            severity="error",
            code="missing_source_refs",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field=field,
            message=f"{field} must be a non-empty list.",
        )
        return
    for index, ref in enumerate(value, start=1):
        ref_field = f"{field}[{index}]"
        if not isinstance(ref, dict):
            _add_finding(
                findings,
                severity="error",
                code="source_ref_not_object",
                target="common",
                file=file_name,
                line=line,
                record_id=record_id,
                field=ref_field,
                message="source_refs entries must be objects.",
            )
            continue
        for required_field in ("source_type", "source_id", "page"):
            required_value = ref.get(required_field)
            if _is_missing(required_value):
                _add_finding(
                    findings,
                    severity="error",
                    code="incomplete_source_ref",
                    target="common",
                    file=file_name,
                    line=line,
                    record_id=record_id,
                    field=f"{ref_field}.{required_field}",
                    message=f"source_refs entries must include {required_field}.",
                )
        page = ref.get("page")
        if not _is_missing(page) and (not _is_int(page) or page < 1):
            _add_finding(
                findings,
                severity="error",
                code="invalid_source_ref_page",
                target="common",
                file=file_name,
                line=line,
                record_id=record_id,
                field=f"{ref_field}.page",
                message="source_refs page must be a positive integer.",
            )


def _source_ref_types(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(ref.get("source_type")) for ref in value if isinstance(ref, dict) and not _is_missing(ref.get("source_type"))}


def _validate_bool_value(
    value: Any,
    *,
    findings: list[dict[str, Any]],
    file_name: str,
    line: int,
    record_id: str | None,
    field: str,
) -> None:
    if not isinstance(value, bool):
        _add_finding(
            findings,
            severity="error",
            code="invalid_boolean_field",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field=field,
            message=f"{field} must be a boolean.",
        )


def _validate_visual_chunk_contract(
    *,
    record: dict[str, Any],
    findings: list[dict[str, Any]],
    line: int,
    record_id: str | None,
) -> None:
    chunk_type = record.get("chunk_type")
    if chunk_type not in VISUAL_CHUNK_TYPES:
        return
    file_name = RETRIEVAL_CHUNKS
    source_types = _source_ref_types(record.get("source_refs"))
    required_source_types = VISUAL_CHUNK_REQUIRED_SOURCE_TYPES[str(chunk_type)]
    missing_required_types = sorted(
        required
        for required in required_source_types
        if required not in source_types and not (required in FIGURE_SOURCE_TYPES and source_types & FIGURE_SOURCE_TYPES)
    )
    if missing_required_types:
        _add_finding(
            findings,
            severity="error",
            code="missing_visual_source_ref",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field="source_refs",
            message=f"{chunk_type} chunks must include source_refs for: {', '.join(missing_required_types)}.",
        )
    if "generated_text" in record:
        _validate_bool_value(
            record.get("generated_text"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
            field="generated_text",
        )
    if "derived_from_context" in record:
        _validate_bool_value(
            record.get("derived_from_context"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
            field="derived_from_context",
        )
    if chunk_type == "figure_description":
        if record.get("generated_text") is not True:
            _add_finding(
                findings,
                severity="error",
                code="missing_generated_text_flag",
                target="common",
                file=file_name,
                line=line,
                record_id=record_id,
                field="generated_text",
                message="figure_description chunks must carry generated_text=true.",
            )
        if record.get("generation_strategy") != FIGURE_DESCRIPTION_GENERATION_STRATEGY:
            _add_finding(
                findings,
                severity="error",
                code="invalid_generation_strategy",
                target="common",
                file=file_name,
                line=line,
                record_id=record_id,
                field="generation_strategy",
                message=(
                    "figure_description chunks must use "
                    f"{FIGURE_DESCRIPTION_GENERATION_STRATEGY} generation_strategy."
                ),
            )


def _validate_retrieval_chunk_record(
    *,
    line: int,
    record: dict[str, Any],
    findings: list[dict[str, Any]],
    seen_chunk_ids: set[str],
) -> None:
    file_name = RETRIEVAL_CHUNKS
    record_id = _record_id(record)
    missing = sorted(field for field in RETRIEVAL_REQUIRED_FIELDS if field not in record)
    if missing:
        _add_finding(
            findings,
            severity="error",
            code="missing_required_field",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field=",".join(missing),
            message=f"Missing required retrieval chunk fields: {', '.join(missing)}.",
        )

    chunk_id = record.get("chunk_id")
    if not isinstance(chunk_id, str) or not chunk_id.strip():
        _add_finding(
            findings,
            severity="error",
            code="invalid_chunk_id",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field="chunk_id",
            message="chunk_id must be a non-empty string.",
        )
    elif chunk_id in seen_chunk_ids:
        _add_finding(
            findings,
            severity="error",
            code="duplicate_chunk_id",
            target="common",
            file=file_name,
            line=line,
            record_id=chunk_id,
            field="chunk_id",
            message=f"Duplicate chunk_id: {chunk_id}.",
        )
    else:
        seen_chunk_ids.add(chunk_id)

    if record.get("schema_version") != SCHEMA_VERSION:
        _add_finding(
            findings,
            severity="error",
            code="schema_version_mismatch",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field="schema_version",
            message="schema_version must be 1.0.",
        )

    source_sha256 = record.get("source_sha256")
    if not isinstance(source_sha256, str) or not HEX_SHA256_RE.fullmatch(source_sha256):
        _add_finding(
            findings,
            severity="error",
            code="invalid_source_sha256",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field="source_sha256",
            message="source_sha256 must be a lowercase SHA-256 hex string.",
        )

    for field in (
        "chunk_index",
        "retrieval_priority",
        "char_count",
        "token_estimate",
        "embedding_token_estimate",
        "source_record_count",
    ):
        if field in record and not _is_int(record.get(field)):
            _add_finding(
                findings,
                severity="error",
                code="invalid_integer_field",
                target="common",
                file=file_name,
                line=line,
                record_id=record_id,
                field=field,
                message=f"{field} must be an integer.",
            )

    chunk_index = record.get("chunk_index")
    if _is_int(chunk_index) and chunk_index != line:
        _add_finding(
            findings,
            severity="warning",
            code="chunk_index_line_mismatch",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field="chunk_index",
            message="chunk_index should match deterministic JSONL order.",
        )

    for field in (
        "chunk_type",
        "text",
        "embedding_text",
        "embedding_text_strategy",
        "section_path",
        "chunk_group_id",
        "source_dedupe_key",
        "chunk_boundary_policy",
        "relationship_strategy",
    ):
        if field in record and not isinstance(record.get(field), str):
            _add_finding(
                findings,
                severity="error",
                code="invalid_string_field",
                target="common",
                file=file_name,
                line=line,
                record_id=record_id,
                field=field,
                message=f"{field} must be a string.",
            )

    if (
        isinstance(record.get("text"), str)
        and record.get("char_count") is not None
        and record.get("char_count") != len(record["text"])
    ):
        _add_finding(
            findings,
            severity="warning",
            code="char_count_mismatch",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field="char_count",
            message="char_count does not match text length.",
        )

    _validate_page_range_value(
        record.get("page_range"),
        findings=findings,
        file_name=file_name,
        line=line,
        record_id=record_id,
    )

    for field in ("heading_path", "semantic_types", "chunk_boundary_reasons"):
        value = record.get(field)
        if field in record and (not isinstance(value, list) or not all(isinstance(item, str) for item in value)):
            _add_finding(
                findings,
                severity="error",
                code="invalid_string_list_field",
                target="common",
                file=file_name,
                line=line,
                record_id=record_id,
                field=field,
                message=f"{field} must be a list of strings.",
            )
    if record.get("normative_strength") is not None and not isinstance(record.get("normative_strength"), str):
        _add_finding(
            findings,
            severity="error",
            code="invalid_normative_strength",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field="normative_strength",
            message="normative_strength must be a string or null.",
        )
    _validate_bbox(
        record.get("bbox"),
        findings=findings,
        file_name=file_name,
        line=line,
        record_id=record_id,
        field="bbox",
        required=False,
    )
    if "source_refs" in record:
        _validate_source_refs(
            record.get("source_refs"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
        )
    _validate_visual_chunk_contract(record=record, findings=findings, line=line, record_id=record_id)
    for field in RELATIONSHIP_ID_FIELDS:
        if field in record and not isinstance(record.get(field), str):
            _add_finding(
                findings,
                severity="error",
                code="invalid_relationship_id_field",
                target="common",
                file=file_name,
                line=line,
                record_id=record_id,
                field=field,
                message=f"{field} must be a string chunk id when present.",
            )
    related_chunk_ids = record.get("related_chunk_ids")
    if "related_chunk_ids" in record and (
        not isinstance(related_chunk_ids, list) or not all(isinstance(item, str) for item in related_chunk_ids)
    ):
        _add_finding(
            findings,
            severity="error",
            code="invalid_related_chunk_ids",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field="related_chunk_ids",
            message="related_chunk_ids must be a list of string chunk ids.",
        )


def _validate_chunk_relationship_targets(
    records: list[tuple[int, dict[str, Any]]],
    *,
    findings: list[dict[str, Any]],
) -> None:
    chunk_ids = {str(record.get("chunk_id")) for _, record in records if isinstance(record.get("chunk_id"), str)}
    for line, record in records:
        record_id = _record_id(record)
        for field in RELATIONSHIP_ID_FIELDS:
            value = record.get(field)
            if not isinstance(value, str):
                continue
            if value not in chunk_ids:
                _add_finding(
                    findings,
                    severity="error",
                    code="relationship_target_missing",
                    target="common",
                    file=RETRIEVAL_CHUNKS,
                    line=line,
                    record_id=record_id,
                    field=field,
                    message=f"{field} references missing chunk id: {value}.",
                )
        related_chunk_ids = record.get("related_chunk_ids")
        if not isinstance(related_chunk_ids, list):
            continue
        for related_index, value in enumerate(related_chunk_ids, start=1):
            if not isinstance(value, str):
                continue
            if value not in chunk_ids:
                _add_finding(
                    findings,
                    severity="error",
                    code="relationship_target_missing",
                    target="common",
                    file=RETRIEVAL_CHUNKS,
                    line=line,
                    record_id=record_id,
                    field=f"related_chunk_ids[{related_index}]",
                    message=f"related_chunk_ids references missing chunk id: {value}.",
                )


def _json_metadata_size(value: dict[str, Any]) -> int | None:
    try:
        return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    except (TypeError, ValueError):
        return None


def _openai_metadata(record: dict[str, Any]) -> dict[str, Any]:
    page_range = record.get("page_range") if isinstance(record.get("page_range"), list) else []
    return {
        "chunk_type": record.get("chunk_type"),
        "section_path": record.get("section_path"),
        "page_start": page_range[0] if len(page_range) == 2 else None,
        "page_end": page_range[1] if len(page_range) == 2 else None,
        "source_refs": record.get("source_refs"),
        "semantic_types": record.get("semantic_types"),
        "retrieval_priority": record.get("retrieval_priority"),
        "token_estimate": record.get("token_estimate"),
        "embedding_token_estimate": record.get("embedding_token_estimate"),
        "source_dedupe_key": record.get("source_dedupe_key"),
        "merged_source_chunk_ids": record.get("merged_source_chunk_ids"),
        "previous_chunk_id": record.get("previous_chunk_id"),
        "next_chunk_id": record.get("next_chunk_id"),
        "section_anchor_chunk_id": record.get("section_anchor_chunk_id"),
        "related_chunk_ids": record.get("related_chunk_ids"),
        "relationship_strategy": record.get("relationship_strategy"),
        "schema_version": record.get("schema_version"),
        "source_sha256": record.get("source_sha256"),
        "generated_text": record.get("generated_text"),
        "generation_strategy": record.get("generation_strategy"),
        "derived_from_context": record.get("derived_from_context"),
    }


def _azure_metadata(record: dict[str, Any]) -> dict[str, Any]:
    page_range = record.get("page_range") if isinstance(record.get("page_range"), list) else []
    try:
        source_refs_json = json.dumps(record.get("source_refs"), ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        source_refs_json = None
    return {
        "id": record.get("chunk_id"),
        "chunk_type": record.get("chunk_type"),
        "section_path": record.get("section_path"),
        "semantic_types": record.get("semantic_types"),
        "page_start": page_range[0] if len(page_range) == 2 else None,
        "page_end": page_range[1] if len(page_range) == 2 else None,
        "retrieval_priority": record.get("retrieval_priority"),
        "token_estimate": record.get("token_estimate"),
        "embedding_token_estimate": record.get("embedding_token_estimate"),
        "source_dedupe_key": record.get("source_dedupe_key"),
        "merged_source_chunk_ids": record.get("merged_source_chunk_ids"),
        "previous_chunk_id": record.get("previous_chunk_id"),
        "next_chunk_id": record.get("next_chunk_id"),
        "section_anchor_chunk_id": record.get("section_anchor_chunk_id"),
        "related_chunk_ids": record.get("related_chunk_ids"),
        "relationship_strategy": record.get("relationship_strategy"),
        "source_refs_json": source_refs_json,
        "generated_text": record.get("generated_text"),
        "generation_strategy": record.get("generation_strategy"),
        "derived_from_context": record.get("derived_from_context"),
    }


def _document_metadata(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("chunk_id"),
        "source_text": record.get("text"),
        "chunk_type": record.get("chunk_type"),
        "source_refs": record.get("source_refs"),
        "section_path": record.get("section_path"),
        "page_range": record.get("page_range"),
        "semantic_types": record.get("semantic_types"),
        "retrieval_priority": record.get("retrieval_priority"),
        "token_estimate": record.get("token_estimate"),
        "embedding_token_estimate": record.get("embedding_token_estimate"),
        "source_dedupe_key": record.get("source_dedupe_key"),
        "merged_source_chunk_ids": record.get("merged_source_chunk_ids"),
        "schema_version": record.get("schema_version"),
        "source_sha256": record.get("source_sha256"),
        "previous_chunk_id": record.get("previous_chunk_id"),
        "next_chunk_id": record.get("next_chunk_id"),
        "section_anchor_chunk_id": record.get("section_anchor_chunk_id"),
        "related_chunk_ids": record.get("related_chunk_ids"),
        "relationship_strategy": record.get("relationship_strategy"),
        "generated_text": record.get("generated_text"),
        "generation_strategy": record.get("generation_strategy"),
        "derived_from_context": record.get("derived_from_context"),
    }


def _metadata_for_target(record: dict[str, Any], target: str) -> dict[str, Any]:
    if target == "azure-ai-search":
        return _azure_metadata(record)
    if target in {"langchain", "llamaindex"}:
        return _document_metadata(record)
    return _openai_metadata(record)


def _validate_target_mapping(
    *,
    target: str,
    line: int,
    record: dict[str, Any],
    findings: list[dict[str, Any]],
    metadata_max_bytes: int,
) -> None:
    file_name = RETRIEVAL_CHUNKS
    record_id = _record_id(record)
    chunk_id = record.get("chunk_id")
    text = record.get("text")
    if not isinstance(chunk_id, str) or not chunk_id.strip():
        _add_finding(
            findings,
            severity="error",
            code="target_id_not_mappable",
            target=target,
            file=file_name,
            line=line,
            record_id=record_id,
            field="chunk_id",
            message=f"{target} mapping requires a non-empty string id.",
        )
    if not isinstance(text, str) or not text.strip():
        text_field = "page_content" if target == "langchain" else "text"
        _add_finding(
            findings,
            severity="error",
            code="target_text_not_mappable",
            target=target,
            file=file_name,
            line=line,
            record_id=record_id,
            field=text_field,
            message=f"{target} mapping requires non-empty source text.",
        )

    metadata = _metadata_for_target(record, target)
    if not all(isinstance(key, str) for key in metadata):
        _add_finding(
            findings,
            severity="error",
            code="metadata_key_not_string",
            target=target,
            file=file_name,
            line=line,
            record_id=record_id,
            field="metadata",
            message="Metadata keys must be strings.",
        )
    size = _json_metadata_size(metadata)
    if size is None:
        _add_finding(
            findings,
            severity="error",
            code="metadata_not_json_serializable",
            target=target,
            file=file_name,
            line=line,
            record_id=record_id,
            field="metadata",
            message="Metadata must be deterministic JSON-serializable.",
        )
    elif size > metadata_max_bytes:
        _add_finding(
            findings,
            severity="warning",
            code="metadata_size_exceeds_limit",
            target=target,
            file=file_name,
            line=line,
            record_id=record_id,
            field="metadata",
            message=f"Metadata size {size} bytes exceeds configured {metadata_max_bytes} byte guardrail.",
        )

    if target == "azure-ai-search":
        page_range = record.get("page_range")
        if not (isinstance(page_range, list) and len(page_range) == 2 and all(_is_int(page) for page in page_range)):
            _add_finding(
                findings,
                severity="error",
                code="azure_page_fields_not_mappable",
                target=target,
                file=file_name,
                line=line,
                record_id=record_id,
                field="page_range",
                message="Azure page_start/page_end require integer page_range values.",
            )
        if not isinstance(record.get("semantic_types"), list) or not all(
            isinstance(item, str) for item in record.get("semantic_types", [])
        ):
            _add_finding(
                findings,
                severity="error",
                code="azure_semantic_types_not_mappable",
                target=target,
                file=file_name,
                line=line,
                record_id=record_id,
                field="semantic_types",
                message="Azure semantic_types must map to a string collection.",
            )


def _validate_table_row_record(
    *,
    file_name: str,
    line: int,
    record: dict[str, Any],
    findings: list[dict[str, Any]],
) -> None:
    record_id = _record_id(record)
    _validate_required_fields(
        record,
        required_fields=TABLE_ROW_REQUIRED_FIELDS,
        findings=findings,
        file_name=file_name,
        line=line,
        record_id=record_id,
    )
    for field in ("table_id", "table_row_id", "source_mode", "row_text", "rag_header_strategy"):
        if field in record:
            _validate_string_value(
                record.get(field),
                findings=findings,
                file_name=file_name,
                line=line,
                record_id=record_id,
                field=field,
            )
    for field in ("page", "table_index", "row_index", "header_depth"):
        if field in record:
            _validate_int_value(
                record.get(field),
                findings=findings,
                file_name=file_name,
                line=line,
                record_id=record_id,
                field=field,
                positive=field != "header_depth",
            )
    if "headers" in record:
        _validate_string_list_value(
            record.get("headers"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
            field="headers",
        )
    if "cells" in record and not isinstance(record.get("cells"), dict):
        _add_finding(
            findings,
            severity="error",
            code="invalid_object_field",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field="cells",
            message="cells must be an object keyed by table header.",
        )
    if "quality_score" in record and not _is_number(record.get("quality_score")):
        _add_finding(
            findings,
            severity="error",
            code="invalid_number_field",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field="quality_score",
            message="quality_score must be a number.",
        )
    if "header_confidence" in record and not _is_number(record.get("header_confidence")):
        _add_finding(
            findings,
            severity="error",
            code="invalid_number_field",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field="header_confidence",
            message="header_confidence must be a number.",
        )
    if "fallback_reasons" in record:
        _validate_string_list_value(
            record.get("fallback_reasons"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
            field="fallback_reasons",
        )
    if "bbox" in record:
        _validate_bbox(
            record.get("bbox"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
            field="bbox",
            required=False,
        )


def _validate_requirement_trace_record(
    *,
    file_name: str,
    line: int,
    record: dict[str, Any],
    findings: list[dict[str, Any]],
) -> None:
    record_id = _record_id(record)
    _validate_required_fields(
        record,
        required_fields=REQUIREMENT_TRACE_REQUIRED_FIELDS,
        findings=findings,
        file_name=file_name,
        line=line,
        record_id=record_id,
    )
    for field in ("trace_id", "normative_strength", "text", "testability_hint"):
        if field in record:
            _validate_string_value(
                record.get(field),
                findings=findings,
                file_name=file_name,
                line=line,
                record_id=record_id,
                field=field,
            )
    for field in ("requirement_id", "condition", "applicability", "exception_text"):
        if field in record:
            _validate_string_value(
                record.get(field),
                findings=findings,
                file_name=file_name,
                line=line,
                record_id=record_id,
                field=field,
                required=False,
            )
    if "trace_index" in record:
        _validate_int_value(
            record.get("trace_index"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
            field="trace_index",
            positive=True,
        )
    if "page_range" in record:
        _validate_page_range_value(
            record.get("page_range"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
        )
    if "bbox" in record:
        _validate_bbox(
            record.get("bbox"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
            field="bbox",
            required=False,
        )
    for field in ("heading_path", "dependency_refs", "classification_reasons"):
        if field in record:
            _validate_string_list_value(
                record.get(field),
                findings=findings,
                file_name=file_name,
                line=line,
                record_id=record_id,
                field=field,
            )
    if "classification_confidence" in record and not _is_number(record.get("classification_confidence")):
        _add_finding(
            findings,
            severity="error",
            code="invalid_number_field",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field="classification_confidence",
            message="classification_confidence must be a number.",
        )
    if "source_refs" in record:
        _validate_source_refs(
            record.get("source_refs"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
        )


def _validate_technical_table_record(
    *,
    file_name: str,
    line: int,
    record: dict[str, Any],
    findings: list[dict[str, Any]],
) -> None:
    record_id = _record_id(record)
    _validate_required_fields(
        record,
        required_fields=TECHNICAL_TABLE_REQUIRED_FIELDS,
        findings=findings,
        file_name=file_name,
        line=line,
        record_id=record_id,
    )
    for field in ("technical_table_unit_id", "unit_type", "table_id", "table_row_id", "text"):
        if field in record:
            _validate_string_value(
                record.get(field),
                findings=findings,
                file_name=file_name,
                line=line,
                record_id=record_id,
                field=field,
            )
    for field in NULLABLE_STRING_FIELDS:
        if field in record:
            _validate_string_value(
                record.get(field),
                findings=findings,
                file_name=file_name,
                line=line,
                record_id=record_id,
                field=field,
                required=False,
            )
    for field in ("technical_table_unit_index", "page", "row_index"):
        if field in record:
            _validate_int_value(
                record.get(field),
                findings=findings,
                file_name=file_name,
                line=line,
                record_id=record_id,
                field=field,
                positive=True,
            )
    if "raw_cells" in record and not isinstance(record.get("raw_cells"), dict):
        _add_finding(
            findings,
            severity="error",
            code="invalid_object_field",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field="raw_cells",
            message="raw_cells must be an object preserving original table cells.",
        )
    if "bbox" in record:
        _validate_bbox(
            record.get("bbox"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
            field="bbox",
            required=False,
        )
    if "source_refs" in record:
        _validate_source_refs(
            record.get("source_refs"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
        )
    if "classification_confidence" in record and not _is_number(record.get("classification_confidence")):
        _add_finding(
            findings,
            severity="error",
            code="invalid_number_field",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field="classification_confidence",
            message="classification_confidence must be a number.",
        )
    if "classification_reasons" in record:
        _validate_string_list_value(
            record.get("classification_reasons"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
            field="classification_reasons",
        )


def _validate_figure_description_record(
    *,
    file_name: str,
    line: int,
    record: dict[str, Any],
    findings: list[dict[str, Any]],
) -> None:
    record_id = _record_id(record)
    _validate_required_fields(
        record,
        required_fields=FIGURE_DESCRIPTION_REQUIRED_FIELDS,
        findings=findings,
        file_name=file_name,
        line=line,
        record_id=record_id,
    )
    for field in ("description_id", "figure_id", "text", "generation_strategy"):
        if field in record:
            _validate_string_value(
                record.get(field),
                findings=findings,
                file_name=file_name,
                line=line,
                record_id=record_id,
                field=field,
            )
    if "page" in record:
        _validate_int_value(
            record.get("page"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
            field="page",
            positive=True,
        )
    if "generated_text" in record:
        _validate_bool_value(
            record.get("generated_text"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
            field="generated_text",
        )
    if record.get("generated_text") is not True:
        _add_finding(
            findings,
            severity="error",
            code="missing_generated_text_flag",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field="generated_text",
            message="figure description sidecar records must carry generated_text=true.",
        )
    if record.get("generation_strategy") != FIGURE_DESCRIPTION_GENERATION_STRATEGY:
        _add_finding(
            findings,
            severity="error",
            code="invalid_generation_strategy",
            target="common",
            file=file_name,
            line=line,
            record_id=record_id,
            field="generation_strategy",
            message=(
                "figure description sidecar records must use "
                f"{FIGURE_DESCRIPTION_GENERATION_STRATEGY} generation_strategy."
            ),
        )
    if "source_refs" in record:
        _validate_source_refs(
            record.get("source_refs"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
        )
    if "bbox" in record:
        _validate_bbox(
            record.get("bbox"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
            field="bbox",
            required=False,
        )


def _validate_figure_structure_record(
    *,
    file_name: str,
    line: int,
    record: dict[str, Any],
    findings: list[dict[str, Any]],
) -> None:
    record_id = _record_id(record)
    _validate_required_fields(
        record,
        required_fields=FIGURE_STRUCTURE_REQUIRED_FIELDS,
        findings=findings,
        file_name=file_name,
        line=line,
        record_id=record_id,
    )
    for field in ("structure_id", "figure_id", "text", "structure_type"):
        if field in record:
            _validate_string_value(
                record.get(field),
                findings=findings,
                file_name=file_name,
                line=line,
                record_id=record_id,
                field=field,
                required=field != "structure_type",
            )
    if "page" in record:
        _validate_int_value(
            record.get("page"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
            field="page",
            positive=True,
        )
    for field in ("generated_text", "derived_from_context"):
        if field in record:
            _validate_bool_value(
                record.get(field),
                findings=findings,
                file_name=file_name,
                line=line,
                record_id=record_id,
                field=field,
            )
    if "source_refs" in record:
        _validate_source_refs(
            record.get("source_refs"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
        )
    if "bbox" in record:
        _validate_bbox(
            record.get("bbox"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
            field="bbox",
            required=False,
        )


def _validate_optional_sidecar_record(
    *,
    file_name: str,
    line: int,
    record: dict[str, Any],
    findings: list[dict[str, Any]],
) -> None:
    record_id = _record_id(record)
    if file_name == "requirement_traceability_rag.jsonl":
        _validate_requirement_trace_record(file_name=file_name, line=line, record=record, findings=findings)
    elif file_name == "technical_tables_rag.jsonl":
        _validate_technical_table_record(file_name=file_name, line=line, record=record, findings=findings)
    elif file_name == "tables_rag.jsonl":
        _validate_table_row_record(file_name=file_name, line=line, record=record, findings=findings)
    elif file_name == "figure_descriptions_rag.jsonl":
        _validate_figure_description_record(file_name=file_name, line=line, record=record, findings=findings)
    elif file_name == "figure_structures_rag.jsonl":
        _validate_figure_structure_record(file_name=file_name, line=line, record=record, findings=findings)
    elif file_name in SOURCE_REF_SIDECARS:
        id_field = SOURCE_REF_SIDECARS[file_name]
        if _is_missing(record.get(id_field)):
            _add_finding(
                findings,
                severity="error",
                code="missing_sidecar_record_id",
                target="common",
                file=file_name,
                line=line,
                record_id=record_id,
                field=id_field,
                message=f"{file_name} records must include {id_field}.",
            )
        _validate_source_refs(
            record.get("source_refs"),
            findings=findings,
            file_name=file_name,
            line=line,
            record_id=record_id,
        )
    elif file_name == "text_blocks_rag.jsonl":
        for field in TEXT_BLOCK_FIELDS:
            if _is_missing(record.get(field)):
                _add_finding(
                    findings,
                    severity="warning",
                    code="missing_text_block_provenance",
                    target="common",
                    file=file_name,
                    line=line,
                    record_id=record_id,
                    field=field,
                    message=f"text block records should include {field}.",
                )


def _is_absolute_path(value: str) -> bool:
    return bool(POSIX_ABSOLUTE_PATH_RE.search(value) or WINDOWS_ABSOLUTE_PATH_RE.search(value))


def _scan_confidential_value(
    *,
    value: Any,
    findings: list[dict[str, Any]],
    file_name: str,
    field_path: str,
    target: str = "confidential-safe",
    line: int | None = None,
    record_id: str | None = None,
    source_hash_seen: set[str],
) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            next_path = f"{field_path}.{key}" if field_path else str(key)
            _scan_confidential_value(
                value=item,
                findings=findings,
                file_name=file_name,
                field_path=next_path,
                target=target,
                line=line,
                record_id=record_id,
                source_hash_seen=source_hash_seen,
            )
        return
    if isinstance(value, list):
        for index, item in enumerate(value, start=1):
            _scan_confidential_value(
                value=item,
                findings=findings,
                file_name=file_name,
                field_path=f"{field_path}[{index}]",
                target=target,
                line=line,
                record_id=record_id,
                source_hash_seen=source_hash_seen,
            )
        return
    if not isinstance(value, str) or not value:
        return

    if _is_absolute_path(value):
        _add_finding(
            findings,
            severity="warning",
            code="confidential_absolute_path",
            target=target,
            file=file_name,
            line=line,
            record_id=record_id,
            field=field_path,
            message="Absolute local path is not confidential-safe metadata.",
        )
    if PDF_FILENAME_RE.search(value) and value != "redacted.pdf":
        _add_finding(
            findings,
            severity="warning",
            code="confidential_filename_exposed",
            target=target,
            file=file_name,
            line=line,
            record_id=record_id,
            field=field_path,
            message="PDF filename should be redacted before sharing confidential-safe metadata.",
        )
    if field_path.endswith("source_sha256") and HEX_SHA256_RE.fullmatch(value):
        key = f"{file_name}:{field_path}"
        if key not in source_hash_seen:
            source_hash_seen.add(key)
            _add_finding(
                findings,
                severity="warning",
                code="confidential_source_hash_requires_review",
                target=target,
                file=file_name,
                line=line,
                record_id=record_id,
                field=field_path,
                message="source_sha256 is useful for identity checks but requires review before sharing.",
            )
    if CUSTOMER_FIELD_RE.search(field_path):
        _add_finding(
            findings,
            severity="warning",
            code="confidential_identifier_field_requires_review",
            target=target,
            file=file_name,
            line=line,
            record_id=record_id,
            field=field_path,
            message="Customer/product/codename metadata requires review before sharing.",
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


def _expand_targets(target: str) -> list[str]:
    if target == "all":
        return list(INDEX_TARGETS)
    return [target]


def validate_index_contract(
    *,
    output_dir: Path,
    target: str = "all",
    confidential_safe: bool = False,
    metadata_max_bytes: int | None = None,
) -> dict[str, Any]:
    """Validate local RAG sidecars against offline index mapping contracts."""
    targets = _expand_targets(target)
    findings: list[dict[str, Any]] = []
    file_summaries: list[dict[str, Any]] = []
    source_hash_seen: set[str] = set()
    if not output_dir.exists():
        _add_finding(
            findings,
            severity="error",
            code="missing_output_dir",
            target="common",
            file=None,
            message=f"Output directory does not exist: {output_dir}.",
        )

    retrieval_records, retrieval_summary = _read_jsonl(
        output_dir / RETRIEVAL_CHUNKS,
        file_name=RETRIEVAL_CHUNKS,
        findings=findings,
        required=True,
    )
    file_summaries.append(retrieval_summary)

    seen_chunk_ids: set[str] = set()
    for line, record in retrieval_records:
        _validate_retrieval_chunk_record(line=line, record=record, findings=findings, seen_chunk_ids=seen_chunk_ids)
        for target_name in targets:
            _validate_target_mapping(
                target=target_name,
                line=line,
                record=record,
                findings=findings,
                metadata_max_bytes=metadata_max_bytes or DEFAULT_METADATA_LIMITS[target_name],
            )
        if confidential_safe:
            _scan_confidential_value(
                value=record,
                findings=findings,
                file_name=RETRIEVAL_CHUNKS,
                field_path="",
                line=line,
                record_id=_record_id(record),
                source_hash_seen=source_hash_seen,
            )
    _validate_chunk_relationship_targets(retrieval_records, findings=findings)

    for file_name in SIDE_CAR_FILES:
        records, summary = _read_jsonl(output_dir / file_name, file_name=file_name, findings=findings)
        file_summaries.append(summary)
        for line, record in records:
            _validate_optional_sidecar_record(file_name=file_name, line=line, record=record, findings=findings)
            if confidential_safe:
                _scan_confidential_value(
                    value=record,
                    findings=findings,
                    file_name=file_name,
                    field_path="",
                    line=line,
                    record_id=_record_id(record),
                    source_hash_seen=source_hash_seen,
                )

    for file_name in JSON_FILES:
        payload, summary = _read_json(output_dir / file_name, file_name=file_name, findings=findings)
        file_summaries.append(summary)
        if confidential_safe and payload is not None:
            _scan_confidential_value(
                value=payload,
                findings=findings,
                file_name=file_name,
                field_path="",
                source_hash_seen=source_hash_seen,
            )

    if confidential_safe:
        _add_finding(
            findings,
            severity="info",
            code="text_redaction_not_performed",
            target="confidential-safe",
            file=None,
            field="text",
            message="Confidential-safe validation does not anonymize source text.",
        )

    sorted_findings = _sort_findings(findings)
    error_count = sum(1 for finding in sorted_findings if finding["severity"] == "error")
    warning_count = sum(1 for finding in sorted_findings if finding["severity"] == "warning")
    info_count = sum(1 for finding in sorted_findings if finding["severity"] == "info")
    status = "failed" if error_count else ("warning" if warning_count else "passed")
    checked_files = sum(1 for summary in file_summaries if summary["exists"])
    checked_records = sum(int(summary["record_count"]) for summary in file_summaries)
    report = {
        "schema_version": SCHEMA_VERSION,
        "purpose": "rag_index_contract_validation",
        "status": status,
        "passed": error_count == 0,
        "output_dir": str(output_dir),
        "targets": targets,
        "summary": {
            "checked_files": checked_files,
            "checked_records": checked_records,
            "error_count": error_count,
            "warning_count": warning_count,
            "info_count": info_count,
        },
        "files": _file_summaries(file_summaries, sorted_findings),
        "findings": sorted_findings,
    }
    return IndexContractReport.model_validate(report).model_dump(mode="json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate pdf2md RAG sidecars for offline indexer contracts.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target", choices=ALL_TARGETS, default="all")
    parser.add_argument("--report-file", type=Path, default=None)
    parser.add_argument("--confidential-safe", action="store_true")
    parser.add_argument("--metadata-max-bytes", type=int, default=None)
    parser.add_argument("--fail-on-warning", action="store_true")
    parser.add_argument("--fail-on-error", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_index_contract(
        output_dir=args.output_dir,
        target=args.target,
        confidential_safe=args.confidential_safe,
        metadata_max_bytes=args.metadata_max_bytes,
    )
    report_path = args.report_file or args.output_dir / REPORT_FILENAME
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = report["summary"]
    print(
        "Index contract validation: "
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
