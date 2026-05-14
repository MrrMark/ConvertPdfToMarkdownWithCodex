from __future__ import annotations

import json
import re
from typing import Any

from pdf2md.serializers.rag_tables import flatten_rag_table_records, normalize_rag_table_payload


BIT_RANGE_PATTERN = re.compile(r"^\s*(?:bits?\s*)?(?P<bits>\d+(?::\d+)?)\s*$", re.IGNORECASE)
HEX_VALUE_PATTERN = re.compile(r"\b(?:0x[0-9a-f]+|[0-9a-f]+h)\b", re.IGNORECASE)
REQ_ID_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{1,12}(?:-[A-Z0-9]{1,12})*-\d+\b")

TECHNICAL_HEADER_HINTS = {
    "access",
    "address",
    "bit",
    "bits",
    "byte",
    "command",
    "default",
    "description",
    "dword",
    "field",
    "feature",
    "identifier",
    "log",
    "meaning",
    "method",
    "name",
    "object",
    "opcode",
    "parameter",
    "protocolid",
    "register",
    "reset",
    "security",
    "securityfield",
    "securitydescription",
    "status",
    "uid",
    "value",
}


def _clean_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _cell(cells: dict[str, Any], *names: str) -> str | None:
    by_clean_key = {_clean_key(key): value for key, value in cells.items()}
    for name in names:
        value = by_clean_key.get(_clean_key(name))
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _header_hints(headers: list[Any]) -> set[str]:
    hints: set[str] = set()
    for header in headers:
        for token in re.findall(r"[A-Za-z]+", str(header).lower()):
            if token in TECHNICAL_HEADER_HINTS:
                hints.add(token)
    return hints


def _page(record: dict[str, Any]) -> int:
    try:
        return int(record.get("page") or 0)
    except (TypeError, ValueError):
        return 0


def _unit_type(headers: list[Any], cells: dict[str, Any], row_text: str) -> tuple[str | None, list[str]]:
    hints = _header_hints(headers)
    reasons = [f"header_{hint}" for hint in sorted(hints)]
    command = _cell(cells, "Command", "Command Name", "Name")
    opcode = _cell(cells, "Opcode", "Command Opcode")
    field = _cell(cells, "Field", "Field Name", "Parameter", "Security Field")
    bits = _cell(cells, "Bits", "Bit", "Bit Range")
    log_identifier = _cell(cells, "Log Identifier", "LID", "Log Page", "Identifier")
    feature_identifier = _cell(cells, "Feature Identifier", "FID", "Feature")
    register = _cell(cells, "Register", "Register Name")
    method = _cell(cells, "Method", "Method ID")
    security_object = _cell(cells, "Object", "Object ID")
    authority = _cell(cells, "Authority")
    uid = _cell(cells, "UID", "Protocol ID", "ProtocolID")
    security_field = _cell(cells, "Security Field")
    value = _cell(cells, "Value", "Status", "Code")

    if command and opcode:
        return "command_opcode", reasons + ["command_and_opcode"]
    if opcode:
        return "opcode", reasons + ["opcode"]
    if method and {"method", "uid", "protocolid"} & hints:
        return "security_method", reasons + ["security_method_header"]
    if security_object and {"object", "uid", "protocolid"} & hints:
        return "security_object", reasons + ["security_object_header"]
    if authority and {"authority", "uid"} & hints:
        return "security_authority", reasons + ["security_authority_header"]
    if security_field and {"securityfield", "security", "bits", "field"} & hints:
        return "security_field", reasons + ["security_field_header"]
    if uid and {"uid", "object", "protocolid"} & hints and _cell(cells, "Description", "Security Description"):
        return "security_object", reasons + ["security_uid_header"]
    if log_identifier and HEX_VALUE_PATTERN.search(log_identifier):
        return "log_page", reasons + ["log_identifier"]
    if feature_identifier and HEX_VALUE_PATTERN.search(feature_identifier):
        return "feature_identifier", reasons + ["feature_identifier"]
    if register or ("register" in hints and field):
        return "register_field", reasons + ["register_header"]
    if field and bits and BIT_RANGE_PATTERN.search(bits):
        return "bitfield", reasons + ["field_and_bits"]
    if value and _cell(cells, "Description", "Meaning"):
        return "enum_value", reasons + ["value_description"]
    if REQ_ID_PATTERN.search(row_text):
        return "requirement_row", reasons + ["requirement_id_pattern"]
    if len(hints) >= 2 and (field or value or command):
        return "technical_parameter", reasons + ["technical_header_set"]
    return None, reasons


def _requirement_ref(cells: dict[str, Any], row_text: str) -> str | None:
    explicit = _cell(cells, "Requirement ID", "Requirement", "Req ID", "ID")
    if explicit and REQ_ID_PATTERN.search(explicit):
        return REQ_ID_PATTERN.search(explicit).group(0)  # type: ignore[union-attr]
    match = REQ_ID_PATTERN.search(row_text)
    return match.group(0) if match else None


def build_technical_table_records(rag_tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build typed technical table sidecar rows without changing original table text."""
    records: list[dict[str, Any]] = []
    for row in flatten_rag_table_records(normalize_rag_table_payload(rag_tables)):
        headers = row.get("headers")
        cells = row.get("cells")
        row_text = str(row.get("row_text") or "").strip()
        if not isinstance(headers, list) or not isinstance(cells, dict) or not row_text:
            continue
        unit_type, reasons = _unit_type(headers, cells, row_text)
        if unit_type is None:
            continue
        page = _page(row)
        index = len(records) + 1
        bit_range = _cell(cells, "Bits", "Bit", "Bit Range")
        record = {
            "technical_table_unit_id": f"tech-table-{index:06d}",
            "technical_table_unit_index": index,
            "unit_type": unit_type,
            "page": page,
            "table_id": row.get("table_id"),
            "table_row_id": row.get("table_row_id"),
            "row_index": row.get("row_index"),
            "text": row_text,
            "raw_cells": cells,
            "bit_range": bit_range,
            "field_name": _cell(cells, "Field", "Field Name", "Parameter", "Name", "Security Field"),
            "value": _cell(cells, "Value", "Status", "Code", "UID", "Protocol ID", "ProtocolID"),
            "meaning": _cell(cells, "Description", "Meaning", "Security Description", "Requirement Description"),
            "reset_default": _cell(cells, "Reset", "Default", "Reset Default"),
            "access": _cell(cells, "Access", "Attributes"),
            "requirement_ref": _requirement_ref(cells, row_text),
            "opcode": _cell(cells, "Opcode", "Command Opcode"),
            "command": _cell(cells, "Command", "Command Name"),
            "log_identifier": _cell(cells, "Log Identifier", "LID", "Log Page", "Identifier"),
            "feature_identifier": _cell(cells, "Feature Identifier", "FID", "Feature"),
            "bbox": row.get("bbox"),
            "source_refs": [
                {
                    "source_type": "table_row",
                    "source_id": row.get("table_row_id"),
                    "page": page,
                    "table_id": row.get("table_id"),
                    "row_index": row.get("row_index"),
                    "bbox": row.get("bbox"),
                }
            ],
            "classification_confidence": 0.9
            if unit_type
            in {
                "command_opcode",
                "bitfield",
                "security_method",
                "security_object",
                "security_authority",
                "security_field",
            }
            else 0.84,
            "classification_reasons": sorted(dict.fromkeys(reasons)),
        }
        records.append(record)
    return records


def serialize_technical_tables_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
