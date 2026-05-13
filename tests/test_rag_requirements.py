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

    records = build_requirement_traceability_records(requirements=requirements, rag_tables=[])

    assert records[0]["trace_id"] == "req-trace-000001"
    assert records[0]["requirement_id"] == "REQ-12"
    assert records[0]["condition"] == "when requested"
    assert records[0]["testability_hint"] == "directly_testable"
    assert records[0]["source_refs"][0]["source_id"] == "page-0001-block-0001"


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

    records = build_requirement_traceability_records(requirements=[], rag_tables=rag_tables)

    assert records[0]["requirement_id"] == "LABL-9"
    assert records[0]["text"] == "The label shall not degrade over the device lifetime."
    assert records[0]["source_refs"][0]["source_id"] == "page-0002-table-0001-row-0001"

    jsonl = serialize_requirement_traceability_jsonl(records)
    assert json.loads(jsonl)["classification_reasons"] == ["table_description", "table_requirement_id"]
