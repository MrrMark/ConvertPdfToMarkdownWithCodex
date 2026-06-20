from __future__ import annotations

import json
import re
from typing import Any

from pdf2md.serializers.rag_tables import flatten_rag_table_records, normalize_rag_table_payload
from pdf2md.serializers.rag_stable_ids import with_stable_source_metadata


BIT_RANGE_PATTERN = re.compile(r"^\s*(?:bits?\s*)?(?P<bits>\d+(?::\d+)?)\s*$", re.IGNORECASE)
HEX_VALUE_PATTERN = re.compile(r"\b(?:0x[0-9a-f]+|[0-9a-f]+h)\b", re.IGNORECASE)
REQ_ID_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{1,12}(?:-[A-Z0-9]{1,12})*-\d+\b", re.IGNORECASE)
COMMAND_DWORD_PATTERN = re.compile(r"\b(?:command\s+dword|cdw|dword|dw)\s*(?P<index>\d{1,2})\b", re.IGNORECASE)
COMMAND_CONTEXT_PATTERN = re.compile(r"(?P<name>[A-Za-z][A-Za-z0-9 /_-]{1,80}?)\s+commands?\b", re.IGNORECASE)
COMMAND_CONTEXT_SKIP = {"admin", "i/o", "io", "nvm", "nvm command set", "command set"}
COMMAND_RELATED_UNIT_TYPES = {"command_dword_field", "command_pointer_field", "status_code"}

