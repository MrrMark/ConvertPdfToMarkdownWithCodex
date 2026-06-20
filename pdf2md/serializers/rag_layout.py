from __future__ import annotations

import json
from typing import Any

from pdf2md.models import PageResult
from pdf2md.serializers.rag_tables import normalize_rag_table_payload


LAYOUT_SCHEMA_VERSION = "1.0"


def _page_of(record: dict[str, Any]) -> int:
    try:
        return int(record.get("page") or 0)
    except (TypeError, ValueError):
        return 0


def _bbox(record: dict[str, Any]) -> list[float] | None:
    value = record.get("bbox")
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        return [float(value[0]), float(value[1]), float(value[2]), float(value[3])]
    except (TypeError, ValueError):
        return None


def _union_bboxes(boxes: list[list[float]]) -> list[float] | None:
    if not boxes:
        return None
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]


def _caption_key(text: Any) -> str:
    return " ".join(str(text or "").split()).casefold()


def _caption_blocks_by_page(text_block_records: list[dict[str, Any]]) -> dict[int, dict[str, str]]:
    captions: dict[int, dict[str, str]] = {}
    for record in text_block_records:
        if record.get("block_type") != "caption":
            continue
        key = _caption_key(record.get("text"))
        block_id = str(record.get("block_id") or "")
        if not key or not block_id:
            continue
        captions.setdefault(_page_of(record), {}).setdefault(key, block_id)
    return captions


def _text_region_refs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: int(item.get("block_index") or 0)):
        block_id = str(record.get("block_id") or "")
        if not block_id:
            continue
        refs.append(
            {
                "region_type": "text_block",
                "source_type": "text_block",
                "source_id": block_id,
                "order_index": int(record.get("block_index") or 0),
                "role": str(record.get("block_type") or "text_block"),
                "bbox": _bbox(record),
                "line_indices": list(record.get("line_indices") or []),
            }
        )
    return refs


def _table_region_refs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: int(item.get("table_index") or 0)):
        table_id = str(record.get("table_id") or "")
        if not table_id:
            continue
        refs.append(
            {
                "region_type": "table",
                "source_type": "table",
                "source_id": table_id,
                "order_index": int(record.get("table_index") or 0),
                "role": "table",
                "bbox": _bbox(record),
                "caption_present": bool(str(record.get("caption_text") or "").strip()),
                "confidence": record.get("table_confidence_v2"),
            }
        )
    return refs


def _figure_region_refs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: int(item.get("figure_index") or 0)):
        figure_id = str(record.get("figure_id") or "")
        if not figure_id:
            continue
        refs.append(
            {
                "region_type": "figure",
                "source_type": str(record.get("source_refs", [{}])[0].get("source_type") or "figure")
                if isinstance(record.get("source_refs"), list) and record.get("source_refs")
                else "figure",
                "source_id": figure_id,
                "order_index": int(record.get("figure_index") or 0),
                "role": str(record.get("figure_kind") or "figure"),
                "bbox": _bbox(record),
                "caption_present": bool(str(record.get("caption_text") or "").strip()),
                "caption_confidence": record.get("caption_confidence"),
            }
        )
    return refs


