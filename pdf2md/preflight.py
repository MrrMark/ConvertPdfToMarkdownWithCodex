from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pdf2md.utils.page_range import parse_page_range
from pdf2md.utils.pdf import PdfDocumentContext


DEFAULT_SAMPLE_PAGE_COUNT = 5
LARGE_SPEC_PAGE_THRESHOLD = 200
VERY_LARGE_SPEC_PAGE_THRESHOLD = 600
HIGH_VISUAL_DENSITY_THRESHOLD = 0.75
HIGH_TABLE_DENSITY_THRESHOLD = 1.0


@dataclass(frozen=True)
class PreflightOptions:
    """Options that influence conservative large-spec conversion planning."""

    pages: str | None = None
    password: str | None = None
    sample_page_count: int = DEFAULT_SAMPLE_PAGE_COUNT
    domain_adapter: str | None = None
    prefer_visual: bool = False
    prefer_assetless: bool = False


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _sample_pages(selected_pages: list[int], sample_page_count: int) -> list[int]:
    if not selected_pages:
        return []
    sample_count = max(1, min(sample_page_count, len(selected_pages)))
    if sample_count == len(selected_pages):
        return selected_pages
    if sample_count == 1:
        return [selected_pages[0]]
    last_index = len(selected_pages) - 1
    indexes = sorted({round(index * last_index / (sample_count - 1)) for index in range(sample_count)})
    return [selected_pages[index] for index in indexes]


def _safe_text_line_count(context: PdfDocumentContext, page_number: int) -> int:
    try:
        return len(context.get_text_lines(page_number))
    except Exception:  # noqa: BLE001 - preflight must stay advisory.
        return 0


def _safe_image_count(context: PdfDocumentContext, page_number: int) -> int:
    try:
        return len(context.get_image_boxes(page_number))
    except Exception:  # noqa: BLE001 - preflight must stay advisory.
        return 0


def _safe_table_count(context: PdfDocumentContext, page_number: int) -> int:
    try:
        page = context.get_pdfplumber_page(page_number)
        return len(page.find_tables() or [])
    except Exception:  # noqa: BLE001 - preflight must stay advisory.
        return 0


