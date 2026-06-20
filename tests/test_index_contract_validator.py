from __future__ import annotations

import json
from pathlib import Path

from pdf2md.models import IndexContractReport
from scripts.validate_index_contract import _metadata_for_target, main, validate_index_contract


SOURCE_SHA256 = "a" * 64


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def _valid_chunk(**overrides) -> dict:
    text = overrides.pop("text", "The controller shall return SUCCESS.")
    chunk = {
        "chunk_id": "chunk-000001",
        "schema_version": "1.0",
        "chunk_index": 1,
        "chunk_type": "requirement",
        "text": text,
        "source_sha256": SOURCE_SHA256,
        "source_refs": [
            {
                "source_type": "requirement_trace",
                "source_id": "req-trace-000001",
                "page": 1,
                "bbox": [72.0, 92.0, 240.0, 102.0],
            }
        ],
        "page_range": [1, 1],
        "bbox": [72.0, 92.0, 240.0, 102.0],
        "heading_path": ["1 Requirements"],
        "semantic_types": ["requirement"],
        "normative_strength": "required",
        "retrieval_priority": 100,
        "char_count": len(text),
        "token_estimate": 9,
        "section_path": "1 Requirements",
        "chunk_group_id": "requirement-page-0001",
        "source_record_count": 1,
        "source_dedupe_key": "req-trace-000001",
        "chunk_boundary_policy": "source_record",
        "chunk_boundary_reasons": ["requirement_boundary"],
    }
    chunk.update(overrides)
    return chunk


def _valid_table_row(**overrides) -> dict:
    record = {
        "table_id": "page-0001-table-0001",
        "table_row_id": "page-0001-table-0001-row-0001",
        "page": 1,
        "table_index": 1,
        "source_mode": "html",
        "headers": ["Bits", "Field", "Description"],
        "row_index": 1,
        "cells": {"Bits": "07:00", "Field": "STATUS", "Description": "Status field"},
        "row_text": "Bits = 07:00 | Field = STATUS | Description = Status field",
        "bbox": [72.0, 92.0, 240.0, 122.0],
        "quality_score": 0.91,
        "fallback_reasons": ["AMBIGUOUS_GRID"],
        "header_depth": 1,
        "header_confidence": 0.86,
        "rag_header_strategy": "single_header_row",
    }
    record.update(overrides)
    return record


def _valid_requirement_trace(**overrides) -> dict:
    record = {
        "trace_id": "req-trace-000001",
        "trace_index": 1,
        "requirement_id": "REQ-1",
        "normative_strength": "required",
        "text": "REQ-1 shall return GOOD when enabled.",
        "condition": "when enabled",
        "applicability": None,
        "dependency_refs": ["Section 1.2"],
        "exception_text": None,
        "testability_hint": "directly_testable",
        "page_range": [1, 1],
        "bbox": [72.0, 92.0, 240.0, 122.0],
        "heading_path": ["1 Requirements"],
        "source_refs": [
            {
                "source_type": "requirement",
                "source_id": "page-0001-sem-0001",
                "page": 1,
                "bbox": [72.0, 92.0, 240.0, 122.0],
            }
        ],
        "classification_confidence": 0.9,
        "classification_reasons": ["semantic_requirement"],
    }
    record.update(overrides)
    return record


def _valid_technical_table(**overrides) -> dict:
    record = {
        "technical_table_unit_id": "tech-table-000001",
        "technical_table_unit_index": 1,
        "unit_type": "bitfield",
        "page": 1,
        "table_id": "page-0001-table-0001",
        "table_row_id": "page-0001-table-0001-row-0001",
        "row_index": 1,
        "text": "Bits = 07:00 | Field = STATUS | Description = Status field",
        "raw_cells": {"Bits": "07:00", "Field": "STATUS", "Description": "Status field"},
        "bit_range": "07:00",
        "field_name": "STATUS",
        "value": None,
        "meaning": "Status field",
        "reset_default": None,
        "access": None,
        "requirement_ref": None,
        "opcode": None,
        "command": None,
        "log_identifier": None,
        "feature_identifier": None,
        "bbox": [72.0, 92.0, 240.0, 122.0],
        "source_refs": [
            {
                "source_type": "table_row",
                "source_id": "page-0001-table-0001-row-0001",
                "page": 1,
                "table_id": "page-0001-table-0001",
                "row_index": 1,
                "bbox": [72.0, 92.0, 240.0, 122.0],
            }
        ],
        "classification_confidence": 0.9,
        "classification_reasons": ["field_and_bits"],
    }
    record.update(overrides)
    return record


