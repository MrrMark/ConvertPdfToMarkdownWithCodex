from __future__ import annotations

import json

from pdf2md.serializers.rag_chunks import (
    assign_chunk_relationships,
    build_retrieval_chunk_diagnostics,
    build_retrieval_chunks,
    merge_sibling_text_chunks,
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
                    "headers": ["Field", "Value"],
                    "column_header_paths": [
                        {
                            "column_index": 1,
                            "header": "Field",
                            "path": ["Register", "Field"],
                            "path_text": "Register / Field",
                            "source": "multi_row_header",
                            "placeholder": False,
                        }
                    ],
                    "column_placeholder_header_ratio": 0.0,
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
        contextual_embedding_text=True,
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
    assert chunks[3]["context_metadata"]["column_header_paths"][0]["path_text"] == "Register / Field"
    assert "Header paths: Register / Field" in chunks[3]["embedding_text"]
    assert chunks[0]["chunk_boundary_reasons"] == ["text_block_boundary"]
    assert chunks[0]["section_path"] == "1 Requirements"
    assert len(chunks[1]["stable_source_id"]) == 40
    assert len(chunks[1]["stable_requirement_seed"]) == 40

    repeated_chunks = build_retrieval_chunks(
        text_block_records=text_blocks,
        semantic_units=[requirement, definition],
        requirements=[requirement],
        rag_tables=rag_tables,
        source_sha256="a" * 64,
        contextual_embedding_text=True,
    )
    assert repeated_chunks[1]["stable_source_id"] == chunks[1]["stable_source_id"]
    assert repeated_chunks[1]["stable_requirement_seed"] == chunks[1]["stable_requirement_seed"]

    jsonl = serialize_retrieval_chunks_jsonl(chunks)
    assert json.loads(jsonl.splitlines()[1])["normative_strength"] == "required"


def test_retrieval_chunks_keep_review_only_domain_candidates_low_priority() -> None:
    domain_candidate = {
        "domain_unit_id": "domain-spdm-000001",
        "domain_unit_index": 1,
        "domain": "spdm",
        "unit_type": "spdm_measurement",
        "candidate_status": "review_only",
        "candidate_kind": "spdm_measurement_text",
        "review_required": True,
        "review_reasons": ["text_derived_candidate", "not_table_provenance"],
        "text": "SPDM GET_MEASUREMENTS message flow",
        "normalized_fields": {
            "source_text_span": "GET_MEASUREMENTS",
            "candidate_status": "review_only",
            "candidate_kind": "spdm_measurement_text",
        },
        "source_refs": [{"source_type": "text_block", "source_id": "page-0001-block-0001", "page": 1}],
        "page_range": [1, 1],
        "bbox": [72.0, 72.0, 300.0, 90.0],
        "heading_path": ["SPDM Messages"],
    }

    chunks = build_retrieval_chunks(
        text_block_records=[],
        semantic_units=[],
        requirements=[],
        rag_tables=[],
        domain_units=[domain_candidate],
        source_sha256="b" * 64,
        contextual_embedding_text=True,
    )

    assert chunks[0]["chunk_type"] == "domain_unit"
    assert chunks[0]["retrieval_priority"] == 58
    assert chunks[0]["semantic_types"] == ["review_only", "spdm_measurement", "spdm_measurement_text"]
    assert chunks[0]["chunk_boundary_reasons"] == ["domain_unit_boundary", "review_only_domain_candidate"]
    assert chunks[0]["context_metadata"]["candidate_status"] == "review_only"
    assert chunks[0]["context_metadata"]["source_text_span"] == "GET_MEASUREMENTS"
    assert "Candidate status: review_only" in chunks[0]["embedding_text"]


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
        source_sha256="c" * 64,
    )

    assert [chunk["chunk_type"] for chunk in chunks] == ["requirement_trace", "technical_table"]
    assert chunks[0]["retrieval_priority"] == 98
    assert chunks[0]["semantic_types"] == ["requirement_trace"]
    assert chunks[1]["semantic_types"] == ["log_page"]
    assert len(chunks[0]["stable_requirement_seed"]) == 40
    assert len(chunks[1]["stable_source_id"]) == 40


