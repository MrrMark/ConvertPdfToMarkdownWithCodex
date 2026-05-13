from __future__ import annotations

import json
import re
from typing import Any

from pdf2md.models import DomainAdapterMode
from pdf2md.serializers.rag_tables import flatten_rag_table_records, normalize_rag_table_payload


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


def _known_nvme_row(record: dict[str, Any]) -> bool:
    headers = record.get("headers")
    cells = record.get("cells")
    if not isinstance(headers, list) or not isinstance(cells, dict):
        return False
    normalized_headers = {_clean_key(str(header)) for header in headers}
    return len(normalized_headers & NVME_HEADER_TOKENS) >= 2


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


def _page(record: dict[str, Any]) -> int:
    try:
        return int(record.get("page") or 0)
    except (TypeError, ValueError):
        return 0


def build_domain_units(
    *,
    domain_adapter: DomainAdapterMode | str,
    rag_tables: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build opt-in domain-specific RAG records from deterministic table provenance."""
    if not isinstance(domain_adapter, DomainAdapterMode):
        domain_adapter = DomainAdapterMode(domain_adapter)
    if domain_adapter is DomainAdapterMode.NONE:
        return []
    if domain_adapter is not DomainAdapterMode.NVME:
        return []

    records: list[dict[str, Any]] = []
    for table_row in flatten_rag_table_records(normalize_rag_table_payload(rag_tables)):
        if not _known_nvme_row(table_row):
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
                "domain": "nvme",
                "unit_type": unit_type,
                "name": name,
                "value": value,
                "description": description,
                "text": str(table_row.get("row_text") or "").strip(),
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
    return records


def serialize_domain_units_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
