from __future__ import annotations

import json
from pathlib import Path

from fixtures.pdf_builder import (
    build_appendix_clause_requirement_pdf,
    build_complex_table_pdf,
    build_bottom_footnote_pdf,
    build_code_block_pdf,
    build_continued_table_pdf,
    build_diagram_suite_pdf,
    build_font_heading_pdf,
    build_grouped_list_pdf,
    build_image_only_pdf,
    build_korean_text_pdf,
    build_layout_stress_pdf,
    build_nvme_base_slice_pdf,
    build_nvme_command_set_slice_pdf,
    build_password_pdf,
    build_repeated_template_table_pdf,
    build_repeated_header_footer_pdf,
    build_repeated_image_pdf,
    build_simple_table_pdf,
    build_single_column_pdf,
    build_semantic_cross_refs_pdf,
    build_semantic_definitions_pdf,
    build_semantic_requirements_pdf,
    build_semantic_table_parameters_pdf,
    build_structured_text_pdf,
    build_table_accuracy_pack_pdf,
    build_two_column_pdf,
    build_uppercase_body_pdf,
)

from pdf2md.config import Config
from pdf2md.models import DomainAdapterMode, RagTableOutputMode
from pdf2md.pipeline import run_conversion
from helpers.normalize_outputs import normalize_manifest, normalize_report


GOLDEN_ROOT = Path("tests/golden/corpus")
STABLE_METADATA_FIELDS = {
    "source_sha256",
    "source_dedupe_key",
    "stable_source_id",
    "stable_requirement_seed",
}


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _nvme_base_slice_options() -> dict:
    return {
        "rag_profile": "technical_spec_rag",
        "rag_table_output": RagTableOutputMode.BOTH,
        "domain_adapter": DomainAdapterMode.NVME,
        "repair_hyphenation": True,
        "retrieval_tokenizer": "regex",
        "rag_contextual_embedding_text": True,
        "rag_merge_sibling_text_chunks": True,
        "rag_chunk_relationship_metadata": True,
    }


def _normalize_jsonl_sidecar(content: str, sidecar_name: str) -> str:
    if not sidecar_name.endswith(".jsonl") or not content.strip():
        return content
    records = []
    for line in content.splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        for field in STABLE_METADATA_FIELDS:
            record.pop(field, None)
        if sidecar_name == "figures_rag.jsonl":
            if record.get("sha256"):
                record["sha256"] = "<sha256>"
            if record.get("crop_content_ratio") is not None:
                record["crop_content_ratio"] = "<crop_content_ratio>"
        if sidecar_name == "retrieval_chunks_rag.jsonl":
            record.pop("schema_version", None)
        records.append(record)
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + ("\n" if records else "")


def test_deterministic_pdf_fixture_builder_covers_priority_corpus(tmp_path: Path) -> None:
    builders = {
        "single_column.pdf": build_single_column_pdf,
        "two_column.pdf": build_two_column_pdf,
        "layout_stress.pdf": build_layout_stress_pdf,
        "header_footer.pdf": build_repeated_header_footer_pdf,
        "simple_table.pdf": build_simple_table_pdf,
        "complex_table.pdf": build_complex_table_pdf,
        "continued_table.pdf": build_continued_table_pdf,
        "table_accuracy_pack.pdf": build_table_accuracy_pack_pdf,
        "nvme_base_slice.pdf": build_nvme_base_slice_pdf,
        "nvme_command_set_slice.pdf": build_nvme_command_set_slice_pdf,
        "diagram_suite.pdf": build_diagram_suite_pdf,
        "repeated_template_table.pdf": build_repeated_template_table_pdf,
        "repeated_image.pdf": build_repeated_image_pdf,
        "image_only.pdf": build_image_only_pdf,
        "korean.pdf": build_korean_text_pdf,
        "structured_text.pdf": build_structured_text_pdf,
        "font_heading.pdf": build_font_heading_pdf,
        "uppercase_body.pdf": build_uppercase_body_pdf,
        "grouped_list.pdf": build_grouped_list_pdf,
        "code_block.pdf": build_code_block_pdf,
        "bottom_footnote.pdf": build_bottom_footnote_pdf,
        "semantic_requirements.pdf": build_semantic_requirements_pdf,
        "semantic_definitions.pdf": build_semantic_definitions_pdf,
        "semantic_cross_refs.pdf": build_semantic_cross_refs_pdf,
        "semantic_table_parameters.pdf": build_semantic_table_parameters_pdf,
        "appendix_clause_requirements.pdf": build_appendix_clause_requirement_pdf,
        "password.pdf": build_password_pdf,
    }

    for filename, builder in builders.items():
        path = tmp_path / filename
        builder(path)
        assert path.exists()
        assert path.stat().st_size > 0