def test_retrieval_chunks_boost_command_spec_context_for_embedding() -> None:
    domain_unit = {
        "domain_unit_id": "domain-nvme-000001",
        "domain_unit_index": 1,
        "domain": "nvme",
        "unit_type": "command_dword_field",
        "text": "Command Dword = CDW10 | Bits = 31:00 | Field = SLBA",
        "source_refs": [{"source_type": "technical_table_unit", "source_id": "tech-table-000001", "page": 2}],
        "page_range": [2, 2],
        "normalized_fields": {
            "command_context": "Read",
            "command_dword": "CDW10",
            "field_name": "SLBA",
            "related_command_opcode": "02h",
            "relationship_hints": ["belongs_to_command", "command_dword_layout"],
        },
    }
    technical = {
        "technical_table_unit_id": "tech-table-000001",
        "technical_table_unit_index": 1,
        "unit_type": "command_dword_field",
        "text": "Command Dword = CDW10 | Bits = 31:00 | Field = SLBA",
        "page": 2,
        "table_id": "page-0002-table-0001",
        "source_refs": [{"source_type": "table_row", "source_id": "page-0002-table-0001-row-0001", "page": 2}],
        "heading_path": ["NVM Command Set", "Read Command"],
        "command_context": "Read",
        "command_dword": "CDW10",
        "related_command_opcode": "02h",
        "relationship_hints": ["belongs_to_command", "command_dword_layout"],
    }

    chunks = build_retrieval_chunks(
        text_block_records=[],
        semantic_units=[],
        requirements=[],
        rag_tables=[],
        domain_units=[domain_unit],
        technical_table_records=[technical],
        contextual_embedding_text=True,
        source_sha256="d" * 64,
    )

    assert [chunk["chunk_type"] for chunk in chunks] == ["domain_unit", "technical_table"]
    assert chunks[0]["retrieval_priority"] == 97
    assert chunks[1]["retrieval_priority"] == 94
    assert chunks[0]["text"] == domain_unit["text"]
    assert "Command context: Read" in chunks[0]["embedding_text"]
    assert "Related command opcode: 02h" in chunks[0]["embedding_text"]
    assert "Relationship hints: belongs_to_command | command_dword_layout" in chunks[1]["embedding_text"]
    assert chunks[1]["embedding_text_strategy"] == "technical_table_context_prefix"


def test_retrieval_chunks_boost_ocp_requirement_context_without_changing_text() -> None:
    domain_unit = {
        "domain_unit_id": "domain-ocp-000001",
        "domain_unit_index": 1,
        "domain": "ocp",
        "unit_type": "requirement",
        "text": "Requirement ID = STD-LOG-1 | Requirement Description = SSD shall expose Log Identifier 01h.",
        "source_refs": [{"source_type": "technical_table_unit", "source_id": "tech-table-000001", "page": 2}],
        "page_range": [2, 2],
        "normalized_fields": {
            "requirement_id": "STD-LOG-1",
            "requirement_prefix": "STD-LOG",
            "requirement_family": "log_page",
            "ocp_section_context": "log_page",
            "related_log_identifier": "01h",
            "relationship_hints": ["references_nvme_log_page"],
        },
    }

    chunks = build_retrieval_chunks(
        text_block_records=[],
        semantic_units=[],
        requirements=[],
        rag_tables=[],
        domain_units=[domain_unit],
        contextual_embedding_text=True,
        source_sha256="e" * 64,
    )

    assert chunks[0]["chunk_type"] == "domain_unit"
    assert chunks[0]["retrieval_priority"] == 98
    assert chunks[0]["text"] == domain_unit["text"]
    assert "Requirement ID: STD-LOG-1" in chunks[0]["embedding_text"]
    assert "Requirement family: log_page" in chunks[0]["embedding_text"]
    assert "Related log identifier: 01h" in chunks[0]["embedding_text"]
    assert chunks[0]["embedding_text_strategy"] == "domain_unit_context_prefix"


