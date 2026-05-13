from __future__ import annotations

import json
import re
from typing import Any

from pdf2md.models import DomainAdapterMode
from pdf2md.serializers.rag_tables import flatten_rag_table_records, normalize_rag_table_payload
from pdf2md.serializers.rag_technical_tables import build_technical_table_records


NVME_HEADER_TOKENS = {
    "bits",
    "command",
    "description",
    "field",
    "name",
    "opcode",
    "parameter",
    "value",
}
PCIE_HEADER_TOKENS = {
    "access",
    "address",
    "bits",
    "capability",
    "description",
    "field",
    "offset",
    "register",
    "value",
}
OCP_HEADER_TOKENS = {
    "description",
    "optional",
    "requirement",
    "requirementid",
    "ssd",
}
TCG_HEADER_TOKENS = {
    "authority",
    "bytes",
    "description",
    "field",
    "method",
    "object",
    "protocolid",
    "uid",
    "value",
}


def _clean_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _cell_value(cells: dict[str, Any], *names: str) -> str | None:
    by_clean_key = {_clean_key(key): value for key, value in cells.items()}
    for name in names:
        value = by_clean_key.get(_clean_key(name))
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _known_domain_row(record: dict[str, Any], tokens: set[str]) -> bool:
    headers = record.get("headers")
    cells = record.get("cells")
    if not isinstance(headers, list) or not isinstance(cells, dict):
        return False
    normalized_headers = {_clean_key(str(header)) for header in headers}
    return len(normalized_headers & tokens) >= 2


def _unit_from_row(record: dict[str, Any]) -> tuple[str, str, str | None, str | None, list[str]] | None:
    cells = record.get("cells")
    if not isinstance(cells, dict):
        return None
    command = _cell_value(cells, "Command", "Name")
    opcode = _cell_value(cells, "Opcode")
    field = _cell_value(cells, "Field", "Parameter")
    bits = _cell_value(cells, "Bits")
    value = _cell_value(cells, "Value")
    description = _cell_value(cells, "Description")

    if command and opcode:
        return "command", command, opcode, description, ["nvme_command_opcode_row"]
    if opcode:
        return "opcode", opcode, opcode, description, ["nvme_opcode_row"]
    if field and bits:
        return "register_field", field, bits, description, ["nvme_register_field_row"]
    if value and description:
        return "enum_value", value, value, description, ["nvme_enum_value_row"]
    if field and description:
        return "field", field, bits or value, description, ["nvme_field_row"]
    return None


def _domain_tokens(domain_adapter: DomainAdapterMode) -> set[str]:
    if domain_adapter is DomainAdapterMode.NVME:
        return NVME_HEADER_TOKENS
    if domain_adapter is DomainAdapterMode.PCIE:
        return PCIE_HEADER_TOKENS
    if domain_adapter is DomainAdapterMode.OCP:
        return OCP_HEADER_TOKENS
    if domain_adapter is DomainAdapterMode.TCG:
        return TCG_HEADER_TOKENS
    if domain_adapter is DomainAdapterMode.CUSTOMER_REQUIREMENTS:
        return OCP_HEADER_TOKENS | {"id", "reqid", "shall", "must"}
    return set()


def _unit_from_technical_record(
    record: dict[str, Any],
    *,
    domain_adapter: DomainAdapterMode,
) -> tuple[str, str, str | None, str | None, list[str]] | None:
    unit_type = str(record.get("unit_type") or "")
    raw_cells = record.get("raw_cells")
    if not isinstance(raw_cells, dict):
        raw_cells = {}
    field = str(record.get("field_name") or "").strip()
    value = str(record.get("value") or record.get("opcode") or record.get("bit_range") or "").strip()
    description = str(record.get("meaning") or "").strip() or None
    command = str(record.get("command") or "").strip()
    log_identifier = str(record.get("log_identifier") or "").strip()
    feature_identifier = str(record.get("feature_identifier") or "").strip()
    requirement_ref = str(record.get("requirement_ref") or "").strip()

    if domain_adapter is DomainAdapterMode.NVME:
        if unit_type == "command_opcode" and command:
            return "command", command, value or None, description, ["nvme_command_opcode_row"]
        if unit_type == "log_page" and log_identifier:
            return "log_page", log_identifier, log_identifier, description, ["nvme_log_identifier_row"]
        if unit_type == "feature_identifier" and feature_identifier:
            return "feature", feature_identifier, feature_identifier, description, ["nvme_feature_identifier_row"]
        if unit_type in {"bitfield", "register_field"} and field:
            return "register_field", field, value or None, description, ["nvme_register_field_row"]

    if domain_adapter is DomainAdapterMode.PCIE:
        register = _cell_value(raw_cells, "Register", "Capability", "Field", "Name") or field
        if unit_type in {"register_field", "bitfield", "technical_parameter"} and register:
            return "register_field", register, value or None, description, ["pcie_register_or_capability_row"]

    if domain_adapter is DomainAdapterMode.OCP:
        req_id = requirement_ref or _cell_value(raw_cells, "Requirement ID", "Requirement", "ID")
        if req_id:
            return "requirement", req_id, req_id, description, ["ocp_requirement_id_row"]

    if domain_adapter is DomainAdapterMode.TCG:
        method = _cell_value(raw_cells, "Method", "Method ID", "Object", "Authority", "Field") or field
        if method:
            return "security_method", method, value or None, description, ["tcg_security_method_or_object_row"]

    if domain_adapter is DomainAdapterMode.CUSTOMER_REQUIREMENTS:
        req_id = requirement_ref or _cell_value(raw_cells, "Requirement ID", "Req ID", "ID", "Requirement")
        if req_id:
            return "requirement", req_id, req_id, description, ["customer_requirement_id_row"]

    return None


