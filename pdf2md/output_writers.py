from __future__ import annotations

from typing import Any

from pdf2md.config import Config
from pdf2md.extractors.text import PageLayoutMetadata, TextLine
from pdf2md.models import RagTableOutputMode
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
from pdf2md.serializers.rag_tables import (
    flatten_rag_table_records,
    serialize_rag_tables_jsonl,
    serialize_rag_tables_markdown,
)
from pdf2md.serializers.rag_text_blocks import serialize_text_blocks_jsonl
from pdf2md.serializers.rag_technical_tables import serialize_technical_tables_jsonl
from pdf2md.utils.io import write_json, write_text


def _text_line_payload(line: TextLine) -> dict:
    return {
        "text": line.text,
        "top": line.top,
        "bottom": line.bottom,
        "x0": line.x0,
        "x1": line.x1,
        "font_size": line.font_size,
        "font_family": line.font_family,
        "font_style_hint": line.font_style_hint,
        "line_height": line.line_height,
        "left_indent": line.left_indent,
        "right_indent": line.right_indent,
        "y_band": line.y_band,
    }


def write_debug_artifacts(
    *,
    config: Config,
    selected_pages: list[int],
    raw_lines_by_page: dict[int, list[dict]],
    ordered_lines_by_page: dict[int, list[TextLine]],
    normalized_lines_by_page: dict[int, list[dict]],
    text_metadata_by_page: dict[int, PageLayoutMetadata],
    table_candidates_by_page: dict[int, list[dict]],
    image_candidates_by_page: dict[int, list[dict]],
    table_quality_review_pack: dict[str, Any] | None = None,
) -> None:
    """Write local-only debug artifacts without changing public conversion output."""
    debug_root = config.output_dir / "debug"
    debug_root.mkdir(parents=True, exist_ok=True)
    for page in selected_pages:
        prefix = f"page-{page:04d}"
        metadata = text_metadata_by_page.get(page)
        write_json(
            debug_root / f"{prefix}-raw-lines.json",
            {
                "page": page,
                "metadata": metadata.model_dump(mode="json") if hasattr(metadata, "model_dump") else (
                    metadata.__dict__ if metadata else {}
                ),
                "lines": raw_lines_by_page.get(page, []),
            },
        )
        write_json(
            debug_root / f"{prefix}-ordered-lines.json",
            {
                "page": page,
                "lines": [_text_line_payload(line) for line in ordered_lines_by_page.get(page, [])],
            },
        )
        write_json(
            debug_root / f"{prefix}-normalized-lines.json",
            {
                "page": page,
                "lines": normalized_lines_by_page.get(page, []),
            },
        )
        write_json(
            debug_root / f"{prefix}-table-candidates.json",
            {
                "page": page,
                "candidates": table_candidates_by_page.get(page, []),
            },
        )
        write_json(
            debug_root / f"{prefix}-image-candidates.json",
            {
                "page": page,
                "candidates": image_candidates_by_page.get(page, []),
            },
        )
    if table_quality_review_pack is not None:
        write_json(debug_root / "table-quality-review-pack.json", table_quality_review_pack)


def write_rag_table_outputs(
    *,
    config: Config,
    output_mode: RagTableOutputMode,
    rag_tables: list[dict],
) -> tuple[int, int]:
    """Write optional table sidecars and return record/file counts."""
    if output_mode is RagTableOutputMode.NONE:
        return 0, 0

    record_count = len(flatten_rag_table_records(rag_tables))
    file_count = 0
    if output_mode.writes_markdown():
        write_text(
            config.output_dir / config.rag_tables_markdown_filename,
            serialize_rag_tables_markdown(rag_tables),
        )
        file_count += 1
    if output_mode.writes_jsonl():
        write_text(config.output_dir / config.rag_tables_jsonl_filename, serialize_rag_tables_jsonl(rag_tables))
        file_count += 1
    return record_count, file_count


def write_rag_text_block_output(config: Config, records: list[dict]) -> tuple[int, int]:
    write_text(config.output_dir / config.rag_text_blocks_jsonl_filename, serialize_text_blocks_jsonl(records))
    return len(records), 1


def write_semantic_layer_outputs(
    config: Config,
    *,
    semantic_units: list[dict],
    requirements: list[dict],
    cross_refs: list[dict],
) -> tuple[int, int, int, int, int, int]:
    write_text(config.output_dir / config.semantic_units_jsonl_filename, serialize_semantic_units_jsonl(semantic_units))
    write_text(config.output_dir / config.requirements_jsonl_filename, serialize_requirements_jsonl(requirements))
    write_text(config.output_dir / config.cross_refs_jsonl_filename, serialize_cross_refs_jsonl(cross_refs))
    return len(semantic_units), 1, len(requirements), 1, len(cross_refs), 1


def write_retrieval_chunk_output(config: Config, records: list[dict]) -> tuple[int, int]:
    write_text(config.output_dir / config.retrieval_chunks_jsonl_filename, serialize_retrieval_chunks_jsonl(records))
    return len(records), 1


def write_page_layout_output(config: Config, records: list[dict]) -> tuple[int, int]:
    write_text(config.output_dir / config.page_layout_jsonl_filename, serialize_page_layout_jsonl(records))
    return len(records), 1


def write_figure_rag_output(config: Config, records: list[dict]) -> tuple[int, int]:
    write_text(config.output_dir / config.figures_rag_jsonl_filename, serialize_figures_jsonl(records))
    return len(records), 1


def write_figure_ocr_evidence_output(config: Config, records: list[dict]) -> tuple[int, int]:
    write_text(
        config.output_dir / config.figure_ocr_evidence_jsonl_filename,
        serialize_region_ocr_evidence_jsonl(records),
    )
    return len(records), 1


def write_figure_description_output(config: Config, records: list[dict]) -> tuple[int, int]:
    write_text(
        config.output_dir / config.figure_descriptions_jsonl_filename,
        serialize_figure_descriptions_jsonl(records),
    )
    return len(records), 1


def write_figure_structure_output(config: Config, records: list[dict]) -> tuple[int, int]:
    write_text(
        config.output_dir / config.figure_structures_jsonl_filename,
        serialize_figure_structures_jsonl(records),
    )
    return len(records), 1


def write_domain_unit_output(config: Config, records: list[dict]) -> tuple[int, int]:
    write_text(config.output_dir / config.domain_units_jsonl_filename, serialize_domain_units_jsonl(records))
    return len(records), 1


def write_requirement_traceability_output(config: Config, records: list[dict]) -> tuple[int, int]:
    write_text(
        config.output_dir / config.requirement_traceability_jsonl_filename,
        serialize_requirement_traceability_jsonl(records),
    )
    return len(records), 1


def write_technical_table_output(config: Config, records: list[dict]) -> tuple[int, int]:
    write_text(config.output_dir / config.technical_tables_jsonl_filename, serialize_technical_tables_jsonl(records))
    return len(records), 1