def test_retrieval_chunks_mark_review_only_traceability_records() -> None:
    trace = {
        "trace_id": "req-trace-000001",
        "trace_index": 1,
        "text": "Controller: The device component that processes commands.",
        "source_refs": [{"source_type": "text_block", "source_id": "page-0001-block-0001", "page": 1}],
        "page_range": [1, 1],
        "normative_strength": "informative",
        "candidate_kind": "definition",
        "is_requirement_candidate": False,
    }

    chunks = build_retrieval_chunks(
        text_block_records=[],
        semantic_units=[],
        requirements=[],
        rag_tables=[],
        requirement_traceability_records=[trace],
    )

    assert chunks[0]["retrieval_priority"] == 60
    assert chunks[0]["semantic_types"] == ["definition", "requirement_trace", "review_only"]
    assert "review_only_trace" in chunks[0]["chunk_boundary_reasons"]


def test_retrieval_chunks_can_include_assetless_figure_text_chunks() -> None:
    figure_records = [
        {
            "figure_id": "page-0001-figure-0001",
            "page": 1,
            "figure_index": 1,
            "record_type": "image",
            "status": "available",
            "path": "assets/images/page-0001-figure-001.png",
            "bbox": [72.0, 120.0, 420.0, 320.0],
            "caption_text": "Figure 1: State machine diagram",
            "caption_confidence": 0.91,
            "heading_path": ["2.1 State Machine"],
            "figure_kind": "state_machine",
            "diagram_candidate": True,
            "detected_labels": ["IDLE", "READY", "ERROR"],
            "nearby_text_refs": [
                {
                    "block_id": "page-0001-block-0003",
                    "page": 1,
                    "text": "RESET transitions the controller back to IDLE.",
                }
            ],
            "source_refs": [
                {
                    "source_type": "figure",
                    "source_id": "page-0001-figure-0001",
                    "page": 1,
                    "bbox": [72.0, 120.0, 420.0, 320.0],
                    "path": "assets/images/page-0001-figure-001.png",
                }
            ],
        }
    ]

    chunks = build_retrieval_chunks(
        text_block_records=[],
        semantic_units=[],
        requirements=[],
        rag_tables=[],
        figure_records=figure_records,
        include_figure_text_chunks=True,
        source_sha256="b" * 64,
    )

    assert [chunk["chunk_type"] for chunk in chunks] == ["figure_text"]
    chunk = chunks[0]
    assert chunk["text"] == "\n".join(
        [
            "caption: Figure 1: State machine diagram",
            "heading_path: 2.1 State Machine",
            "figure_kind: state_machine",
            "detected_labels: IDLE | READY | ERROR",
            "nearby_text: RESET transitions the controller back to IDLE.",
        ]
    )
    assert chunk["source_refs"] == [
        {
            "source_type": "figure",
            "source_id": "page-0001-figure-0001",
            "page": 1,
            "bbox": [72.0, 120.0, 420.0, 320.0],
            "figure_id": "page-0001-figure-0001",
        }
    ]
    assert "path" not in chunk["source_refs"][0]
    assert chunk["semantic_types"] == ["diagram", "figure_text", "state_machine"]
    assert chunk["retrieval_priority"] == 78
    assert "observed_caption" in chunk["chunk_boundary_reasons"]


