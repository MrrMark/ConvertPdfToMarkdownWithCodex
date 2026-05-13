from __future__ import annotations

import json

from pdf2md.serializers.rag_chunks import (
    build_retrieval_chunk_diagnostics,
    build_retrieval_chunks,
    optimize_retrieval_chunks,
    serialize_retrieval_chunks_jsonl,
)


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
        source_sha256="a" * 64,
    )

    assert [chunk["chunk_type"] for chunk in chunks] == [
        "text_block",
        "requirement",
        "semantic_unit",
        "table_row",
    ]
    assert chunks[0]["chunk_id"] == "chunk-000001"
    assert chunks[0]["schema_version"] == "1.0"
    assert chunks[0]["source_sha256"] == "a" * 64
    assert chunks[1]["retrieval_priority"] == 100
    assert chunks[1]["source_refs"][-1]["source_type"] == "requirement"
    assert chunks[2]["semantic_types"] == ["definition"]
    assert chunks[3]["source_refs"][0]["source_id"] == "page-0001-table-0001-row-0001"
    assert chunks[0]["chunk_boundary_reasons"] == ["text_block_boundary"]
    assert chunks[0]["section_path"] == "1 Requirements"

    jsonl = serialize_retrieval_chunks_jsonl(chunks)
    assert json.loads(jsonl.splitlines()[1])["normative_strength"] == "required"


def test_retrieval_chunks_include_traceability_and_technical_table_units() -> None:
    trace = {
        "trace_id": "req-trace-000001",
        "trace_index": 1,
        "text": "The device shall report SMART status.",
        "source_refs": [{"source_type": "table_row", "source_id": "page-0001-table-0001-row-0001", "page": 1}],
        "page_range": [1, 1],
        "normative_strength": "required",
    }
    technical = {
        "technical_table_unit_id": "tech-table-000001",
        "technical_table_unit_index": 1,
        "unit_type": "log_page",
        "text": "Log Identifier = C0h | Description = SMART",
        "page": 1,
        "table_id": "page-0001-table-0001",
        "source_refs": [{"source_type": "table_row", "source_id": "page-0001-table-0001-row-0001", "page": 1}],
    }

    chunks = build_retrieval_chunks(
        text_block_records=[],
        semantic_units=[],
        requirements=[],
        rag_tables=[],
        requirement_traceability_records=[trace],
        technical_table_records=[technical],
    )

    assert [chunk["chunk_type"] for chunk in chunks] == ["requirement_trace", "technical_table"]
    assert chunks[0]["retrieval_priority"] == 98
    assert chunks[1]["semantic_types"] == ["log_page"]


def test_retrieval_chunk_diagnostics_report_length_and_duplicate_sources() -> None:
    records = [
        {"token_estimate": 8, "source_dedupe_key": "a"},
        {"token_estimate": 1024, "source_dedupe_key": "a"},
    ]

    diagnostics = build_retrieval_chunk_diagnostics(records, target_tokens=512)

    assert diagnostics == {
        "retrieval_chunk_max_token_estimate": 1024,
        "retrieval_chunk_average_token_estimate": 516.0,
        "retrieval_chunk_over_target_count": 1,
        "retrieval_chunk_duplicate_source_ref_count": 1,
    }


def test_retrieval_chunk_optimizer_splits_over_budget_chunks_and_reindexes() -> None:
    records = [
        {
            "chunk_id": "chunk-000001",
            "chunk_index": 1,
            "chunk_type": "requirement",
            "text": "The device shall preserve data. " * 10,
            "source_refs": [{"source_type": "requirement", "source_id": "req-1", "page": 1}],
            "source_dedupe_key": "req-1",
            "chunk_boundary_reasons": ["requirement_boundary"],
            "char_count": 320,
            "token_estimate": 80,
        },
        {
            "chunk_id": "chunk-000002",
            "chunk_index": 2,
            "chunk_type": "text_block",
            "text": "Short chunk.",
            "source_refs": [{"source_type": "text_block", "source_id": "block-1", "page": 1}],
            "source_dedupe_key": "block-1",
            "char_count": 12,
            "token_estimate": 3,
        },
    ]

    optimized = optimize_retrieval_chunks(records, max_tokens=16)

    assert len(optimized) > 2
    assert [record["chunk_id"] for record in optimized] == [
        f"chunk-{index:06d}" for index in range(1, len(optimized) + 1)
    ]
    split_parts = [record for record in optimized if record.get("parent_chunk_id") == "chunk-000001"]
    assert len(split_parts) == split_parts[0]["chunk_part_count"]
    assert all(record["token_estimate"] <= 16 for record in split_parts)
    assert all("token_budget_split" in record["chunk_boundary_reasons"] for record in split_parts)
    assert optimized[-1]["text"] == "Short chunk."