def test_index_contract_accepts_valid_retrieval_chunk_for_all_targets(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "retrieval_chunks_rag.jsonl", [_valid_chunk()])

    report = validate_index_contract(output_dir=tmp_path, target="all")

    validated = IndexContractReport.model_validate(report)
    assert validated.status == "passed"
    assert validated.passed is True
    assert validated.summary.checked_files == 1
    assert validated.summary.checked_records == 1
    assert validated.findings == []
    assert validated.targets == ["openai", "azure-ai-search", "langchain", "llamaindex"]


def test_index_contract_validates_core_sidecar_required_fields(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "retrieval_chunks_rag.jsonl", [_valid_chunk()])
    _write_jsonl(tmp_path / "tables_rag.jsonl", [_valid_table_row()])
    _write_jsonl(tmp_path / "requirement_traceability_rag.jsonl", [_valid_requirement_trace()])
    _write_jsonl(tmp_path / "technical_tables_rag.jsonl", [_valid_technical_table()])

    report = validate_index_contract(output_dir=tmp_path, target="all")

    assert report["status"] == "passed"
    assert report["summary"]["checked_files"] == 4
    assert report["summary"]["checked_records"] == 4
    assert report["findings"] == []


def test_index_contract_validates_visual_chunk_contract(tmp_path: Path) -> None:
    figure_ref = {
        "source_type": "figure",
        "source_id": "page-0001-figure-0001",
        "page": 1,
        "bbox": [72.0, 120.0, 420.0, 320.0],
    }
    description_ref = {
        "source_type": "figure_description",
        "source_id": "figure-description-000001",
        "page": 1,
        "bbox": [72.0, 120.0, 420.0, 320.0],
    }
    structure_ref = {
        "source_type": "figure_structure",
        "source_id": "figure-structure-000001",
        "page": 1,
        "bbox": [72.0, 120.0, 420.0, 320.0],
    }
    _write_jsonl(
        tmp_path / "retrieval_chunks_rag.jsonl",
        [
            _valid_chunk(
                chunk_type="figure_description",
                text="figure_description: State transition diagram.",
                source_refs=[figure_ref, description_ref],
                source_dedupe_key="page-0001-figure-0001|figure-description-000001",
                semantic_types=["figure_description", "generated_text", "state_machine"],
                normative_strength=None,
                retrieval_priority=62,
                generated_text=True,
                generation_strategy="deterministic_context_summary",
            ),
            _valid_chunk(
                chunk_id="chunk-000002",
                chunk_index=2,
                chunk_type="figure_structure",
                text="figure_structure: state_machine.",
                source_refs=[figure_ref, structure_ref],
                source_dedupe_key="page-0001-figure-0001|figure-structure-000001",
                semantic_types=["figure_structure", "state_machine"],
                normative_strength=None,
                retrieval_priority=64,
                generated_text=False,
                derived_from_context=True,
            ),
        ],
    )
    _write_jsonl(
        tmp_path / "figure_descriptions_rag.jsonl",
        [
            {
                "description_id": "figure-description-000001",
                "figure_id": "page-0001-figure-0001",
                "page": 1,
                "text": "figure_description: State transition diagram.",
                "bbox": [72.0, 120.0, 420.0, 320.0],
                "source_refs": [figure_ref],
                "generated_text": True,
                "generation_strategy": "deterministic_context_summary",
            }
        ],
    )
    _write_jsonl(
        tmp_path / "figure_structures_rag.jsonl",
        [
            {
                "structure_id": "figure-structure-000001",
                "figure_id": "page-0001-figure-0001",
                "page": 1,
                "text": "figure_structure: state_machine.",
                "bbox": [72.0, 120.0, 420.0, 320.0],
                "source_refs": [figure_ref],
                "generated_text": False,
                "derived_from_context": True,
            }
        ],
    )

    report = validate_index_contract(output_dir=tmp_path, target="all")

    assert report["status"] == "passed"
    assert report["findings"] == []
    metadata = _metadata_for_target(
        json.loads((tmp_path / "retrieval_chunks_rag.jsonl").read_text(encoding="utf-8").splitlines()[0]),
        "openai",
    )
    assert metadata["generated_text"] is True
    assert metadata["generation_strategy"] == "deterministic_context_summary"