def test_retrieval_chunks_skip_captionless_low_confidence_figure_diagnostics() -> None:
    figure_records = [
        {
            "figure_id": "page-0001-figure-0001",
            "page": 1,
            "figure_index": 1,
            "bbox": [72.0, 120.0, 420.0, 320.0],
            "caption_text": None,
            "caption_confidence": None,
            "heading_path": [],
            "figure_kind": "image",
            "diagram_candidate": False,
            "detected_labels": [],
            "nearby_text_refs": [],
            "captionless_diagnostics": {"status": "captionless_diagnostics_only"},
            "source_refs": [{"source_type": "excluded_figure", "source_id": "page-0001-figure-0001", "page": 1}],
        }
    ]

    chunks = build_retrieval_chunks(
        text_block_records=[],
        semantic_units=[],
        requirements=[],
        rag_tables=[],
        figure_records=figure_records,
        include_figure_text_chunks=True,
    )

    assert chunks == []


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


def test_retrieval_chunk_optimizer_accepts_token_counter() -> None:
    records = [
        {
            "chunk_id": "chunk-000001",
            "chunk_index": 1,
            "chunk_type": "text_block",
            "text": "one two three four five six seven eight nine",
            "source_refs": [{"source_type": "text_block", "source_id": "block-1", "page": 1}],
            "source_dedupe_key": "block-1",
            "char_count": 44,
            "token_estimate": 9,
        },
    ]

    optimized = optimize_retrieval_chunks(records, max_tokens=3, token_counter=lambda text: len(text.split()))

    assert len(optimized) == 3
    assert [record["token_estimate"] for record in optimized] == [3, 3, 3]
    assert [record["text"] for record in optimized] == [
        "one two three",
        "four five six",
        "seven eight nine",
    ]


def test_merge_sibling_text_chunks_combines_adjacent_same_section_records() -> None:
    records = [
        {
            "chunk_id": "chunk-000001",
            "chunk_index": 1,
            "chunk_type": "text_block",
            "text": "Alpha status.",
            "source_refs": [{"source_type": "text_block", "source_id": "block-1", "page": 1}],
            "page_range": [1, 1],
            "bbox": [10.0, 20.0, 100.0, 30.0],
            "heading_path": ["1 Status"],
            "semantic_types": ["paragraph"],
            "retrieval_priority": 50,
            "section_path": "1 Status",
            "chunk_group_id": "text-page-0001",
            "source_record_count": 1,
            "source_dedupe_key": "block-1",
            "chunk_boundary_policy": "source_record",
            "chunk_boundary_reasons": ["text_block_boundary"],
        },
        {
            "chunk_id": "chunk-000002",
            "chunk_index": 2,
            "chunk_type": "text_block",
            "text": "Beta status.",
            "source_refs": [{"source_type": "text_block", "source_id": "block-2", "page": 1}],
            "page_range": [1, 1],
            "bbox": [12.0, 34.0, 120.0, 44.0],
            "heading_path": ["1 Status"],
            "semantic_types": ["paragraph"],
            "retrieval_priority": 50,
            "section_path": "1 Status",
            "chunk_group_id": "text-page-0001",
            "source_record_count": 1,
            "source_dedupe_key": "block-2",
            "chunk_boundary_policy": "source_record",
            "chunk_boundary_reasons": ["text_block_boundary"],
        },
        {
            "chunk_id": "chunk-000003",
            "chunk_index": 3,
            "chunk_type": "requirement",
            "text": "The controller shall return SUCCESS.",
            "source_refs": [{"source_type": "requirement", "source_id": "req-1", "page": 1}],
            "page_range": [1, 1],
            "heading_path": ["1 Status"],
            "semantic_types": ["requirement"],
            "retrieval_priority": 100,
            "section_path": "1 Status",
            "chunk_group_id": "requirement-page-0001",
            "source_record_count": 1,
            "source_dedupe_key": "req-1",
            "chunk_boundary_policy": "source_record",
            "chunk_boundary_reasons": ["requirement_boundary"],
        },
    ]

    merged = merge_sibling_text_chunks(records, max_tokens=6, token_counter=lambda text: len(text.split()))

    assert [record["chunk_id"] for record in merged] == ["chunk-000001", "chunk-000002"]
    assert merged[0]["text"] == "Alpha status.\n\nBeta status."
    assert merged[0]["source_record_count"] == 2
    assert [ref["source_id"] for ref in merged[0]["source_refs"]] == ["block-1", "block-2"]
    assert merged[0]["bbox"] == [10.0, 20.0, 120.0, 44.0]
    assert merged[0]["source_dedupe_key"] == "block-1|block-2"
    assert merged[0]["chunk_boundary_policy"] == "merged_sibling_text_blocks"
    assert "sibling_text_merge" in merged[0]["chunk_boundary_reasons"]
    assert merged[0]["merged_source_chunk_ids"] == ["chunk-000001", "chunk-000002"]
    assert merged[0]["merged_source_chunk_count"] == 2
    assert merged[0]["merge_strategy"] == "adjacent_text_block_same_section_token_budget"
    assert merged[1]["chunk_type"] == "requirement"