def test_synthetic_corpus_matches_golden_outputs(tmp_path: Path) -> None:
    cases = {
        "single_column": (build_single_column_pdf, {}),
        "two_column": (build_two_column_pdf, {}),
        "layout_stress": (build_layout_stress_pdf, {}),
        "header_footer": (build_repeated_header_footer_pdf, {"remove_header_footer": True}),
        "simple_table": (build_simple_table_pdf, {"rag_table_output": RagTableOutputMode.BOTH}),
        "complex_table": (build_complex_table_pdf, {"rag_table_output": RagTableOutputMode.BOTH}),
        "continued_table": (build_continued_table_pdf, {"rag_table_output": RagTableOutputMode.BOTH}),
        "table_accuracy_pack": (build_table_accuracy_pack_pdf, {"rag_table_output": RagTableOutputMode.BOTH}),
        "nvme_base_slice": (build_nvme_base_slice_pdf, _nvme_base_slice_options()),
        "diagram_suite": (build_diagram_suite_pdf, {"figure_crop_fallback": True}),
        "repeated_template_table": (
            build_repeated_template_table_pdf,
            {"rag_table_output": RagTableOutputMode.BOTH},
        ),
        "repeated_image": (build_repeated_image_pdf, {"dedupe_images": True}),
        "structured_text": (build_structured_text_pdf, {"repair_hyphenation": True}),
        "korean": (build_korean_text_pdf, {}),
        "font_heading": (build_font_heading_pdf, {}),
        "uppercase_body": (build_uppercase_body_pdf, {}),
        "grouped_list": (build_grouped_list_pdf, {}),
        "code_block": (build_code_block_pdf, {}),
        "bottom_footnote": (build_bottom_footnote_pdf, {}),
        "semantic_requirements": (build_semantic_requirements_pdf, {}),
        "semantic_definitions": (build_semantic_definitions_pdf, {}),
        "semantic_cross_refs": (build_semantic_cross_refs_pdf, {"rag_table_output": RagTableOutputMode.BOTH}),
        "semantic_table_parameters": (
            build_semantic_table_parameters_pdf,
            {"rag_table_output": RagTableOutputMode.BOTH},
        ),
        "password": (lambda path: build_password_pdf(path, password="secret"), {"password": "secret"}),
    }

    for case_name, (builder, options) in cases.items():
        pdf_path = tmp_path / f"{case_name}.pdf"
        output_dir = tmp_path / case_name
        builder(pdf_path)
        result = run_conversion(
            Config(
                input_pdf=pdf_path,
                output_dir=output_dir,
                keep_page_markers=True,
                **options,
            )
        )

        assert result.exit_code in {0, 2}
        golden_dir = GOLDEN_ROOT / case_name
        assert (output_dir / "document.md").read_text(encoding="utf-8") == (
            golden_dir / "document.md"
        ).read_text(encoding="utf-8")
        assert normalize_manifest(json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))) == (
            normalize_manifest(json.loads((golden_dir / "manifest.json").read_text(encoding="utf-8")))
        )
        assert normalize_report(json.loads((output_dir / "report.json").read_text(encoding="utf-8"))) == (
            normalize_report(json.loads((golden_dir / "report.json").read_text(encoding="utf-8")))
        )
        for sidecar_name in (
            "rag_tables.md",
            "tables_rag.jsonl",
            "text_blocks_rag.jsonl",
            "semantic_units_rag.jsonl",
            "requirements_rag.jsonl",
            "cross_refs_rag.jsonl",
            "requirement_traceability_rag.jsonl",
            "technical_tables_rag.jsonl",
            "domain_units_rag.jsonl",
            "retrieval_chunks_rag.jsonl",
            "figures_rag.jsonl",
        ):
            golden_sidecar = golden_dir / sidecar_name
            output_sidecar = output_dir / sidecar_name
            if golden_sidecar.exists():
                assert _normalize_jsonl_sidecar(output_sidecar.read_text(encoding="utf-8"), sidecar_name) == (
                    _normalize_jsonl_sidecar(golden_sidecar.read_text(encoding="utf-8"), sidecar_name)
                )
            else:
                assert not output_sidecar.exists()


