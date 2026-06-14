from __future__ import annotations

import json

from pdf2md.serializers.rag_requirements import (
    build_requirement_traceability_records,
    serialize_requirement_traceability_jsonl,
)


def test_requirement_traceability_preserves_normative_source_and_test_hint() -> None:
    requirements = [
        {
            "semantic_id": "page-0001-sem-0001",
            "semantic_index": 1,
            "semantic_type": "requirement",
            "text": "REQ-12 The device shall report SMART status when requested.",
            "source_refs": [{"source_type": "text_block", "source_id": "page-0001-block-0001", "page": 1}],
            "page_range": [1, 1],
            "bbox": [72.0, 80.0, 420.0, 100.0],
            "heading_path": ["1 Requirements"],
            "normative_strength": "required",
        }
    ]

    records = build_requirement_traceability_records(requirements=requirements, rag_tables=[], source_sha256="d" * 64)

    assert records[0]["trace_id"] == "req-trace-000001"
    assert records[0]["requirement_id"] == "REQ-12"
    assert records[0]["condition"] == "when requested"
    assert records[0]["conditions"] == ["when requested"]
    assert records[0]["exceptions"] == []
    assert records[0]["testability_hint"] == "directly_testable"
    assert records[0]["verification_intent"] == "direct_test"
    assert records[0]["candidate_kind"] == "normative_requirement"
    assert records[0]["is_requirement_candidate"] is True
    assert records[0]["exclusion_reason"] is None
    assert records[0]["section_path"] == "1 Requirements"
    assert records[0]["domain_unit_id"] is None
    assert records[0]["technical_table_unit_id"] is None
    assert records[0]["source_refs"][0]["source_id"] == "page-0001-block-0001"
    assert records[0]["source_sha256"] == "d" * 64
    assert records[0]["source_dedupe_key"] == "page-0001-block-0001"
    assert len(records[0]["stable_source_id"]) == 40
    assert len(records[0]["stable_requirement_seed"]) == 40


def test_requirement_traceability_extracts_ocp_style_table_rows() -> None:
    rag_tables = [
        {
            "page": 2,
            "table_index": 1,
            "headers": ["Requirement ID", "Description", "SSD"],
            "records": [
                {
                    "page": 2,
                    "table_index": 1,
                    "row_index": 1,
                    "headers": ["Requirement ID", "Description", "SSD"],
                    "cells": {
                        "Requirement ID": "LABL-9",
                        "Description": "The label shall not degrade over the device lifetime.",
                        "SSD": "Mandatory",
                    },
                    "row_text": (
                        "Requirement ID = LABL-9 | Description = The label shall not degrade over the device "
                        "lifetime. | SSD = Mandatory"
                    ),
                }
            ],
        }
    ]

    records = build_requirement_traceability_records(requirements=[], rag_tables=rag_tables, source_sha256="e" * 64)

    assert records[0]["requirement_id"] == "LABL-9"
    assert records[0]["text"] == "The label shall not degrade over the device lifetime."
    assert records[0]["candidate_kind"] == "structured_requirement"
    assert records[0]["is_requirement_candidate"] is True
    assert records[0]["table_id"] == "page-0002-table-0001"
    assert records[0]["table_row_id"] == "page-0002-table-0001-row-0001"
    assert records[0]["source_refs"][0]["source_id"] == "page-0002-table-0001-row-0001"
    assert records[0]["source_dedupe_key"] == "page-0002-table-0001-row-0001"
    assert len(records[0]["stable_requirement_seed"]) == 40

    jsonl = serialize_requirement_traceability_jsonl(records)
    assert json.loads(jsonl)["classification_reasons"] == ["table_description", "table_requirement_id"]


