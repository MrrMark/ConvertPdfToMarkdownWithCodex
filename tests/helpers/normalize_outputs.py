from __future__ import annotations

from copy import deepcopy
from typing import Any


def normalize_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(payload)
    options = normalized.get("options")
    if isinstance(options, dict):
        options["version"] = "<version>"
    return {
        "schema_version": normalized.get("schema_version"),
        "input_file": normalized.get("input_file"),
        "total_pages": normalized.get("total_pages"),
        "selected_pages": normalized.get("selected_pages"),
        "options": options,
        "images": normalized.get("images", []),
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
        "page_cache_hits",
        "page_cache_misses",
        "text_line_extract_count",
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
