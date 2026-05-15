from __future__ import annotations

import json
from typing import Any


HEADING_CONTEXT_KEYWORDS = ("appendix", "clause", "requirement", "vendor")


def stable_table_id(page: int, table_index: int) -> str:
    """Return the deterministic table id used by RAG sidecars."""
    return f"page-{page:04d}-table-{table_index:04d}"


def stable_table_row_id(page: int, table_index: int, row_index: int) -> str:
    """Return the deterministic table row id used by RAG sidecars."""
    return f"{stable_table_id(page, table_index)}-row-{row_index:04d}"


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_rag_table_payload(rag_tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add deterministic table and row ids without mutating extractor payloads."""
    normalized: list[dict[str, Any]] = []
    for table in rag_tables:
        page = _int_value(table.get("page"))
        table_index = _int_value(table.get("table_index"))
        table_id = str(table.get("table_id") or stable_table_id(page, table_index))
        table_copy = dict(table)
        table_copy["table_id"] = table_id
        records: list[dict[str, Any]] = []
        for record in table.get("records", []):
            record_page = _int_value(record.get("page"), page)
            record_table_index = _int_value(record.get("table_index"), table_index)
            row_index = _int_value(record.get("row_index"))
            row_table_id = str(record.get("table_id") or stable_table_id(record_page, record_table_index))
            record_copy = dict(record)
            record_copy["table_id"] = row_table_id
            record_copy["table_row_id"] = str(
                record.get("table_row_id") or stable_table_row_id(record_page, record_table_index, row_index)
            )
            records.append(record_copy)
        table_copy["records"] = records
        normalized.append(table_copy)
    return normalized


def flatten_rag_table_records(rag_tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return row-wise RAG table records in table/page order."""
    records: list[dict[str, Any]] = []
    for table in normalize_rag_table_payload(rag_tables):
        records.extend(table.get("records", []))
    return records


def _bbox_top(record: dict[str, Any]) -> float | None:
    bbox = record.get("bbox")
    if not isinstance(bbox, list) or len(bbox) < 2:
        return None
    try:
        return float(bbox[1])
    except (TypeError, ValueError):
        return None


def _heading_path(record: dict[str, Any]) -> list[str]:
    value = record.get("heading_path")
    return [str(item) for item in value] if isinstance(value, list) else []


def _heading_context_is_high_risk(heading_path: list[str]) -> bool:
    text = " ".join(heading_path).lower()
    return any(keyword in text for keyword in HEADING_CONTEXT_KEYWORDS)


def _nearest_heading_path(
    *,
    page: int,
    table_top: float | None,
    text_block_records: list[dict[str, Any]],
) -> list[str]:
    page_records = [
        record
        for record in text_block_records
        if _int_value(record.get("page")) == page and _heading_path(record)
    ]
    if not page_records:
        return []

    if table_top is not None:
        preceding = [
            (top, _int_value(record.get("block_index")), record)
            for record in page_records
            if (top := _bbox_top(record)) is not None and top <= table_top
        ]
        if preceding:
            return _heading_path(sorted(preceding, key=lambda item: (item[0], item[1]))[-1][2])

    return _heading_path(sorted(page_records, key=lambda item: _int_value(item.get("block_index")))[0])


def annotate_rag_tables_with_heading_context(
    rag_tables: list[dict[str, Any]],
    text_block_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return copies of high-risk appendix/requirement tables with inherited heading context."""
    annotated: list[dict[str, Any]] = []
    for table in normalize_rag_table_payload(rag_tables):
        page = _int_value(table.get("page"))
        heading_path = _nearest_heading_path(
            page=page,
            table_top=_bbox_top(table),
            text_block_records=text_block_records,
        )
        should_attach = _heading_context_is_high_risk(heading_path)
        table_copy = dict(table)
        records: list[dict[str, Any]] = []
        if should_attach:
            table_copy["heading_path"] = heading_path
            table_copy["heading_context_source"] = "nearest_preceding_heading"
        for record in table.get("records", []):
            record_copy = dict(record)
            if should_attach:
                record_copy["heading_path"] = heading_path
                record_copy["heading_context_source"] = "nearest_preceding_heading"
            records.append(record_copy)
        table_copy["records"] = records
        annotated.append(table_copy)
    return annotated


def serialize_rag_tables_jsonl(rag_tables: list[dict[str, Any]]) -> str:
    """Serialize row-wise RAG table records as JSONL."""
    records = flatten_rag_table_records(rag_tables)
    if not records:
        return ""
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"


def serialize_rag_tables_markdown(rag_tables: list[dict[str, Any]]) -> str:
    """Serialize tables as row-wise Markdown optimized for retrieval chunks."""
    chunks: list[str] = []
    for table in rag_tables:
        page = table.get("page")
        index = table.get("table_index")
        source = table.get("source_mode", "")
        group = table.get("continuation_group")
        caption = table.get("caption_text", "")
        headers = table.get("headers", [])
        marker = f"<!-- table-rag: page={page} index={index} source={source}"
        if group:
            marker += f" group={group}"
        marker += " -->"
        lines = [marker]
        lines.append(f"Caption: {caption}" if caption else "Caption:")
        lines.append("Headers: " + " | ".join(str(header) for header in headers))
        for record in table.get("records", []):
            lines.append(f"Row {record.get('row_index')}: {record.get('row_text', '')}")
        chunks.append("\n".join(lines))
    if not chunks:
        return ""
    return "\n\n".join(chunks) + "\n"