def test_build_retrieval_chunks_merges_only_budget_safe_sibling_text_blocks() -> None:
    text_blocks = [
        {
            "block_id": "page-0001-block-0001",
            "page": 1,
            "block_index": 1,
            "block_type": "paragraph",
            "text": "Alpha status.",
            "bbox": [10.0, 20.0, 100.0, 30.0],
            "heading_path": ["1 Status"],
        },
        {
            "block_id": "page-0001-block-0002",
            "page": 1,
            "block_index": 2,
            "block_type": "paragraph",
            "text": "Beta status.",
            "bbox": [12.0, 34.0, 120.0, 44.0],
            "heading_path": ["1 Status"],
        },
        {
            "block_id": "page-0001-block-0003",
            "page": 1,
            "block_index": 3,
            "block_type": "paragraph",
            "text": "Gamma status.",
            "bbox": [12.0, 50.0, 120.0, 60.0],
            "heading_path": ["2 Other"],
        },
    ]
    requirement = {
        "semantic_id": "page-0001-sem-0001",
        "semantic_index": 1,
        "semantic_type": "requirement",
        "text": "The controller shall return SUCCESS.",
        "source_refs": [{"source_type": "text_block", "source_id": "page-0001-block-0001", "page": 1}],
        "page_range": [1, 1],
        "heading_path": ["1 Status"],
        "normative_strength": "required",
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
        semantic_units=[requirement],
        requirements=[requirement],
        rag_tables=rag_tables,
        max_tokens=10,
        token_counter=lambda text: len(text.split()),
        merge_sibling_text_blocks=True,
    )

    assert [chunk["chunk_type"] for chunk in chunks] == ["text_block", "text_block", "requirement", "table_row"]
    assert chunks[0]["text"] == "Alpha status.\n\nBeta status."
    assert chunks[0]["source_record_count"] == 2
    assert chunks[0]["token_estimate"] == 4
    assert chunks[1]["text"] == "Gamma status."
    assert chunks[2]["chunk_boundary_policy"] == "source_record"
    assert chunks[3]["chunk_boundary_policy"] == "source_record"


def test_build_retrieval_chunks_does_not_merge_text_blocks_over_budget() -> None:
    text_blocks = [
        {
            "block_id": "page-0001-block-0001",
            "page": 1,
            "block_index": 1,
            "block_type": "paragraph",
            "text": "Alpha status.",
            "heading_path": ["1 Status"],
        },
        {
            "block_id": "page-0001-block-0002",
            "page": 1,
            "block_index": 2,
            "block_type": "paragraph",
            "text": "Beta status.",
            "heading_path": ["1 Status"],
        },
    ]

    chunks = build_retrieval_chunks(
        text_block_records=text_blocks,
        semantic_units=[],
        requirements=[],
        rag_tables=[],
        max_tokens=3,
        token_counter=lambda text: len(text.split()),
        merge_sibling_text_blocks=True,
    )

    assert [chunk["text"] for chunk in chunks] == ["Alpha status.", "Beta status."]
    assert all(chunk["chunk_boundary_policy"] == "source_record" for chunk in chunks)