def test_index_contract_reports_visual_chunk_contract_errors(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "retrieval_chunks_rag.jsonl",
        [
            _valid_chunk(
                chunk_type="figure_description",
                text="figure_description: missing visual provenance.",
                source_refs=[{"source_type": "figure_description", "source_id": "figure-description-000001", "page": 1}],
                source_dedupe_key="figure-description-000001",
                semantic_types=["figure_description"],
                normative_strength=None,
                retrieval_priority=62,
                generated_text=False,
                generation_strategy="context_summary",
            )
        ],
    )
    _write_jsonl(
        tmp_path / "figure_descriptions_rag.jsonl",
        [
            {
                "description_id": "figure-description-000001",
                "figure_id": "page-0001-figure-0001",
                "page": 1,
                "text": "figure_description: missing strategy.",
                "source_refs": [{"source_type": "figure", "source_id": "page-0001-figure-0001", "page": 1}],
                "generated_text": False,
                "generation_strategy": "context_summary",
            }
        ],
    )

    report = validate_index_contract(output_dir=tmp_path, target="openai")

    codes = [finding["code"] for finding in report["findings"]]
    assert report["status"] == "failed"
    assert "missing_visual_source_ref" in codes
    assert "missing_generated_text_flag" in codes
    assert "invalid_generation_strategy" in codes


def test_index_contract_reports_core_sidecar_schema_errors(tmp_path: Path) -> None:
    broken_table = _valid_table_row(headers="Bits", cells=[], quality_score="good")
    broken_trace = _valid_requirement_trace(trace_index="1", page_range=[2, 1], source_refs=[])
    broken_technical = _valid_technical_table(raw_cells=[], classification_reasons="field_and_bits")
    broken_technical.pop("unit_type")
    _write_jsonl(tmp_path / "retrieval_chunks_rag.jsonl", [_valid_chunk()])
    _write_jsonl(tmp_path / "tables_rag.jsonl", [broken_table])
    _write_jsonl(tmp_path / "requirement_traceability_rag.jsonl", [broken_trace])
    _write_jsonl(tmp_path / "technical_tables_rag.jsonl", [broken_technical])

    report = validate_index_contract(output_dir=tmp_path, target="openai")

    codes = {finding["code"] for finding in report["findings"]}
    assert report["status"] == "failed"
    assert "missing_required_field" in codes
    assert "invalid_string_list_field" in codes
    assert "invalid_object_field" in codes
    assert "invalid_number_field" in codes
    assert "invalid_integer_field" in codes
    assert "invalid_page_range" in codes
    assert "missing_source_refs" in codes


def test_index_contract_target_metadata_preserves_recipe_fields() -> None:
    chunk = _valid_chunk(
        embedding_token_estimate=12,
        merged_source_chunk_ids=["chunk-000010", "chunk-000011"],
        previous_chunk_id="chunk-000000",
        next_chunk_id="chunk-000002",
        section_anchor_chunk_id="chunk-000001",
        parent_section_path="1 Requirements",
        parent_section_anchor_chunk_id="chunk-000000",
        related_chunk_ids=["chunk-000000", "chunk-000002"],
        relationship_reasons=["chunk_group_neighbor", "parent_section_anchor"],
        relationship_strategy="chunk_group_prev_next_section_anchor",
        relationship_metadata_version="2.0",
        chunk_group_index=1,
        chunk_group_count=2,
        section_chunk_index=1,
        section_chunk_count=3,
        context_metadata={
            "metadata_version": "2.0",
            "context_type": "table_row",
            "headers": ["Field", "Description"],
        },
    )

    openai_metadata = _metadata_for_target(chunk, "openai")
    azure_metadata = _metadata_for_target(chunk, "azure-ai-search")
    langchain_metadata = _metadata_for_target(chunk, "langchain")
    llamaindex_metadata = _metadata_for_target(chunk, "llamaindex")

    assert openai_metadata["embedding_token_estimate"] == 12
    assert openai_metadata["merged_source_chunk_ids"] == ["chunk-000010", "chunk-000011"]
    assert openai_metadata["parent_section_anchor_chunk_id"] == "chunk-000000"
    assert openai_metadata["relationship_metadata_version"] == "2.0"
    assert openai_metadata["context_metadata"]["context_type"] == "table_row"
    assert azure_metadata["source_refs_json"].startswith("[")
    assert azure_metadata["context_metadata_json"].startswith("{")
    assert azure_metadata["previous_chunk_id"] == "chunk-000000"
    assert langchain_metadata["source_text"] == chunk["text"]
    assert langchain_metadata["schema_version"] == "1.0"
    assert langchain_metadata["relationship_reasons"] == ["chunk_group_neighbor", "parent_section_anchor"]
    assert llamaindex_metadata["source_refs"] == chunk["source_refs"]
    assert llamaindex_metadata["source_sha256"] == SOURCE_SHA256
    assert llamaindex_metadata["chunk_group_count"] == 2


