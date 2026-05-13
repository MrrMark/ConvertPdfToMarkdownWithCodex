from __future__ import annotations

from copy import deepcopy
from typing import Any


def normalize_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(payload)
    options = normalized.get("options")
    if isinstance(options, dict):
        options["version"] = "<version>"
    images = normalized.get("images", [])
    if isinstance(images, list):
        for image in images:
            if isinstance(image, dict) and image.get("sha256"):
                image["sha256"] = "<sha256>"
    return {
        "schema_version": normalized.get("schema_version"),
        "input_file": normalized.get("input_file"),
        "total_pages": normalized.get("total_pages"),
        "selected_pages": normalized.get("selected_pages"),
        "options": options,
        "images": images,
        "tables": normalized.get("tables", []),
        "warnings": normalized.get("warnings", []),
    }


def normalize_report(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(payload)
    normalized["started_at"] = "<timestamp>"
    normalized["finished_at"] = "<timestamp>"
    normalized["duration_ms"] = 0
    summary = normalized.get("summary")
    if isinstance(summary, dict):
        summary["stage_durations_ms"] = {key: 0 for key in summary.get("stage_durations_ms", {})}
        summary["pages_per_second"] = None
    summary_keys = [
        "processed_pages",
        "warning_count",
        "partial_success",
        "total_suppressed_lines",
        "table_total",
        "table_html_count",
        "table_gfm_count",
        "table_fallback_count",
        "table_fallback_reason_counts",
        "table_low_quality_count",
        "table_caption_linked_count",
        "rag_table_output",
        "rag_table_record_count",
        "rag_table_file_count",
        "rag_text_block_record_count",
        "rag_text_block_file_count",
        "semantic_unit_record_count",
        "semantic_unit_file_count",
        "requirement_record_count",
        "requirement_file_count",
        "cross_ref_record_count",
        "cross_ref_file_count",
        "semantic_low_confidence_count",
        "unresolved_cross_ref_count",
        "normative_requirement_count",
        "retrieval_chunk_record_count",
        "retrieval_chunk_file_count",
        "figure_rag_record_count",
        "figure_rag_file_count",
        "domain_unit_record_count",
        "domain_unit_file_count",
        "page_cache_hits",
        "page_cache_misses",
        "text_line_extract_count",
        "heading_count",
        "list_item_count",
        "code_block_count",
        "hyphenation_repair_count",
        "font_heading_candidate_count",
        "footnote_candidate_count",
        "structure_low_confidence_count",
        "pdf_open_count",
        "pages_per_second",
        "stage_durations_ms",
        "table_quality",
    ]
    return {
        "schema_version": normalized.get("schema_version"),
        "status": normalized.get("status"),
        "engine_usage": normalized.get("engine_usage"),
        "page_results": normalized.get("page_results", []),
        "warnings": normalized.get("warnings", []),
        "summary": {key: summary.get(key) for key in summary_keys if key in summary} if isinstance(summary, dict) else {},
    }