def test_requirement_traceability_marks_review_only_semantic_candidates() -> None:
    semantic_units = [
        {
            "semantic_id": "page-0001-sem-0001",
            "semantic_index": 1,
            "semantic_type": "definition",
            "text": "Controller: The device component that processes commands.",
            "source_refs": [{"source_type": "text_block", "source_id": "page-0001-block-0001", "page": 1}],
            "page_range": [1, 1],
            "bbox": [72.0, 90.0, 420.0, 110.0],
            "heading_path": ["2 Terms"],
            "normative_strength": "informative",
        },
        {
            "semantic_id": "page-0001-sem-0002",
            "semantic_index": 2,
            "semantic_type": "note",
            "text": "NOTE: This value is informative.",
            "source_refs": [{"source_type": "text_block", "source_id": "page-0001-block-0002", "page": 1}],
            "page_range": [1, 1],
            "bbox": [72.0, 120.0, 420.0, 140.0],
            "heading_path": ["2 Terms"],
            "normative_strength": "informative",
        },
        {
            "semantic_id": "page-0001-sem-0003",
            "semantic_index": 3,
            "semantic_type": "paragraph",
            "text": "Example: A host may retry a failed command.",
            "source_refs": [{"source_type": "text_block", "source_id": "page-0001-block-0003", "page": 1}],
            "page_range": [1, 1],
            "bbox": [72.0, 150.0, 420.0, 170.0],
            "heading_path": ["2 Terms"],
            "normative_strength": "informative",
        },
    ]

    records = build_requirement_traceability_records(
        requirements=[],
        rag_tables=[],
        semantic_units=semantic_units,
        source_sha256="f" * 64,
    )

    assert [record["candidate_kind"] for record in records] == ["definition", "note", "example"]
    assert [record["exclusion_reason"] for record in records] == ["definition", "note", "example"]
    assert all(record["is_requirement_candidate"] is False for record in records)
    assert records[0]["section_path"] == "2 Terms"
    assert records[2]["verification_intent"] == "unknown"
    assert len(records[0]["stable_requirement_seed"]) == 40


def test_requirement_traceability_precision_filters_review_only_requirement_candidates() -> None:
    requirements = [
        {
            "semantic_id": "page-0001-sem-0001",
            "semantic_index": 1,
            "semantic_type": "requirement",
            "text": "The overview shall introduce command processing.",
            "source_refs": [{"source_type": "text_block", "source_id": "page-0001-block-0001", "page": 1}],
            "page_range": [1, 1],
            "heading_path": ["1 Introduction"],
            "normative_strength": "required",
        },
        {
            "semantic_id": "page-0001-sem-0002",
            "semantic_index": 2,
            "semantic_type": "requirement",
            "text": "NOTE: The controller shall report this value for illustration only.",
            "source_refs": [{"source_type": "text_block", "source_id": "page-0001-block-0002", "page": 1}],
            "page_range": [1, 1],
            "heading_path": ["2 Operation"],
            "normative_strength": "required",
        },
        {
            "semantic_id": "page-0001-sem-0003",
            "semantic_index": 3,
            "semantic_type": "requirement",
            "text": "Example: A host may retry a failed command.",
            "source_refs": [{"source_type": "text_block", "source_id": "page-0001-block-0003", "page": 1}],
            "page_range": [1, 1],
            "heading_path": ["2 Operation"],
            "normative_strength": "optional",
        },
        {
            "semantic_id": "page-0001-sem-0004",
            "semantic_index": 4,
            "semantic_type": "requirement",
            "text": "Controller: The device shall process commands.",
            "source_refs": [{"source_type": "text_block", "source_id": "page-0001-block-0004", "page": 1}],
            "page_range": [1, 1],
            "heading_path": ["3 Terms"],
            "normative_strength": "required",
        },
        {
            "semantic_id": "page-0001-sem-0005",
            "semantic_index": 5,
            "semantic_type": "requirement",
            "text": "Copyright 2026 Example Group. Permission must be requested before copying.",
            "source_refs": [{"source_type": "text_block", "source_id": "page-0001-block-0005", "page": 1}],
            "page_range": [1, 1],
            "heading_path": ["Legal Notices"],
            "normative_strength": "required",
        },
    ]

    records = build_requirement_traceability_records(requirements=requirements, rag_tables=[])

    assert [record["candidate_kind"] for record in records] == [
        "front_matter",
        "note",
        "example",
        "definition",
        "front_matter",
    ]
    assert [record["exclusion_reason"] for record in records] == [
        "front_matter",
        "note",
        "example",
        "definition",
        "legal_notice",
    ]
    assert all(record["is_requirement_candidate"] is False for record in records)
    assert all("review_only_exclusion" in record["classification_reasons"] for record in records)
