from __future__ import annotations

import json

from pypdf import PdfReader, PdfWriter

from pdf2md.serializers.rag_semantics import (
    build_semantic_layer,
    extract_pdf_outline_reference_targets,
    serialize_semantic_units_jsonl,
)
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


def test_cross_refs_resolve_missing_sections_from_pdf_outline_targets() -> None:
    result = build_semantic_layer(
        text_block_records=[
            _text_block(
                "See Section 3.6.1 for controller behavior.",
                block_id="page-0001-block-0001",
                block_index=1,
            )
        ],
        rag_tables=[],
        pdf_outline_targets=[
            {
                "target_type": "section",
                "target_label": "3.6.1",
                "target_ref": "pdf-outline-section-3-6-1-page-0042",
                "page": 42,
                "title": "3.6.1 Controller Behavior",
            }
        ],
    )

    assert [(record["target_label"], record["resolved"]) for record in result.cross_refs] == [
        ("Section 3.6.1", True)
    ]
    assert result.cross_refs[0]["target_ref"] == "pdf-outline-section-3-6-1-page-0042"
    assert "target_source_pdf_outline" in result.cross_refs[0]["classification_reasons"]
    assert result.unresolved_cross_ref_count == 0


def test_pdf_outline_targets_extract_numeric_sections_and_respect_selected_pages(tmp_path) -> None:
    pdf_path = tmp_path / "outline.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    writer.add_outline_item("3.6.1 Controller Behavior", 0)
    writer.add_outline_item("Appendix B External References", 1)
    with pdf_path.open("wb") as fp:
        writer.write(fp)

    reader = PdfReader(str(pdf_path))

    targets = extract_pdf_outline_reference_targets(reader, selected_pages={1, 2})
    assert [(target["target_type"], target["target_label"], target["page"]) for target in targets] == [
        ("appendix", "B", 2),
        ("section", "3.6.1", 1),
    ]
    assert extract_pdf_outline_reference_targets(reader, selected_pages={1}) == [targets[1]]


def test_cross_refs_resolve_figures_from_list_entries_without_using_them_as_sources() -> None:
    result = build_semantic_layer(
        text_block_records=[
            _text_block("List of Figures", block_id="page-0001-block-0001", block_index=1),
            _text_block(
                "Figure 29: Queue arbitration flow ................ 123",
                block_id="page-0001-block-0002",
                block_index=2,
            ),
            _text_block(
                "See Figure 29 for the queue arbitration state machine.",
                block_id="page-0002-block-0001",
                block_index=1,
            )
            | {"page": 2},
        ],
        rag_tables=[],
    )

    assert [(record["target_label"], record["resolved"]) for record in result.cross_refs] == [
        ("Figure 29", True)
    ]
    assert result.cross_refs[0]["target_ref"] == "pdf-list-figure-29-page-0123"
    assert "target_source_pdf_list" in result.cross_refs[0]["classification_reasons"]
    assert result.unresolved_cross_ref_count == 0


def test_cross_ref_normalization_splits_plural_sections_and_attached_figure_labels() -> None:
    result = build_semantic_layer(
        text_block_records=[
            _text_block("3.6.1 First Target", block_id="page-0001-block-0001", block_index=1, block_type="heading"),
            _text_block("3.6.2 Second Target", block_id="page-0001-block-0002", block_index=2, block_type="heading"),
            _text_block("Figure 23: Completion flow", block_id="page-0001-block-0003", block_index=3, block_type="caption"),
            _text_block(
                "See sections 3.6.1 and 3.6.2. Figure 23Figure 23 shows the completion flow. "
                "Figure 551determines is extraction noise.",
                block_id="page-0001-block-0004",
                block_index=4,
            ),
        ],
        rag_tables=[],
    )

    assert [(record["target_label"], record["resolved"]) for record in result.cross_refs] == [
        ("Section 3.6.1", True),
        ("Section 3.6.2", True),
        ("Figure 23", True),
    ]
    assert result.unresolved_cross_ref_count == 0


def test_cross_ref_guardrails_skip_generic_unresolved_phrases() -> None:
    result = build_semantic_layer(
        text_block_records=[
            _text_block("1 Overview", block_type="heading"),
            _text_block("Table 1: Fields", block_id="page-0001-block-0002", block_index=2, block_type="caption"),
            _text_block("Table of Figures", block_id="page-0001-block-0003", block_index=3),
            _text_block(
                "Relationships section of the NVM Express Base Specification.",
                block_id="page-0001-block-0004",
                block_index=4,
            ),
            _text_block(
                "This section defines terms that are specific to this specification.",
                block_id="page-0001-block-0005",
                block_index=5,
            ),
            _text_block(
                "The base specification defines a register level interface for host software.",
                block_id="page-0001-block-0006",
                block_index=6,
            ),
            _text_block(
                "See Section 1 and Table 1 for details.",
                block_id="page-0001-block-0007",
                block_index=7,
            ),
        ],
        rag_tables=[],
    )

    assert [(record["target_label"], record["resolved"]) for record in result.cross_refs] == [
        ("Section 1", True),
        ("Table 1", True),
    ]
    assert result.unresolved_cross_ref_count == 0
    reference_units = [record for record in result.semantic_units if record["semantic_type"] == "reference"]
    assert len(reference_units) == 2


def test_cross_ref_guardrails_skip_external_appendix_table_terms_and_generic_registers() -> None:
    result = build_semantic_layer(
        text_block_records=[
            _text_block(
                "The Register command shall complete. RFC 9562 Appendix B defines UUID text. "
                "MSI-X Table BIR describes the BAR indicator register. "
                "Section 2.12 of RFC 7296 gives external IKE guidance.",
            )
        ],
        rag_tables=[],
    )

    assert result.cross_refs == []
    assert result.unresolved_cross_ref_count == 0


def test_register_cross_refs_are_kept_only_for_real_identifier_targets() -> None:
    rag_tables = normalize_rag_table_payload(
        [
            {
                "page": 1,
                "table_index": 1,
                "headers": ["Field", "Bits", "Description"],
                "records": [
                    {
                        "page": 1,
                        "table_index": 1,
                        "row_index": 1,
                        "headers": ["Field", "Bits", "Description"],
                        "cells": {"Field": "CAP.NSSRS", "Bits": "36", "Description": "NVM Subsystem Reset Supported"},
                        "row_text": "Field = CAP.NSSRS | Bits = 36 | Description = NVM Subsystem Reset Supported",
                    }
                ],
            }
        ]
    )

    result = build_semantic_layer(
        text_block_records=[
            _text_block("Register CAP.NSSRS shall be set when subsystem reset is supported.")
        ],
        rag_tables=rag_tables,
    )

    assert [(record["target_type"], record["target_label"], record["resolved"]) for record in result.cross_refs] == [
        ("register", "Register CAP.NSSRS", True)
    ]
    assert result.unresolved_cross_ref_count == 0


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
