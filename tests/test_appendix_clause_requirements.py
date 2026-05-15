from __future__ import annotations

import json
from pathlib import Path

from fixtures.pdf_builder import build_appendix_clause_requirement_pdf
from pdf2md.config import Config
from pdf2md.models import DomainAdapterMode, RagTableOutputMode
from pdf2md.pipeline import run_conversion


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_appendix_clause_requirement_table_preserves_heading_context(tmp_path: Path) -> None:
    pdf_path = tmp_path / "appendix_clause_requirements.pdf"
    output_dir = tmp_path / "output"
    build_appendix_clause_requirement_pdf(pdf_path)

    result = run_conversion(
        Config(
            input_pdf=pdf_path,
            output_dir=output_dir,
            keep_page_markers=True,
            rag_table_output=RagTableOutputMode.BOTH,
            domain_adapter=DomainAdapterMode.CUSTOMER_REQUIREMENTS,
        )
    )

    assert result.exit_code == 0
    text_blocks = _read_jsonl(output_dir / "text_blocks_rag.jsonl")
    requirements = _read_jsonl(output_dir / "requirement_traceability_rag.jsonl")
    cross_refs = _read_jsonl(output_dir / "cross_refs_rag.jsonl")
    technical_tables = _read_jsonl(output_dir / "technical_tables_rag.jsonl")
    domain_units = _read_jsonl(output_dir / "domain_units_rag.jsonl")

    assert any(record["text"] == "Appendix A Vendor Requirements" for record in text_blocks)
    body_requirement = next(record for record in requirements if record["requirement_id"] == "VEND-APP-1")
    table_requirement = next(record for record in requirements if record["requirement_id"] == "VEND-APP-2")
    expected_heading_path = ["Appendix A Vendor Requirements", "1.1 Nested Recovery Clause"]
    assert body_requirement["heading_path"] == expected_heading_path
    assert table_requirement["heading_path"] == expected_heading_path
    assert table_requirement["source_refs"][0]["source_type"] == "table_row"
    assert table_requirement["text"] == "The exporter shall keep nested clause headings for vendor tables."

    assert any(
        record["target_type"] == "appendix" and record["target_label"] == "Appendix A" and record["resolved"]
        for record in cross_refs
    )
    assert any(
        record["target_type"] == "table" and record["target_label"] == "Table 1" and record["resolved"]
        for record in cross_refs
    )

    requirement_row = next(record for record in technical_tables if record["requirement_ref"] == "VEND-APP-2")
    assert requirement_row["unit_type"] == "requirement_row"
    assert requirement_row["heading_path"] == expected_heading_path

    domain_record = next(record for record in domain_units if record["name"] == "VEND-APP-2")
    assert domain_record["unit_type"] == "requirement"
    assert domain_record["heading_path"] == expected_heading_path