def _page(record: dict[str, Any]) -> int:
    try:
        return int(record.get("page") or 0)
    except (TypeError, ValueError):
        return 0


def build_domain_units(
    *,
    domain_adapter: DomainAdapterMode | str,
    rag_tables: list[dict[str, Any]],
    technical_table_records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build opt-in domain-specific RAG records from deterministic table provenance."""
    if not isinstance(domain_adapter, DomainAdapterMode):
        domain_adapter = DomainAdapterMode(domain_adapter)
    if domain_adapter is DomainAdapterMode.NONE:
        return []

    records: list[dict[str, Any]] = []
    adapter_technical_records = (
        technical_table_records if technical_table_records is not None else build_technical_table_records(rag_tables)
    )
    for technical_record in adapter_technical_records:
        unit = _unit_from_technical_record(technical_record, domain_adapter=domain_adapter)
        if unit is None:
            continue
        unit_type, name, value, description, reasons = unit
        page = _page(technical_record)
        index = len(records) + 1
        records.append(
            {
                "domain_unit_id": f"domain-{domain_adapter.value}-{index:06d}",
                "domain_unit_index": index,
                "domain": domain_adapter.value,
                "adapter_profile": domain_adapter.value,
                "adapter_version": "1.0",
                "unit_type": unit_type,
                "name": name,
                "value": value,
                "description": description,
                "text": str(technical_record.get("text") or "").strip(),
                "normalized_fields": {
                    "bit_range": technical_record.get("bit_range"),
                    "opcode": technical_record.get("opcode"),
                    "log_identifier": technical_record.get("log_identifier"),
                    "feature_identifier": technical_record.get("feature_identifier"),
                    "requirement_ref": technical_record.get("requirement_ref"),
                    "access": technical_record.get("access"),
                    "reset_default": technical_record.get("reset_default"),
                },
                "source_refs": list(technical_record.get("source_refs") or []),
                "page_range": [page, page],
                "bbox": technical_record.get("bbox"),
                "heading_path": [],
                "classification_confidence": 0.9,
                "classification_reasons": reasons,
            }
        )

    for table_row in flatten_rag_table_records(normalize_rag_table_payload(rag_tables)):
        if not _known_domain_row(table_row, _domain_tokens(domain_adapter)):
            continue
        unit = _unit_from_row(table_row)
        if unit is None:
            continue
        unit_type, name, value, description, reasons = unit
        page = _page(table_row)
        index = len(records) + 1
        records.append(
            {
                "domain_unit_id": f"domain-nvme-{index:06d}",
                "domain_unit_index": index,
                "domain": domain_adapter.value,
                "adapter_profile": domain_adapter.value,
                "adapter_version": "1.0",
                "unit_type": unit_type,
                "name": name,
                "value": value,
                "description": description,
                "text": str(table_row.get("row_text") or "").strip(),
                "normalized_fields": {},
                "source_refs": [
                    {
                        "source_type": "table_row",
                        "source_id": table_row.get("table_row_id"),
                        "page": page,
                        "table_id": table_row.get("table_id"),
                        "row_index": table_row.get("row_index"),
                        "bbox": table_row.get("bbox"),
                    }
                ],
                "page_range": [page, page],
                "bbox": table_row.get("bbox"),
                "heading_path": [],
                "classification_confidence": 0.88,
                "classification_reasons": reasons,
            }
        )
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str | None]] = set()
    for record in records:
        key = (str(record.get("unit_type")), str(record.get("name")), record.get("value"))
        if key in seen:
            continue
        seen.add(key)
        record["domain_unit_id"] = f"domain-{domain_adapter.value}-{len(deduped) + 1:06d}"
        record["domain_unit_index"] = len(deduped) + 1
        deduped.append(record)
    return deduped


def serialize_domain_units_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
