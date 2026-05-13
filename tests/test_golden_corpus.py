from __future__ import annotations

import json
from pathlib import Path

from fixtures.pdf_builder import (
    build_complex_table_pdf,
    build_bottom_footnote_pdf,
    build_code_block_pdf,
    build_continued_table_pdf,
    build_font_heading_pdf,
    build_grouped_list_pdf,
    build_image_only_pdf,
    build_korean_text_pdf,
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
    build_two_column_pdf,
    build_uppercase_body_pdf,
)

from pdf2md.config import Config
from pdf2md.models import RagTableOutputMode
from pdf2md.pipeline import run_conversion
from helpers.normalize_outputs import normalize_manifest, normalize_report


GOLDEN_ROOT = Path("tests/golden/corpus")


def _normalize_jsonl_sidecar(content: str, sidecar_name: str) -> str:
    if sidecar_name not in {"figures_rag.jsonl", "retrieval_chunks_rag.jsonl"} or not content.strip():
        return content
    records = []
    for line in content.splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if sidecar_name == "figures_rag.jsonl" and record.get("sha256"):
            record["sha256"] = "<sha256>"
        if sidecar_name == "retrieval_chunks_rag.jsonl":
            record.pop("schema_version", None)
            record.pop("source_sha256", None)
        records.append(record)
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + ("\n" if records else "")


def test_deterministic_pdf_fixture_builder_covers_priority_corpus(tmp_path: Path) -> None:
    builders = {
        "single_column.pdf": build_single_column_pdf,
        "two_column.pdf": build_two_column_pdf,
        "header_footer.pdf": build_repeated_header_footer_pdf,
        "simple_table.pdf": build_simple_table_pdf,
        "complex_table.pdf": build_complex_table_pdf,
        "continued_table.pdf": build_continued_table_pdf,
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
        "header_footer": (build_repeated_header_footer_pdf, {"remove_header_footer": True}),
        "simple_table": (build_simple_table_pdf, {"rag_table_output": RagTableOutputMode.BOTH}),
        "complex_table": (build_complex_table_pdf, {"rag_table_output": RagTableOutputMode.BOTH}),
        "continued_table": (build_continued_table_pdf, {"rag_table_output": RagTableOutputMode.BOTH}),
        "repeated_template_table": (
            build_repeated_template_table_pdf,
            {"rag_table_output": RagTableOutputMode.BOTH},
        ),
        "repeated_image": (build_repeated_image_pdf, {"dedupe_images": True}),
        "structured_text": (build_structured_text_pdf, {"repair_hyphenation": True}),
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
        assert normalize_manifest(json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))) == json.loads(
            (golden_dir / "manifest.json").read_text(encoding="utf-8")
        )
        assert normalize_report(json.loads((output_dir / "report.json").read_text(encoding="utf-8"))) == json.loads(
            (golden_dir / "report.json").read_text(encoding="utf-8")
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
