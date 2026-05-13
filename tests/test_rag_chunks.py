from __future__ import annotations

import json

from pdf2md.serializers.rag_chunks import build_retrieval_chunks, serialize_retrieval_chunks_jsonl


def test_retrieval_chunks_include_text_semantic_requirement_and_table_provenance() -> None:
    text_blocks = [
        {
            "block_id": "page-0001-block-0001",
            "page": 1,
            "block_index": 1,
            "block_type": "paragraph",
            "text": "The controller shall return SUCCESS.",
            "bbox": [72.0, 80.0, 280.0, 95.0],
            "heading_path": ["1 Requirements"],
        }
    ]
    requirement = {
        "semantic_id": "page-0001-sem-0001",
        "semantic_index": 1,
        "semantic_type": "requirement",
        "text": "The controller shall return SUCCESS.",
        "source_refs": [{"source_type": "text_block", "source_id": "page-0001-block-0001", "page": 1}],
        "page_range": [1, 1],
        "bbox": [72.0, 80.0, 280.0, 95.0],
        "heading_path": ["1 Requirements"],
        "normative_strength": "required",
    }
    definition = {
        "semantic_id": "page-0001-sem-0002",
        "semantic_index": 2,
        "semantic_type": "definition",
        "text": "Controller: The component that processes commands.",
        "source_refs": [{"source_type": "text_block", "source_id": "page-0001-block-0002", "page": 1}],
        "page_range": [1, 1],
        "bbox": [72.0, 100.0, 320.0, 115.0],
        "heading_path": ["1 Requirements"],
        "normative_strength": "informative",
    }
    rag_tables = [
        {
            "page": 1,
            "table_index": 1,
            "records": [
                {
                    "page": 1,
                    "table_index": 1,
                    "row_index": 1,
                    "row_text": "Field = Status | Description = Current status",
                    "bbox": [72.0, 120.0, 420.0, 150.0],
                }
            ],
        }
    ]

    chunks = build_retrieval_chunks(
        text_block_records=text_blocks,
        semantic_units=[requirement, definition],
        requirements=[requirement],
        rag_tables=rag_tables,
    )

    assert [chunk["chunk_type"] for chunk in chunks] == [
        "text_block",
        "requirement",
        "semantic_unit",
        "table_row",
    ]
    assert chunks[0]["chunk_id"] == "chunk-000001"
    assert chunks[1]["retrieval_priority"] == 100
    assert chunks[1]["source_refs"][-1]["source_type"] == "requirement"
    assert chunks[2]["semantic_types"] == ["definition"]
    assert chunks[3]["source_refs"][0]["source_id"] == "page-0001-table-0001-row-0001"

    jsonl = serialize_retrieval_chunks_jsonl(chunks)
    assert json.loads(jsonl.splitlines()[1])["normative_strength"] == "required"