def test_assign_chunk_relationships_adds_group_neighbors_and_section_anchor() -> None:
    chunks = [
        {
            "chunk_id": "chunk-000001",
            "chunk_index": 1,
            "chunk_type": "text_block",
            "text": "Alpha status.",
            "chunk_group_id": "text-page-0001",
            "section_path": "1 Status",
        },
        {
            "chunk_id": "chunk-000002",
            "chunk_index": 2,
            "chunk_type": "text_block",
            "text": "Beta status.",
            "chunk_group_id": "text-page-0001",
            "section_path": "1 Status",
        },
        {
            "chunk_id": "chunk-000003",
            "chunk_index": 3,
            "chunk_type": "requirement",
            "text": "The controller shall return SUCCESS.",
            "chunk_group_id": "requirement-page-0001",
            "section_path": "1 Status",
        },
    ]

    related = assign_chunk_relationships(chunks)

    assert related[0]["next_chunk_id"] == "chunk-000002"
    assert "previous_chunk_id" not in related[0]
    assert related[0]["relationship_strategy"] == "chunk_group_prev_next_section_anchor"
    assert related[0]["relationship_metadata_version"] == "2.0"
    assert related[0]["chunk_group_index"] == 1
    assert related[0]["chunk_group_count"] == 2
    assert related[0]["section_chunk_index"] == 1
    assert related[0]["section_chunk_count"] == 3
    assert related[0]["relationship_reasons"] == ["chunk_group_neighbor"]
    assert related[1]["previous_chunk_id"] == "chunk-000001"
    assert related[1]["section_anchor_chunk_id"] == "chunk-000001"
    assert related[1]["related_chunk_ids"] == ["chunk-000001"]
    assert related[1]["chunk_group_index"] == 2
    assert related[1]["relationship_reasons"] == ["chunk_group_neighbor", "section_anchor"]
    assert related[2]["section_anchor_chunk_id"] == "chunk-000001"
    assert related[2]["related_chunk_ids"] == ["chunk-000001"]
    assert related[2]["chunk_group_count"] == 1
    assert related[2]["section_chunk_index"] == 3
    assert related[2]["relationship_reasons"] == ["section_anchor"]
    assert "previous_chunk_id" not in chunks[1]


def test_assign_chunk_relationships_adds_parent_section_anchor() -> None:
    chunks = [
        {
            "chunk_id": "chunk-000001",
            "chunk_index": 1,
            "chunk_type": "text_block",
            "text": "Root overview.",
            "chunk_group_id": "text-page-0001",
            "section_path": "1 Root",
        },
        {
            "chunk_id": "chunk-000002",
            "chunk_index": 2,
            "chunk_type": "text_block",
            "text": "Child overview.",
            "chunk_group_id": "text-page-0002",
            "section_path": "1 Root > 1.1 Child",
        },
        {
            "chunk_id": "chunk-000003",
            "chunk_index": 3,
            "chunk_type": "requirement",
            "text": "The device shall preserve state.",
            "chunk_group_id": "requirement-page-0002",
            "section_path": "1 Root > 1.1 Child",
        },
    ]

    related = assign_chunk_relationships(chunks)

    assert related[1]["parent_section_path"] == "1 Root"
    assert related[1]["parent_section_anchor_chunk_id"] == "chunk-000001"
    assert related[1]["related_chunk_ids"] == ["chunk-000001"]
    assert related[1]["relationship_reasons"] == ["parent_section_anchor"]
    assert related[2]["section_anchor_chunk_id"] == "chunk-000002"
    assert related[2]["parent_section_anchor_chunk_id"] == "chunk-000001"
    assert related[2]["related_chunk_ids"] == ["chunk-000002", "chunk-000001"]
    assert related[2]["relationship_reasons"] == ["section_anchor", "parent_section_anchor"]


