from __future__ import annotations

import json
from typing import Any


def flatten_rag_table_records(rag_tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return row-wise RAG table records in table/page order."""
    records: list[dict[str, Any]] = []
    for table in rag_tables:
        records.extend(table.get("records", []))
    return records


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
        lines.append(f"Caption: {caption}")
        lines.append("Headers: " + " | ".join(str(header) for header in headers))
        for record in table.get("records", []):
            lines.append(f"Row {record.get('row_index')}: {record.get('row_text', '')}")
        chunks.append("\n".join(lines))
    if not chunks:
        return ""
    return "\n\n".join(chunks) + "\n"