def test_index_contract_reports_required_field_type_and_source_ref_errors(tmp_path: Path) -> None:
    broken = _valid_chunk(source_refs=[], page_range=[2, 1], retrieval_priority="high")
    broken.pop("schema_version")
    _write_jsonl(tmp_path / "retrieval_chunks_rag.jsonl", [broken])

    report = validate_index_contract(output_dir=tmp_path, target="openai")

    codes = [finding["code"] for finding in report["findings"]]
    assert report["status"] == "failed"
    assert report["summary"]["error_count"] >= 4
    assert "missing_required_field" in codes
    assert "schema_version_mismatch" in codes
    assert "missing_source_refs" in codes
    assert "invalid_page_range" in codes
    assert "invalid_integer_field" in codes
    assert report["findings"][0]["severity"] == "error"
    assert report["findings"][0]["line"] == 1


def test_index_contract_reports_metadata_size_guardrail_as_warning(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "retrieval_chunks_rag.jsonl", [_valid_chunk()])

    report = validate_index_contract(output_dir=tmp_path, target="openai", metadata_max_bytes=10)

    assert report["status"] == "warning"
    assert report["passed"] is True
    assert report["summary"]["error_count"] == 0
    assert "metadata_size_exceeds_limit" in {finding["code"] for finding in report["findings"]}


def test_index_contract_validates_optional_chunk_relationship_targets(tmp_path: Path) -> None:
    first = _valid_chunk(
        next_chunk_id="chunk-000002",
        related_chunk_ids=["chunk-000002"],
        relationship_strategy="chunk_group_prev_next_section_anchor",
    )
    second = _valid_chunk(
        chunk_id="chunk-000002",
        chunk_index=2,
        text="The controller shall report status.",
        source_refs=[
            {
                "source_type": "requirement_trace",
                "source_id": "req-trace-000002",
                "page": 1,
                "bbox": [72.0, 112.0, 240.0, 122.0],
            }
        ],
        source_dedupe_key="req-trace-000002",
        previous_chunk_id="chunk-000001",
        section_anchor_chunk_id="chunk-000001",
        parent_section_path="1 Requirements",
        parent_section_anchor_chunk_id="chunk-000001",
        related_chunk_ids=["chunk-000001"],
        relationship_strategy="chunk_group_prev_next_section_anchor",
        relationship_metadata_version="2.0",
    )
    _write_jsonl(tmp_path / "retrieval_chunks_rag.jsonl", [first, second])

    report = validate_index_contract(output_dir=tmp_path, target="openai")

    assert report["status"] == "passed"
    assert report["findings"] == []


def test_index_contract_reports_missing_chunk_relationship_targets(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "retrieval_chunks_rag.jsonl",
        [
            _valid_chunk(
                previous_chunk_id="chunk-missing",
                parent_section_anchor_chunk_id="chunk-parent-missing",
                related_chunk_ids=["chunk-missing"],
                relationship_strategy="chunk_group_prev_next_section_anchor",
            )
        ],
    )

    report = validate_index_contract(output_dir=tmp_path, target="openai")

    assert report["status"] == "failed"
    assert {finding["code"] for finding in report["findings"]} == {"relationship_target_missing"}


def test_index_contract_validates_page_layout_sidecar(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "retrieval_chunks_rag.jsonl", [_valid_chunk()])
    _write_jsonl(
        tmp_path / "page_layout_rag.jsonl",
        [
            {
                "layout_id": "page-0001-layout",
                "schema_version": "1.0",
                "page": 1,
                "source_sha256": SOURCE_SHA256,
                "reading_order_strategy": "multi_column",
                "column_count_estimate": 2,
                "multi_column_detected": True,
                "region_ref_count": 1,
                "region_refs": [
                    {
                        "region_type": "text_block",
                        "source_type": "text_block",
                        "source_id": "page-0001-block-0001",
                    }
                ],
                "caption_link_count": 0,
                "caption_links": [],
            }
        ],
    )

    report = validate_index_contract(output_dir=tmp_path, target="openai")

    assert report["status"] == "passed"
    assert report["findings"] == []


def test_index_contract_reports_invalid_page_layout_sidecar(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "retrieval_chunks_rag.jsonl", [_valid_chunk()])
    _write_jsonl(
        tmp_path / "page_layout_rag.jsonl",
        [
            {
                "layout_id": "page-0001-layout",
                "schema_version": "1.0",
                "page": 1,
                "source_sha256": SOURCE_SHA256,
                "reading_order_strategy": "top",
                "column_count_estimate": 1,
                "multi_column_detected": False,
                "region_ref_count": 2,
                "region_refs": [{"region_type": "text_block"}],
                "caption_link_count": 0,
                "caption_links": [],
            }
        ],
    )

    report = validate_index_contract(output_dir=tmp_path, target="openai")

    assert report["status"] == "failed"
    assert "layout_count_mismatch" in {finding["code"] for finding in report["findings"]}