def test_build_retrieval_chunks_can_add_relationship_metadata_after_optimization() -> None:
    text_blocks = [
        {
            "block_id": "page-0001-block-0001",
            "page": 1,
            "block_index": 1,
            "block_type": "paragraph",
            "text": "Alpha status.",
            "heading_path": ["1 Status"],
        },
        {
            "block_id": "page-0001-block-0002",
            "page": 1,
            "block_index": 2,
            "block_type": "paragraph",
            "text": "Beta status.",
            "heading_path": ["1 Status"],
        },
    ]

    chunks = build_retrieval_chunks(
        text_block_records=text_blocks,
        semantic_units=[],
        requirements=[],
        rag_tables=[],
        relationship_metadata=True,
    )

    assert chunks[0]["next_chunk_id"] == "chunk-000002"
    assert chunks[1]["previous_chunk_id"] == "chunk-000001"
    assert chunks[1]["section_anchor_chunk_id"] == "chunk-000001"
    assert chunks[0]["relationship_strategy"] == "chunk_group_prev_next_section_anchor"
    assert chunks[0]["relationship_metadata_version"] == "2.0"
    assert chunks[0]["chunk_group_index"] == 1
    assert chunks[1]["chunk_group_index"] == 2


def test_contextual_embedding_text_keeps_table_row_text_as_source_of_truth() -> None:
    rag_tables = [
        {
            "page": 1,
            "table_index": 1,
            "caption_text": "Table 1: Status fields",
            "headers": ["Field", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 1,
                    "row_index": 1,
                    "caption_text": "Table 1: Status fields",
                    "headers": ["Field", "Description"],
                    "row_text": "Field = Status | Description = Current status",
                    "heading_path": ["2 Registers"],
                }
            ],
        }
    ]

    chunks = build_retrieval_chunks(
        text_block_records=[],
        semantic_units=[],
        requirements=[],
        rag_tables=rag_tables,
        contextual_embedding_text=True,
        token_counter=lambda text: len(text.split()),
    )

    assert chunks[0]["chunk_type"] == "table_row"
    assert chunks[0]["text"] == "Field = Status | Description = Current status"
    assert chunks[0]["char_count"] == len(chunks[0]["text"])
    assert chunks[0]["embedding_text_strategy"] == "table_context_prefix"
    assert "Section: 2 Registers" in chunks[0]["embedding_text"]
    assert "Caption: Table 1: Status fields" in chunks[0]["embedding_text"]
    assert "Headers: Field | Description" in chunks[0]["embedding_text"]
    assert chunks[0]["embedding_token_estimate"] > chunks[0]["token_estimate"]
    assert chunks[0]["context_metadata"] == {
        "metadata_version": "2.0",
        "context_type": "table_row",
        "table_id": "page-0001-table-0001",
        "caption_text": "Table 1: Status fields",
        "headers": ["Field", "Description"],
        "heading_path": ["2 Registers"],
    }


def test_table_row_context_metadata_inherits_table_level_caption_and_headers() -> None:
    rag_tables = [
        {
            "page": 1,
            "table_index": 1,
            "caption_text": "Table 1: Status fields",
            "headers": ["Field", "Description"],
            "table_confidence_v2": 0.92,
            "table_confidence_v2_bucket": "high",
            "records": [
                {
                    "page": 1,
                    "table_index": 1,
                    "row_index": 1,
                    "row_text": "Field = Status | Description = Current status",
                }
            ],
        }
    ]

    chunks = build_retrieval_chunks(
        text_block_records=[],
        semantic_units=[],
        requirements=[],
        rag_tables=rag_tables,
    )

    assert chunks[0]["text"] == "Field = Status | Description = Current status"
    assert chunks[0]["context_metadata"] == {
        "metadata_version": "2.0",
        "context_type": "table_row",
        "table_id": "page-0001-table-0001",
        "caption_text": "Table 1: Status fields",
        "headers": ["Field", "Description"],
        "table_confidence_v2": 0.92,
        "table_confidence_v2_bucket": "high",
    }