def _caption_link_refs(
    *,
    page: int,
    caption_blocks: dict[int, dict[str, str]],
    table_records: list[dict[str, Any]],
    figure_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    page_caption_blocks = caption_blocks.get(page, {})
    for table in table_records:
        caption_text = str(table.get("caption_text") or "").strip()
        table_id = str(table.get("table_id") or "")
        if not caption_text or not table_id:
            continue
        caption_block_id = page_caption_blocks.get(_caption_key(caption_text))
        links.append(
            {
                "link_type": "table_caption",
                "target_type": "table",
                "target_id": table_id,
                "caption_source_type": "text_block" if caption_block_id else "table",
                "caption_source_id": caption_block_id or table_id,
                "confidence": table.get("table_confidence_v2"),
            }
        )
    for figure in figure_records:
        caption_text = str(figure.get("caption_text") or "").strip()
        figure_id = str(figure.get("figure_id") or "")
        if not caption_text or not figure_id:
            continue
        caption_block_id = page_caption_blocks.get(_caption_key(caption_text))
        links.append(
            {
                "link_type": "figure_caption",
                "target_type": "figure",
                "target_id": figure_id,
                "caption_source_type": "text_block" if caption_block_id else "figure",
                "caption_source_id": caption_block_id or figure_id,
                "confidence": figure.get("caption_confidence"),
            }
        )
    return links


def _source_counts(region_refs: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ref in region_refs:
        source_type = str(ref.get("source_type") or "")
        if not source_type:
            continue
        counts[source_type] = counts.get(source_type, 0) + 1
    return dict(sorted(counts.items()))


def build_page_layout_records(
    *,
    selected_pages: list[int],
    page_results: dict[int, PageResult],
    text_block_records: list[dict[str, Any]],
    rag_tables: list[dict[str, Any]],
    figure_records: list[dict[str, Any]],
    source_sha256: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build page-level layout diagnostics without embedding raw page text."""
    blocks_by_page: dict[int, list[dict[str, Any]]] = {}
    for record in text_block_records:
        blocks_by_page.setdefault(_page_of(record), []).append(record)

    tables_by_page: dict[int, list[dict[str, Any]]] = {}
    for table in normalize_rag_table_payload(rag_tables):
        tables_by_page.setdefault(_page_of(table), []).append(table)

    figures_by_page: dict[int, list[dict[str, Any]]] = {}
    for record in figure_records:
        figures_by_page.setdefault(_page_of(record), []).append(record)

    caption_blocks = _caption_blocks_by_page(text_block_records)
    records: list[dict[str, Any]] = []
    for page in selected_pages:
        page_result = page_results.get(page)
        text_blocks = blocks_by_page.get(page, [])
        tables = tables_by_page.get(page, [])
        figures = figures_by_page.get(page, [])
        text_refs = _text_region_refs(text_blocks)
        table_refs = _table_region_refs(tables)
        figure_refs = _figure_region_refs(figures)
        region_refs = text_refs + table_refs + figure_refs
        bbox_by_kind = {
            "text": _union_bboxes([ref["bbox"] for ref in text_refs if isinstance(ref.get("bbox"), list)]),
            "table": _union_bboxes([ref["bbox"] for ref in table_refs if isinstance(ref.get("bbox"), list)]),
            "figure": _union_bboxes([ref["bbox"] for ref in figure_refs if isinstance(ref.get("bbox"), list)]),
        }
        content_bbox = _union_bboxes([ref["bbox"] for ref in region_refs if isinstance(ref.get("bbox"), list)])
        caption_links = _caption_link_refs(
            page=page,
            caption_blocks=caption_blocks,
            table_records=tables,
            figure_records=figures,
        )
        column_count = page_result.column_count_estimate if page_result else 1
        records.append(
            {
                "layout_id": f"page-{page:04d}-layout",
                "schema_version": LAYOUT_SCHEMA_VERSION,
                "page": page,
                "source_sha256": source_sha256,
                "reading_order_strategy": page_result.reading_order_strategy if page_result else "unknown",
                "column_count_estimate": column_count,
                "multi_column_detected": column_count > 1,
                "text_block_count": len(text_blocks),
                "heading_count": sum(1 for block in text_blocks if block.get("block_type") == "heading"),
                "caption_block_count": sum(1 for block in text_blocks if block.get("block_type") == "caption"),
                "table_count": len(tables),
                "figure_count": len(figures),
                "header_footer_suppressed_count": page_result.header_footer_suppressed_count if page_result else 0,
                "suppressed_line_count": page_result.suppressed_line_count if page_result else 0,
                "dedupe_count": page_result.dedupe_count if page_result else 0,
                "line_merge_count": page_result.line_merge_count if page_result else 0,
                "content_bbox": content_bbox,
                "bbox_by_kind": bbox_by_kind,
                "region_ref_count": len(region_refs),
                "region_refs": region_refs,
                "caption_link_count": len(caption_links),
                "caption_links": caption_links,
                "source_counts": _source_counts(region_refs),
            }
        )

    metrics = {
        "page_layout_record_count": len(records),
        "layout_region_ref_count": sum(int(record.get("region_ref_count") or 0) for record in records),
        "layout_caption_link_count": sum(int(record.get("caption_link_count") or 0) for record in records),
        "layout_multi_column_page_count": sum(1 for record in records if record.get("multi_column_detected")),
        "layout_header_footer_suppressed_page_count": sum(
            1 for record in records if int(record.get("header_footer_suppressed_count") or 0) > 0
        ),
    }
    return records, metrics


def serialize_page_layout_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
