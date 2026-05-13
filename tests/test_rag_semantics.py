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


def test_legal_notice_and_toc_entries_are_not_requirements() -> None:
    result = build_semantic_layer(
        text_block_records=[
            _text_block(
                "Copyright 2026 Example Group. All rights reserved. Permission must be requested before copying.",
                block_id="page-0001-block-0001",
                block_index=1,
            ),
            _text_block(
                "Table 4: Optional Admin Commands ........ 37",
                block_id="page-0001-block-0002",
                block_index=2,
            ),
            _text_block(
                "The controller shall report SMART status.",
                block_id="page-0006-block-0001",
                block_index=1,
            )
            | {"page": 6},
        ],
        rag_tables=[],
    )

    assert [record["text"] for record in result.requirements] == ["The controller shall report SMART status."]


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
    assert result.cross_refs[-1]["unresolved_reason"] == "missing_target_type"
    assert result.unresolved_cross_ref_count == 1
    reference_units = [record for record in result.semantic_units if record["semantic_type"] == "reference"]
    assert len(reference_units) == 3


def test_technical_cross_refs_include_requirement_and_log_identifier_targets() -> None:
    rag_tables = normalize_rag_table_payload(
        [
            {
                "page": 1,
                "table_index": 1,
                "headers": ["Requirement ID", "Description"],
                "records": [
                    {
                        "page": 1,
                        "table_index": 1,
                        "row_index": 1,
                        "headers": ["Requirement ID", "Description"],
                        "cells": {"Requirement ID": "GLP-ACC-1", "Description": "Log pages shall be accessible."},
                        "row_text": "Requirement ID = GLP-ACC-1 | Description = Log pages shall be accessible.",
                    },
                    {
                        "page": 1,
                        "table_index": 1,
                        "row_index": 2,
                        "headers": ["Log Identifier", "Description"],
                        "cells": {"Log Identifier": "C0h", "Description": "SMART / Health Information Extended"},
                        "row_text": "Log Identifier = C0h | Description = SMART / Health Information Extended",
                    },
                ],
            }
        ]
    )

    result = build_semantic_layer(
        text_block_records=[
            _text_block("See Requirement GLP-ACC-1 and Log Identifier C0h for sanitize behavior.")
        ],
        rag_tables=rag_tables,
    )

    assert [(record["target_type"], record["target_label"], record["resolved"]) for record in result.cross_refs] == [
        ("requirement", "Requirement GLP-ACC-1", True),
        ("log_page", "Log Identifier C0h", True),
    ]


def test_technical_cross_refs_resolve_hex_format_variants_and_explain_unresolved() -> None:
    rag_tables = normalize_rag_table_payload(
        [
            {
                "page": 1,
                "table_index": 1,
                "headers": ["Feature Identifier", "Description"],
                "records": [
                    {
                        "page": 1,
                        "table_index": 1,
                        "row_index": 1,
                        "headers": ["Feature Identifier", "Description"],
                        "cells": {"Feature Identifier": "0x0C", "Description": "Autonomous Power State Transition"},
                        "row_text": "Feature Identifier = 0x0C | Description = Autonomous Power State Transition",
                    }
                ],
            }
        ]
    )

    result = build_semantic_layer(
        text_block_records=[
            _text_block("See FID 0Ch for APST behavior and Opcode 0x99 for vendor behavior.")
        ],
        rag_tables=rag_tables,
    )

    resolved_feature, unresolved_opcode = result.cross_refs
    assert resolved_feature["target_type"] == "feature"
    assert resolved_feature["resolved"] is True
    assert resolved_feature["target_ref"] == "page-0001-table-0001-row-0001"
    assert resolved_feature["normalized_target_key"] == "hex:c"
    assert resolved_feature["candidate_count"] == 1
    assert unresolved_opcode["target_type"] == "opcode"
    assert unresolved_opcode["resolved"] is False
    assert unresolved_opcode["normalized_target_key"] == "hex:99"
    assert unresolved_opcode["unresolved_reason"] == "missing_target_type"


def test_semantic_jsonl_is_deterministic() -> None:
    result = build_semantic_layer(
        text_block_records=[_text_block("The controller shall return SUCCESS.")],
        rag_tables=[],
    )

    first = json.loads(serialize_semantic_units_jsonl(result.semantic_units).splitlines()[0])
    assert first["semantic_id"] == "page-0001-sem-0001"
    assert first["semantic_index"] == 1
    assert first["source_refs"][0]["source_type"] == "text_block"
