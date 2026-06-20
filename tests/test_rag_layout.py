from __future__ import annotations

import json

from pdf2md.models import PageResult
from pdf2md.serializers.rag_layout import build_page_layout_records, serialize_page_layout_jsonl


def test_page_layout_records_keep_refs_without_raw_text() -> None:
    text_blocks = [
        {
            "block_id": "page-0001-block-0001",
            "page": 1,
            "block_index": 1,
            "block_type": "heading",
            "text": "1 Scope",
            "bbox": [72.0, 40.0, 160.0, 56.0],
            "line_indices": [1],
        },
        {
            "block_id": "page-0001-block-0002",
            "page": 1,
            "block_index": 2,
            "block_type": "caption",
            "text": "Table 1: Status fields",
            "bbox": [72.0, 90.0, 220.0, 104.0],
            "line_indices": [2],
        },
    ]
    rag_tables = [
        {
            "page": 1,
            "table_index": 1,
            "caption_text": "Table 1: Status fields",
            "bbox": [72.0, 110.0, 420.0, 180.0],
            "table_confidence_v2": 0.91,
            "records": [],
        }
    ]
    figure_records = [
        {
            "figure_id": "page-0001-figure-0001",
            "page": 1,
            "figure_index": 1,
            "figure_kind": "diagram",
            "bbox": [72.0, 220.0, 320.0, 360.0],
            "caption_text": "",
            "caption_confidence": None,
        }
    ]

    records, metrics = build_page_layout_records(
        selected_pages=[1],
        page_results={1: PageResult(page=1, reading_order_strategy="multi_column", column_count_estimate=2)},
        text_block_records=text_blocks,
        rag_tables=rag_tables,
        figure_records=figure_records,
        source_sha256="a" * 64,
    )

    assert metrics == {
        "page_layout_record_count": 1,
        "layout_region_ref_count": 4,
        "layout_caption_link_count": 1,
        "layout_multi_column_page_count": 1,
        "layout_header_footer_suppressed_page_count": 0,
    }
    record = records[0]
    assert record["layout_id"] == "page-0001-layout"
    assert record["multi_column_detected"] is True
    assert record["region_ref_count"] == 4
    assert record["caption_links"] == [
        {
            "link_type": "table_caption",
            "target_type": "table",
            "target_id": "page-0001-table-0001",
            "caption_source_type": "text_block",
            "caption_source_id": "page-0001-block-0002",
            "confidence": 0.91,
        }
    ]
    payload = json.loads(serialize_page_layout_jsonl(records).splitlines()[0])
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "1 Scope" not in serialized
    assert "Table 1: Status fields" not in serialized
    assert payload["source_counts"] == {"figure": 1, "table": 1, "text_block": 2}