TECHNICAL_HEADER_HINTS = {
    "access",
    "address",
    "algorithm",
    "attribute",
    "attributes",
    "bit",
    "bits",
    "byte",
    "certificate",
    "cdw",
    "command",
    "commanddword",
    "code",
    "controller",
    "default",
    "description",
    "dword",
    "field",
    "feature",
    "identifier",
    "key",
    "keyexchange",
    "locking",
    "log",
    "management",
    "meaning",
    "measurement",
    "message",
    "method",
    "name",
    "namespace",
    "offset",
    "object",
    "opcode",
    "parameter",
    "pointer",
    "property",
    "protocolid",
    "provider",
    "queue",
    "queuetype",
    "range",
    "register",
    "request",
    "response",
    "reset",
    "sc",
    "scope",
    "sct",
    "security",
    "securityfield",
    "securitydescription",
    "session",
    "slot",
    "status",
    "statuscode",
    "statuscodetype",
    "statuscodevalue",
    "state",
    "structure",
    "subsystem",
    "support",
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


def _cell_by_clean_key_suffix(cells: dict[str, Any], *suffixes: str) -> str | None:
    normalized_suffixes = tuple(_clean_key(suffix) for suffix in suffixes)
    for key, value in cells.items():
        clean_key = _clean_key(key)
        if not any(clean_key.endswith(suffix) for suffix in normalized_suffixes):
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _cell_by_clean_key_contains(cells: dict[str, Any], *tokens: str) -> str | None:
    normalized_tokens = tuple(_clean_key(token) for token in tokens)
    for key, value in cells.items():
        clean_key = _clean_key(key)
        if not all(token in clean_key for token in normalized_tokens):
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _command_name(cells: dict[str, Any]) -> str | None:
    return _cell(cells, "Command", "Command Name", "Name", "2 Command") or _cell_by_clean_key_suffix(
        cells,
        "command",
    )


def _opcode_value(cells: dict[str, Any]) -> str | None:
    return _cell(
        cells,
        "Opcode",
        "Command Opcode",
        "Combined Opcode",
        "Combined Opcode 1",
        "Combined Opcode 2",
    ) or _cell_by_clean_key_contains(cells, "combined", "opcode")


def _normalize_command_dword(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"\s+", " ", str(value).strip())
    if not text:
        return None
    match = COMMAND_DWORD_PATTERN.search(text)
    if match:
        return f"CDW{int(match.group('index'))}"
    if re.fullmatch(r"\d{1,2}", text):
        return f"CDW{int(text)}"
    return text


def _command_dword(cells: dict[str, Any], headers: list[Any], row_text: str) -> str | None:
    raw = _cell(
        cells,
        "Command Dword",
        "Command Dword Number",
        "Command DW",
        "CDW",
        "Dword",
        "DW",
    )
    normalized = _normalize_command_dword(raw)
    if normalized:
        return normalized
    for value in [*headers, *cells.keys(), row_text]:
        normalized = _normalize_command_dword(str(value))
        if normalized and normalized.upper().startswith("CDW"):
            return normalized
    return None


def _normalize_command_scope(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"\s+", " ", str(value).strip()).lower()
    if not text:
        return None
    if "admin" in text:
        return "admin"
    if "i/o" in text or "i-o" in text or re.search(r"\bio\b", text) or "nvm command" in text:
        return "io"
    return None


def _command_scope(cells: dict[str, Any], row_text: str) -> str | None:
    raw = _cell(
        cells,
        "Command Scope",
        "Command Type",
        "Queue Type",
        "Submission Queue Type",
        "Scope",
        "Command Set",
    )
    return _normalize_command_scope(raw) or _normalize_command_scope(row_text)


def _pointer_type(cells: dict[str, Any], headers: list[Any], row_text: str) -> str | None:
    raw = _cell(cells, "Pointer", "Pointer Type", "Command Pointer", "Data Pointer", "Metadata Pointer")
    candidates = [raw, *headers, *cells.keys(), row_text]
    for candidate in candidates:
        text = str(candidate or "").strip().lower()
        if re.search(r"\bmetadata\s+pointer\b", text) or "mptr" in text:
            return "metadata"
        if re.search(r"\bdata\s+pointer\b", text) or re.search(r"\bdptr\b", text):
            return "data"
    return None


def _status_code_group(status_code_type: str | None) -> str | None:
    if not status_code_type:
        return None
    text = re.sub(r"\s+", " ", str(status_code_type).strip()).lower()
    compact = _clean_key(text)
    if not compact:
        return None
    if compact in {"0", "0h", "00h", "x0", "x00", "0x0", "0x00"} or "generic" in text:
        return "generic"
    if compact in {"1", "1h", "01h", "x1", "x01", "0x1", "0x01"} or "command specific" in text:
        return "command_specific"
    if compact in {"2", "2h", "02h", "x2", "x02", "0x2", "0x02"} or (
        "media" in text and "integrity" in text
    ):
        return "media_data_integrity"
    if compact in {"3", "3h", "03h", "x3", "x03", "0x3", "0x03"} or "path" in text:
        return "path_related"
    if "vendor" in text:
        return "vendor_specific"
    if "reserved" in text:
        return "reserved"
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _description(cells: dict[str, Any]) -> str | None:
    return _cell(cells, "Description", "Definition", "Meaning", "Security Description", "Requirement Description")


def _status_code_value(cells: dict[str, Any]) -> str | None:
    return _cell(cells, "Status Code", "Status Code Value", "SC", "Code")


def _looks_like_status_value_table(
    *,
    headers: list[Any],
    cells: dict[str, Any],
    description: str | None,
    row_text: str,
) -> bool:
    value = _cell(cells, "Value")
    if not value or not HEX_VALUE_PATTERN.search(value):
        return False
    if _cell(cells, "Commands Affected"):
        return True
    header_hints = _header_hints(headers)
    text = f"{description or ''} {row_text}".lower()
    if {"status", "code"} <= header_hints or "status code" in text:
        return True
    status_terms = (
        "abort",
        "denied",
        "error",
        "exceeded",
        "failed",
        "failure",
        "invalid",
        "miscompare",
        "out of range",
        "protection",
    )
    return "command" in text and any(term in text for term in status_terms)


def _status_code_is_zero(status_code_value: str | None) -> bool:
    if not status_code_value:
        return False
    text = str(status_code_value).strip().lower()
    if text.endswith("h"):
        text = f"0x{text[:-1]}"
    try:
        return int(text, 16 if text.startswith("0x") else 10) == 0
    except ValueError:
        return False


def _status_error_class(
    *,
    status_code_group: str | None,
    status_code_value: str | None,
    description: str | None,
) -> str | None:
    text = str(description or "").lower()
    if _status_code_is_zero(status_code_value) and ("success" in text or status_code_group == "generic"):
        return "success"
    if "abort" in text:
        return "aborted_command"
    if "timeout" in text or "time out" in text:
        return "timeout"
    if "lba" in text and ("range" in text or "invalid" in text):
        return "invalid_address"
    if "invalid" in text or "unsupported" in text or "not supported" in text:
        return "invalid_request"
    if "integrity" in text or "crc" in text or "guard" in text:
        return "data_integrity"
    if "conflict" in text:
        return "conflict"
    return status_code_group if status_code_group not in {None, "reserved"} else None


def _retry_hint(
    *,
    error_class: str | None,
    status_code_value: str | None,
    description: str | None,
) -> str | None:
    text = str(description or "").lower()
    if error_class == "success" or _status_code_is_zero(status_code_value):
        return "not_applicable"
    if "do not retry" in text or "not retry" in text or "non-retry" in text:
        return "do_not_retry"
    if "correct" in text or "invalid" in text or "out of range" in text or "not supported" in text:
        return "correct_command"
    if "may retry" in text or "retryable" in text or "retry the command" in text or "retry" in text:
        return "retry_allowed"
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


def _heading_path(record: dict[str, Any]) -> list[str]:
    value = record.get("heading_path")
    return [str(item) for item in value] if isinstance(value, list) else []


def _add_hint(hints: list[str], value: str) -> None:
    if value not in hints:
        hints.append(value)


def _normalize_command_context(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"\s+", " ", str(value).strip())
    text = re.sub(r"^\d+(?:\.\d+)*\s+", "", text).strip(" :-")
    if not text:
        return None
    if text.lower() in COMMAND_CONTEXT_SKIP:
        return None
    return text


def _command_context_from_heading_path(record: dict[str, Any]) -> str | None:
    for heading in reversed(_heading_path(record)):
        text = re.sub(r"\s+", " ", str(heading).strip())
        if "command set" in text.lower():
            continue
        match = re.search(r"\bcommand\s*[:\-]\s*(?P<name>[A-Za-z][A-Za-z0-9 /_-]{1,80})", text, re.IGNORECASE)
        if match:
            context = _normalize_command_context(match.group("name"))
            if context:
                return context
        match = COMMAND_CONTEXT_PATTERN.search(text)
        if match:
            context = _normalize_command_context(match.group("name"))
            if context:
                return context
    return None


def _command_scope_key(record: dict[str, Any]) -> tuple[int, tuple[str, ...]]:
    return (_page(record), tuple(_heading_path(record)))


def _enrich_command_relationships(records: list[dict[str, Any]]) -> None:
    command_by_scope: dict[tuple[int, tuple[str, ...]], dict[str, Any]] = {}
    command_by_context: dict[tuple[int, str], dict[str, Any]] = {}

    for record in records:
        unit_type = str(record.get("unit_type") or "")
        hints = list(record.get("relationship_hints") or [])
        command = _normalize_command_context(str(record.get("command") or ""))
        if unit_type == "command_opcode" and command:
            record["command_context"] = command
            record["command_context_source"] = "explicit_command_column"
            record["related_command_unit_id"] = record.get("technical_table_unit_id")
            record["related_command_opcode"] = record.get("opcode")
            _add_hint(hints, "command_anchor")
            record["relationship_hints"] = hints
            command_by_scope[_command_scope_key(record)] = record
            command_by_context[(_page(record), command.lower())] = record
            continue

        heading_context = _command_context_from_heading_path(record)
        related = command_by_scope.get(_command_scope_key(record))
        if heading_context:
            related = command_by_context.get((_page(record), heading_context.lower()), related)
        if unit_type not in COMMAND_RELATED_UNIT_TYPES and not heading_context:
            record["relationship_hints"] = hints
            continue

        context = heading_context
        if context is None and related:
            context = _normalize_command_context(str(related.get("command_context") or ""))
        if context:
            record["command_context"] = context
            record["command_context_source"] = "heading_path" if heading_context else "previous_command_row"
            _add_hint(hints, "belongs_to_command")
        if related and context and str(related.get("command_context") or "").lower() == context.lower():
            record["related_command_unit_id"] = related.get("technical_table_unit_id")
            record["related_command_opcode"] = related.get("opcode")
        if unit_type == "command_dword_field":
            _add_hint(hints, "command_dword_layout")
        elif unit_type == "command_pointer_field":
            _add_hint(hints, "command_pointer_layout")
        elif unit_type == "status_code":
            _add_hint(hints, "status_code_taxonomy")
        record["relationship_hints"] = hints


def _unit_type(headers: list[Any], cells: dict[str, Any], row_text: str) -> tuple[str | None, list[str]]:
    hints = _header_hints(headers)
    reasons = [f"header_{hint}" for hint in sorted(hints)]
    command = _command_name(cells)
    opcode = _opcode_value(cells)
    field = _cell(
        cells,
        "Field",
        "Field Name",
        "Parameter",
        "Command Dword Field",
        "CDW Field",
        "Dword Field",
        "Pointer Field",
        "Data Pointer Field",
        "Metadata Pointer Field",
        "Queue Field",
        "Namespace Field",
        "Controller Field",
        "Data Structure Field",
        "Security Field",
    )
    bits = _cell(cells, "Bits", "Bit", "Bit Range")
    description = _description(cells)
    log_identifier = _cell(cells, "Log Identifier", "LID", "Log Page", "Log Page Identifier", "Identifier")
    feature_identifier = _cell(cells, "Feature Identifier", "FID", "Feature")
    register = _cell(cells, "Register", "Register Name", "Property")
    offset = _cell(cells, "Offset", "Address")
    status_code_type = _cell(cells, "Status Code Type", "SCT")
    status_code_value = _status_code_value(cells)
    if status_code_value is None and _looks_like_status_value_table(
        headers=headers,
        cells=cells,
        description=description,
        row_text=row_text,
    ):
        status_code_value = _cell(cells, "Value")
        status_code_type = status_code_type or (
            "Command Specific Status" if _cell(cells, "Commands Affected") else "Generic"
        )
    controller_support = _cell(cells, "Controller Support", "Controller Support Requirements")
    namespace_support = _cell(cells, "Namespace Support", "Namespace Support Requirements", "NVM Subsystem")
    support = _cell(cells, "Support", "Supported", "Support Requirement")
    scope = _cell(cells, "Scope", "NVM Subsystem")
    queue = _cell(cells, "Queue", "Queue Type")
    data_structure = _cell(cells, "Data Structure", "Structure")
    command_dword = _command_dword(cells, headers, row_text)
    pointer_type = _pointer_type(cells, headers, row_text)
    method = _cell(cells, "Method", "Method ID")
    security_object = _cell(cells, "Object", "Object ID")
    security_provider = _cell(cells, "Security Provider", "SP", "Provider")
    locking_range = _cell(cells, "Locking Range", "Range")
    key_name = _cell(cells, "Key", "Key Name", "Key Management")
    session_state = _cell(cells, "Session State", "Session", "State")
    authority = _cell(cells, "Authority")
    uid = _cell(cells, "UID", "Protocol ID", "ProtocolID")
    security_field = _cell(cells, "Security Field")
    value = _cell(cells, "Value", "Status", "Code")
    message = _cell(cells, "Message", "Message Name", "Command")
    message_code = _cell(cells, "Message Code", "Code", "Request Code", "Response Code")
    request = _cell(cells, "Request", "Request Message")
    response = _cell(cells, "Response", "Response Message")
    measurement = _cell(cells, "Measurement", "Measurement Index", "Measurement Block", "Measurement Type")
    certificate = _cell(cells, "Certificate", "Certificate Slot", "Slot")
    algorithm = _cell(cells, "Algorithm", "Algorithm Type", "Base Asym Algo", "Hash Algorithm")
    key_exchange = _cell(cells, "Key Exchange", "KeyExchange", "Key Exchange Parameter")
    session = _cell(cells, "Session", "Session State", "State")

    if command and opcode:
        return "command_opcode", reasons + ["command_and_opcode"]
    if opcode:
        return "opcode", reasons + ["opcode"]
    if message and message_code and {"message", "code"} & hints:
        return "spdm_message", reasons + ["spdm_message_code_header"]
    if request and response:
        return "spdm_request_response", reasons + ["spdm_request_response_header"]
    if measurement and "measurement" in hints:
        return "spdm_measurement", reasons + ["spdm_measurement_header"]
    if certificate and {"certificate", "slot"} & hints:
        return "spdm_certificate", reasons + ["spdm_certificate_header"]
    if algorithm and "algorithm" in hints:
        return "spdm_algorithm", reasons + ["spdm_algorithm_header"]
    if key_exchange and {"keyexchange", "key"} & hints:
        return "spdm_key_exchange", reasons + ["spdm_key_exchange_header"]
    if method and {"method", "uid", "protocolid"} & hints:
        return "security_method", reasons + ["security_method_header"]
    if security_provider and {"security", "provider", "object", "uid"} & hints:
        return "security_provider", reasons + ["security_provider_header"]
    if locking_range and {"locking", "range", "security", "field", "bits"} & hints:
        return "locking_range", reasons + ["locking_range_header"]
    if key_name and {"key", "management", "security"} & hints:
        return "key_management", reasons + ["key_management_header"]
    if session_state and {"session", "state", "security"} & hints:
        return "session_state", reasons + ["session_state_header"]
    if session and {"session", "state"} & hints:
        return "session_state", reasons + ["session_state_header"]
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
    if (status_code_type and status_code_value) or (
        status_code_value and "status" in hints and {"code", "sc"} & hints and description
    ):
        return "status_code", reasons + ["status_code_header"]
    if command_dword and (field or bits or description):
        return "command_dword_field", reasons + ["command_dword_header"]
    if pointer_type and (field or description or "pointer" in hints):
        return "command_pointer_field", reasons + ["command_pointer_header"]
    if (controller_support or namespace_support or support) and (
        description or _requirement_ref(cells, row_text) or {"support", "controller", "namespace", "subsystem"} & hints
    ):
        return "support_requirement", reasons + ["support_requirement_header"]
    if field and (queue or "queue" in hints):
        return "queue_field", reasons + ["queue_header"]
    if field and {"namespace", "subsystem"} & hints:
        return "namespace_field", reasons + ["namespace_header"]
    if field and "controller" in hints:
        return "controller_field", reasons + ["controller_header"]
    if field and (data_structure or "structure" in hints):
        return "data_structure_field", reasons + ["data_structure_header"]
    if register or ("register" in hints and field) or ((offset or {"offset", "property"} & hints) and field):
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


def build_technical_table_records(rag_tables: list[dict[str, Any]], *, source_sha256: str = "") -> list[dict[str, Any]]:
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
        status_code_type = _cell(cells, "Status Code Type", "SCT")
        status_code_value = _status_code_value(cells)
        description = _description(cells)
        if status_code_value is None and _looks_like_status_value_table(
            headers=headers,
            cells=cells,
            description=description,
            row_text=row_text,
        ):
            status_code_value = _cell(cells, "Value")
            status_code_type = status_code_type or (
                "Command Specific Status" if _cell(cells, "Commands Affected") else "Generic"
            )
        status_code_group = _status_code_group(status_code_type)
        error_class = _status_error_class(
            status_code_group=status_code_group,
            status_code_value=status_code_value,
            description=description,
        )
        controller_support = _cell(cells, "Controller Support", "Controller Support Requirements")
        namespace_support = _cell(cells, "Namespace Support", "Namespace Support Requirements", "NVM Subsystem")
        command_scope = _command_scope(cells, row_text)
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
            "field_name": _cell(
                cells,
                "Field",
                "Field Name",
                "Parameter",
                "Command Dword Field",
                "CDW Field",
                "Dword Field",
                "Pointer Field",
                "Data Pointer Field",
                "Metadata Pointer Field",
                "Queue Field",
                "Namespace Field",
                "Controller Field",
                "Data Structure Field",
                "Name",
                "Security Field",
            ),
            "value": _cell(cells, "Value", "Status", "Status Code", "SC", "Code", "UID", "Protocol ID", "ProtocolID"),
            "meaning": description,
            "reset_default": _cell(cells, "Reset", "Default", "Reset Default"),
            "access": _cell(cells, "Access", "Attributes"),
            "requirement_ref": _requirement_ref(cells, row_text),
            "opcode": _opcode_value(cells),
            "command": _command_name(cells),
            "command_dword": _command_dword(cells, headers, row_text),
            "command_scope": command_scope,
            "queue_type": command_scope,
            "pointer_type": _pointer_type(cells, headers, row_text),
            "command_context": None,
            "command_context_source": None,
            "related_command_unit_id": None,
            "related_command_opcode": None,
            "relationship_hints": [],
            "log_identifier": _cell(cells, "Log Identifier", "LID", "Log Page", "Log Page Identifier", "Identifier"),
            "feature_identifier": _cell(cells, "Feature Identifier", "FID", "Feature"),
            "register_name": _cell(cells, "Register", "Register Name", "Property"),
            "offset": _cell(cells, "Offset", "Address"),
            "status_code_type": status_code_type,
            "status_code_value": status_code_value,
            "status_code_group": status_code_group,
            "error_class": error_class,
            "retry_hint": _retry_hint(
                error_class=error_class,
                status_code_value=status_code_value,
                description=description,
            ),
            "controller_support": controller_support,
            "namespace_support": namespace_support,
            "scope": _cell(cells, "Scope", "NVM Subsystem"),
            "bbox": row.get("bbox"),
            "table_confidence_v2": row.get("table_confidence_v2"),
            "table_confidence_v2_bucket": row.get("table_confidence_v2_bucket"),
            "table_confidence_v2_reasons": row.get("table_confidence_v2_reasons", []),
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
                "command_dword_field",
                "command_pointer_field",
                "bitfield",
                "status_code",
                "queue_field",
                "namespace_field",
                "controller_field",
                "support_requirement",
                "data_structure_field",
                "security_method",
                "security_object",
                "security_authority",
                "security_field",
                "security_provider",
                "locking_range",
                "key_management",
                "session_state",
                "spdm_message",
                "spdm_request_response",
                "spdm_measurement",
                "spdm_certificate",
                "spdm_algorithm",
                "spdm_key_exchange",
                "spdm_session",
            }
            else 0.84,
            "classification_reasons": sorted(dict.fromkeys(reasons)),
        }
        heading_path = _heading_path(row)
        if heading_path:
            record["heading_path"] = heading_path
        records.append(
            with_stable_source_metadata(
                record,
                source_sha256=source_sha256,
                requirement_locator_id=str(row.get("table_row_id") or ""),
            )
        )
    _enrich_command_relationships(records)
    return records


def serialize_technical_tables_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