def test_index_contract_validates_ocr_evidence_sidecar(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "retrieval_chunks_rag.jsonl", [_valid_chunk()])
    _write_jsonl(
        tmp_path / "figure_ocr_evidence_rag.jsonl",
        [
            {
                "evidence_id": "ocr-evidence-000001",
                "schema_version": "1.0",
                "reason_taxonomy_version": "1.0",
                "evidence_type": "region_ocr",
                "target_type": "figure",
                "target_id": "page-0001-figure-0001",
                "page": 1,
                "bbox": [10.0, 20.0, 120.0, 160.0],
                "source_sha256": SOURCE_SHA256,
                "ocr_backend": "tesseract",
                "ocr_lang": "eng",
                "status": "accepted",
                "accepted": True,
                "accepted_reason": "confidence_above_threshold",
                "rejected_reason": None,
                "confidence_threshold": 0.65,
                "confidence": 0.9,
                "ocr_text": "NVME1",
                "candidate": {"text": "NVME1", "confidence": 0.9},
                "rejected": None,
                "report_only": True,
                "text_replaced": False,
                "markdown_inserted": False,
                "source_refs": [
                    {
                        "source_type": "figure",
                        "source_id": "page-0001-figure-0001",
                        "page": 1,
                    }
                ],
            }
        ],
    )

    report = validate_index_contract(output_dir=tmp_path, target="openai")

    assert report["status"] == "passed"
    assert report["findings"] == []


def test_index_contract_reports_invalid_ocr_evidence_sidecar(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "retrieval_chunks_rag.jsonl", [_valid_chunk()])
    _write_jsonl(
        tmp_path / "figure_ocr_evidence_rag.jsonl",
        [
            {
                "evidence_id": "ocr-evidence-000001",
                "schema_version": "1.0",
                "reason_taxonomy_version": "1.0",
                "evidence_type": "region_ocr",
                "target_type": "figure",
                "target_id": "page-0001-figure-0001",
                "page": 1,
                "bbox": [10.0, 20.0, 120.0, 160.0],
                "source_sha256": SOURCE_SHA256,
                "ocr_backend": "tesseract",
                "ocr_lang": "eng",
                "status": "accepted",
                "accepted": True,
                "report_only": False,
                "text_replaced": True,
                "markdown_inserted": True,
                "source_refs": [],
            }
        ],
    )

    report = validate_index_contract(output_dir=tmp_path, target="openai")

    codes = {finding["code"] for finding in report["findings"]}
    assert report["status"] == "failed"
    assert "accepted_ocr_evidence_missing_text" in codes
    assert "ocr_evidence_not_report_only" in codes
    assert "ocr_evidence_markdown_pollution" in codes


def test_index_contract_confidential_safe_detects_paths_filename_and_hash(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "retrieval_chunks_rag.jsonl", [_valid_chunk()])
    _write_jsonl(
        tmp_path / "figures_rag.jsonl",
        [
            {
                "figure_id": "page-0001-figure-0001",
                "page": 1,
                "path": "/Users/example/specs/customer-diagram.png",
                "source_refs": [
                    {
                        "source_type": "figure",
                        "source_id": "page-0001-figure-0001",
                        "page": 1,
                        "path": "/Users/example/specs/customer-diagram.png",
                    }
                ],
            }
        ],
    )
    (tmp_path / "manifest.json").write_text(json.dumps({"input_file": "secret-spec.pdf"}), encoding="utf-8")

    report = validate_index_contract(output_dir=tmp_path, target="openai", confidential_safe=True)

    codes = {finding["code"] for finding in report["findings"]}
    assert report["status"] == "warning"
    assert "confidential_absolute_path" in codes
    assert "confidential_filename_exposed" in codes
    assert "confidential_source_hash_requires_review" in codes
    assert "text_redaction_not_performed" in codes


def test_index_contract_main_writes_report_and_honors_fail_on_error(tmp_path: Path) -> None:
    report_file = tmp_path / "contract.json"

    exit_code = main(
        [
            "--output-dir",
            str(tmp_path),
            "--target",
            "openai",
            "--report-file",
            str(report_file),
            "--fail-on-error",
        ]
    )

    assert exit_code == 1
    payload = json.loads(report_file.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["findings"][0]["code"] == "missing_required_file"