def _average(values: list[int]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _recommend_window_size(*, selected_page_count: int, visual_density: float, table_density: float) -> int:
    if selected_page_count >= VERY_LARGE_SPEC_PAGE_THRESHOLD:
        return 50 if visual_density >= HIGH_VISUAL_DENSITY_THRESHOLD else 100
    if selected_page_count >= LARGE_SPEC_PAGE_THRESHOLD:
        return 75 if table_density >= HIGH_TABLE_DENSITY_THRESHOLD else 100
    return min(100, max(25, selected_page_count))


def _recommend_image_mode(
    *,
    selected_page_count: int,
    visual_density: float,
    prefer_visual: bool,
    prefer_assetless: bool,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if prefer_assetless:
        return "placeholder", ["assetless_rag_requested"]
    if prefer_visual:
        if selected_page_count >= VERY_LARGE_SPEC_PAGE_THRESHOLD and visual_density >= HIGH_VISUAL_DENSITY_THRESHOLD:
            return "placeholder", ["visual_requested", "large_high_visual_density_asset_guard"]
        return "referenced", ["visual_requested"]
    if selected_page_count >= LARGE_SPEC_PAGE_THRESHOLD:
        reasons.append("large_text_table_domain_ingest")
        if visual_density >= HIGH_VISUAL_DENSITY_THRESHOLD:
            reasons.append("high_visual_density")
        return "none", reasons
    return "referenced", ["default_preserve_visual_evidence"]


def plan_large_spec_conversion(input_pdf: Path, options: PreflightOptions | None = None) -> dict[str, Any]:
    """Return deterministic planning advice for large technical-spec conversion."""
    options = options or PreflightOptions()
    resolved_input = input_pdf.resolve()
    with PdfDocumentContext.open(resolved_input, options.password) as context:
        total_pages = context.total_pages
        selected_pages = parse_page_range(options.pages, total_pages)
        sampled_pages = _sample_pages(selected_pages, options.sample_page_count)
        text_line_counts = [_safe_text_line_count(context, page) for page in sampled_pages]
        image_counts = [_safe_image_count(context, page) for page in sampled_pages]
        table_counts = [_safe_table_count(context, page) for page in sampled_pages]

    selected_page_count = len(selected_pages)
    avg_text_lines = _average(text_line_counts)
    avg_images = _average(image_counts)
    avg_tables = _average(table_counts)
    estimated_text_line_count = round(avg_text_lines * selected_page_count)
    estimated_image_count = round(avg_images * selected_page_count)
    estimated_table_count = round(avg_tables * selected_page_count)
    visual_density = avg_images
    table_density = avg_tables
    recommend_windowed = (
        selected_page_count >= LARGE_SPEC_PAGE_THRESHOLD
        or estimated_image_count >= 100
        or estimated_table_count >= 200
    )
    window_size = _recommend_window_size(
        selected_page_count=selected_page_count,
        visual_density=visual_density,
        table_density=table_density,
    )
    image_mode, image_mode_reasons = _recommend_image_mode(
        selected_page_count=selected_page_count,
        visual_density=visual_density,
        prefer_visual=options.prefer_visual,
        prefer_assetless=options.prefer_assetless,
    )
    rag_profile = "technical_spec_rag_visual" if options.prefer_visual else "technical_spec_rag"
    rag_sidecar_scope = "minimal" if selected_page_count >= 1200 and not options.prefer_visual else "full"
    recommended_options: dict[str, Any] = {
        "rag_profile": rag_profile,
        "image_mode": image_mode,
        "rag_sidecar_scope": rag_sidecar_scope,
        "image_extraction_page_timeout_seconds": 5 if image_mode != "none" else None,
        "image_extraction_stage_timeout_seconds": 180 if selected_page_count >= VERY_LARGE_SPEC_PAGE_THRESHOLD else 120,
        "figure_semantics_stage_timeout_seconds": 90 if options.prefer_visual else 60,
    }
    if options.domain_adapter:
        recommended_options["domain_adapter"] = options.domain_adapter
    if recommend_windowed:
        recommended_options["window_size"] = window_size

    return {
        "schema_version": "1.0",
        "purpose": "large_spec_preflight_plan",
        "input_pdf": str(resolved_input),
        "source_sha256": _file_sha256(resolved_input),
        "total_pages": total_pages,
        "selected_page_count": selected_page_count,
        "sampled_pages": sampled_pages,
        "sample_metrics": {
            "text_line_counts": text_line_counts,
            "image_counts": image_counts,
            "table_counts": table_counts,
            "avg_text_lines_per_page": avg_text_lines,
            "avg_images_per_page": avg_images,
            "avg_tables_per_page": avg_tables,
        },
        "estimates": {
            "estimated_text_line_count": estimated_text_line_count,
            "estimated_image_count": estimated_image_count,
            "estimated_table_count": estimated_table_count,
        },
        "recommendation": {
            "use_page_windowing": recommend_windowed,
            "preferred_mcp_tool": "pdf2md_convert_pdf_windowed" if recommend_windowed else "pdf2md_convert_pdf",
            "window_size": window_size if recommend_windowed else None,
            "recommended_options": recommended_options,
            "reasons": {
                "image_mode": image_mode_reasons,
                "windowing": [
                    reason
                    for reason, enabled in (
                        ("large_selected_page_count", selected_page_count >= LARGE_SPEC_PAGE_THRESHOLD),
                        ("estimated_image_count_high", estimated_image_count >= 100),
                        ("estimated_table_count_high", estimated_table_count >= 200),
                    )
                    if enabled
                ],
            },
        },
    }