def test_nvme_base_slice_golden_sidecars_cover_adapter_contract(tmp_path: Path) -> None:
    pdf_path = tmp_path / "nvme_base_slice.pdf"
    output_dir = tmp_path / "nvme_base_slice"
    build_nvme_base_slice_pdf(pdf_path)

    result = run_conversion(
        Config(
            input_pdf=pdf_path,
            output_dir=output_dir,
            keep_page_markers=True,
            **_nvme_base_slice_options(),
        )
    )

    assert result.exit_code == 0
    technical_tables = _read_jsonl(output_dir / "technical_tables_rag.jsonl")
    domain_units = _read_jsonl(output_dir / "domain_units_rag.jsonl")
    traces = _read_jsonl(output_dir / "requirement_traceability_rag.jsonl")

    assert {"command_opcode", "log_page", "feature_identifier", "register_field"} <= {
        record["unit_type"] for record in technical_tables
    }
    assert all(record["table_row_id"] for record in technical_tables)
    assert all(record["stable_source_id"] and record["stable_requirement_seed"] for record in technical_tables)
    command_table = next(record for record in technical_tables if record["unit_type"] == "command_opcode")
    assert command_table["command_context"] == "Identify"
    assert command_table["related_command_unit_id"] == command_table["technical_table_unit_id"]
    assert command_table["relationship_hints"] == ["command_anchor"]

    units_by_type = {record["unit_type"]: record for record in domain_units}
    assert {"command", "log_page", "feature", "register_field"} <= set(units_by_type)
    assert units_by_type["command"]["normalized_fields"]["opcode"] == "06h"
    assert units_by_type["command"]["normalized_fields"]["command_context"] == "Identify"
    assert units_by_type["command"]["normalized_fields"]["relationship_hints"] == ["command_anchor"]
    assert units_by_type["log_page"]["normalized_fields"]["log_identifier"] == "02h"
    assert units_by_type["feature"]["normalized_fields"]["feature_identifier"] == "0Ch"
    assert units_by_type["register_field"]["normalized_fields"]["register_name"] == "CAP"
    assert units_by_type["register_field"]["normalized_fields"]["offset"] == "0x0000"
    assert all(record["source_refs"][0]["source_type"] == "table_row" for record in domain_units)
    assert all(record["source_refs"][1]["source_type"] == "technical_table_unit" for record in domain_units)
    assert all(record["stable_source_id"] and record["stable_requirement_seed"] for record in domain_units)

    trace_kinds = {record["candidate_kind"]: record for record in traces}
    assert trace_kinds["normative_requirement"]["is_requirement_candidate"] is True
    assert trace_kinds["normative_requirement"]["requirement_id"] is None
    assert trace_kinds["note"]["is_requirement_candidate"] is False
    assert trace_kinds["example"]["is_requirement_candidate"] is False
    assert all(record["stable_source_id"] and record["stable_requirement_seed"] for record in traces)
