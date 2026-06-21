from __future__ import annotations

from pathlib import Path

from pdf2md.config import Config
from pdf2md.models import RagTableOutputMode
from pdf2md.output_writers import (
    write_domain_unit_output,
    write_figure_description_output,
    write_figure_ocr_evidence_output,
    write_figure_rag_output,
    write_figure_structure_output,
    write_page_layout_output,
    write_rag_table_outputs,
    write_rag_text_block_output,
    write_requirement_traceability_output,
    write_retrieval_chunk_output,
    write_semantic_layer_outputs,
    write_technical_table_output,
)
from pdf2md.serializers.rag_chunks import serialize_retrieval_chunks_jsonl
from pdf2md.serializers.rag_domain_adapters import serialize_domain_units_jsonl
from pdf2md.serializers.rag_figure_semantics import (
    serialize_figure_descriptions_jsonl,
    serialize_figure_structures_jsonl,
)
from pdf2md.serializers.rag_figures import serialize_figures_jsonl
from pdf2md.serializers.rag_layout import serialize_page_layout_jsonl
from pdf2md.serializers.rag_ocr_evidence import serialize_region_ocr_evidence_jsonl
from pdf2md.serializers.rag_requirements import serialize_requirement_traceability_jsonl
from pdf2md.serializers.rag_semantics import (
    serialize_cross_refs_jsonl,
    serialize_requirements_jsonl,
    serialize_semantic_units_jsonl,
)
from pdf2md.serializers.rag_tables import serialize_rag_tables_jsonl
from pdf2md.serializers.rag_text_blocks import serialize_text_blocks_jsonl
from pdf2md.serializers.rag_technical_tables import serialize_technical_tables_jsonl


def _config(tmp_path: Path) -> Config:
    return Config(input_pdf=tmp_path / "input.pdf", output_dir=tmp_path)


def _records() -> list[dict]:
    return [
        {
            "id": "alpha",
            "page": 1,
            "text": "원문 보존",
            "bbox": [1.0, 2.0, 3.0, 4.0],
            "nested": {"status": "ok", "values": [1, 2]},
        },
        {
            "id": "beta",
            "page": 2,
            "text": "sidecar line",
            "source_refs": [{"source_type": "text_block", "source_id": "page-0002-block-0001"}],
        },
    ]


def test_streaming_sidecar_writers_match_existing_jsonl_serializers(tmp_path: Path) -> None:
    config = _config(tmp_path)
    records = _records()

    assert write_rag_text_block_output(config, records) == (2, 1)
    assert (tmp_path / "text_blocks_rag.jsonl").read_text(encoding="utf-8") == serialize_text_blocks_jsonl(records)

    assert write_retrieval_chunk_output(config, records) == (2, 1)
    assert (tmp_path / "retrieval_chunks_rag.jsonl").read_text(encoding="utf-8") == serialize_retrieval_chunks_jsonl(
        records
    )

    assert write_page_layout_output(config, records) == (2, 1)
    assert (tmp_path / "page_layout_rag.jsonl").read_text(encoding="utf-8") == serialize_page_layout_jsonl(records)

    assert write_figure_rag_output(config, records) == (2, 1)
    assert (tmp_path / "figures_rag.jsonl").read_text(encoding="utf-8") == serialize_figures_jsonl(records)

    assert write_figure_ocr_evidence_output(config, records) == (2, 1)
    assert (tmp_path / "figure_ocr_evidence_rag.jsonl").read_text(
        encoding="utf-8"
    ) == serialize_region_ocr_evidence_jsonl(records)

    assert write_figure_description_output(config, records) == (2, 1)
    assert (tmp_path / "figure_descriptions_rag.jsonl").read_text(
        encoding="utf-8"
    ) == serialize_figure_descriptions_jsonl(records)

    assert write_figure_structure_output(config, records) == (2, 1)
    assert (tmp_path / "figure_structures_rag.jsonl").read_text(
        encoding="utf-8"
    ) == serialize_figure_structures_jsonl(records)

    assert write_domain_unit_output(config, records) == (2, 1)
    assert (tmp_path / "domain_units_rag.jsonl").read_text(encoding="utf-8") == serialize_domain_units_jsonl(records)

    assert write_requirement_traceability_output(config, records) == (2, 1)
    assert (tmp_path / "requirement_traceability_rag.jsonl").read_text(
        encoding="utf-8"
    ) == serialize_requirement_traceability_jsonl(records)

    assert write_technical_table_output(config, records) == (2, 1)
    assert (tmp_path / "technical_tables_rag.jsonl").read_text(
        encoding="utf-8"
    ) == serialize_technical_tables_jsonl(records)


def test_streaming_semantic_and_table_writers_match_existing_serializers(tmp_path: Path) -> None:
    config = _config(tmp_path)
    records = _records()

    assert write_semantic_layer_outputs(
        config,
        semantic_units=records,
        requirements=records[:1],
        cross_refs=[],
    ) == (2, 1, 1, 1, 0, 1)
    assert (tmp_path / "semantic_units_rag.jsonl").read_text(encoding="utf-8") == serialize_semantic_units_jsonl(
        records
    )
    assert (tmp_path / "requirements_rag.jsonl").read_text(encoding="utf-8") == serialize_requirements_jsonl(
        records[:1]
    )
    assert (tmp_path / "cross_refs_rag.jsonl").read_text(encoding="utf-8") == serialize_cross_refs_jsonl([])

    rag_tables = [
        {
            "page": 1,
            "table_index": 1,
            "source_mode": "gfm",
            "records": [
                {"page": 1, "table_index": 1, "row_index": 1, "row_text": "A | B"},
                {"page": 1, "table_index": 1, "row_index": 2, "row_text": "한글 | 값"},
            ],
        }
    ]
    assert write_rag_table_outputs(config=config, output_mode=RagTableOutputMode.JSONL, rag_tables=rag_tables) == (2, 1)
    assert (tmp_path / "tables_rag.jsonl").read_text(encoding="utf-8") == serialize_rag_tables_jsonl(rag_tables)
