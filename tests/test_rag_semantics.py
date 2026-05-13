from __future__ import annotations

import json

from pdf2md.serializers.rag_semantics import build_semantic_layer, serialize_semantic_units_jsonl
from pdf2md.serializers.rag_tables import normalize_rag_table_payload


def _text_block(
    text: str,
    *,
    block_id: str = "page-0001-block-0001",
    block_index: int = 1,
    block_type: str = "paragraph",
    parent: str | None = None,
) -> dict:
    return {
        "block_id": block_id,
        "page": 1,
        "block_index": block_index,
        "block_type": block_type,
        "text": text,
        "bbox": [72.0, 72.0 + block_index * 20, 420.0, 92.0 + block_index * 20],
        "line_indices": [block_index],
        "heading_path": ["1 Overview"] if block_type != "heading" else ["1 Overview"],
        "parent_heading_block_id": parent,
        "classification_confidence": 0.9,
        "classification_reasons": ["test"],
    }


def test_normative_keywords_create_requirement_records() -> None:
    result = build_semantic_layer(
        text_block_records=[
            _text_block(
                "The controller shall return SUCCESS. "
                "The host shall not modify reserved bits. "
                "Software should retry the command. "
                "The command may complete asynchronously."
            )
        ],
        rag_tables=[],
    )

    assert [record["normative_strength"] for record in result.requirements] == [
        "required",
        "prohibited",
        "recommended",
        "optional",
    ]
    assert result.normative_requirement_count == 4
    assert result.requirements[0]["text"] == "The controller shall return SUCCESS."


def test_will_and_uppercase_body_are_not_requirements() -> None:
    result = build_semantic_layer(
        text_block_records=[
            _text_block("THIS IS IMPORTANT BODY TEXT", block_index=1),
            _text_block("The controller will report status.", block_id="page-0001-block-0002", block_index=2),
            _text_block("Published in May 2024.", block_id="page-0001-block-0003", block_index=3),
        ],
        rag_tables=[],
    )

    assert result.requirements == []
    assert result.semantic_low_confidence_count == 1


def test_definition_pattern_preserves_source_text() -> None:
    result = build_semantic_layer(
        text_block_records=[
            _text_block("Controller: The device component that processes commands."),
            _text_block(
                "Namespace means a formatted collection of logical blocks.",
                block_id="page-0001-block-0002",
                block_index=2,
            ),
        ],
        rag_tables=[],
    )

    definitions = [record for record in result.semantic_units if record["semantic_type"] == "definition"]
    assert [record["canonical_key"] for record in definitions] == ["controller", "namespace"]
    assert definitions[0]["text"] == "Controller: The device component that processes commands."


def test_table_rows_create_parameter_units_with_stable_ids() -> None:
    rag_tables = normalize_rag_table_payload(
        [
            {
                "page": 1,
                "table_index": 1,
                "caption_text": "Table 1: Fields",
                "headers": ["Field", "Bits", "Description"],
                "records": [
                    {
                        "page": 1,
                        "table_index": 1,
                        "row_index": 1,
                        "headers": ["Field", "Bits", "Description"],
                        "cells": {"Field": "Status", "Bits": "3:0", "Description": "Current status"},
                        "row_text": "Field = Status | Bits = 3:0 | Description = Current status",
                        "bbox": [72.0, 120.0, 420.0, 150.0],
                    }
                ],
            }
        ]
    )

    result = build_semantic_layer(text_block_records=[], rag_tables=rag_tables)

    assert rag_tables[0]["table_id"] == "page-0001-table-0001"
    assert rag_tables[0]["records"][0]["table_row_id"] == "page-0001-table-0001-row-0001"
    parameter = result.semantic_units[0]
    assert parameter["semantic_type"] == "parameter"
    assert parameter["canonical_key"] == "status"
    assert parameter["source_refs"][0]["source_id"] == "page-0001-table-0001-row-0001"


def test_cross_refs_are_resolved_when_targets_exist_and_kept_when_unresolved() -> None:
    result = build_semantic_layer(
        text_block_records=[
            _text_block("1 Overview", block_type="heading"),
            _text_block("Table 1: Fields", block_id="page-0001-block-0002", block_index=2, block_type="caption"),
            _text_block(
                "See Section 1, Table 1, and Figure 9 for details.",
                block_id="page-0001-block-0003",
                block_index=3,
                parent="page-0001-block-0001",
            ),
        ],
        rag_tables=[],
    )

    assert [(record["target_label"], record["resolved"]) for record in result.cross_refs] == [
        ("Section 1", True),
        ("Table 1", True),
        ("Figure 9", False),
    ]
    assert result.unresolved_cross_ref_count == 1
    reference_units = [record for record in result.semantic_units if record["semantic_type"] == "reference"]
    assert len(reference_units) == 3


def test_semantic_jsonl_is_deterministic() -> None:
    result = build_semantic_layer(
        text_block_records=[_text_block("The controller shall return SUCCESS.")],
        rag_tables=[],
    )

    first = json.loads(serialize_semantic_units_jsonl(result.semantic_units).splitlines()[0])
    assert first["semantic_id"] == "page-0001-sem-0001"
    assert first["semantic_index"] == 1
    assert first["source_refs"][0]["source_type"] == "text_block"
