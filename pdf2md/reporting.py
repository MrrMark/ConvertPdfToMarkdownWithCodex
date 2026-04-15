from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from pdf2md.constants import StructureRecoveryReason
from pdf2md.models import ConversionStatus, PageResult, PageStatus, Report, ReportSummary, WarningEntry


def count_structure_marker_reasons(excluded_assets: Iterable[object]) -> dict[str, int]:
    counts = {
        StructureRecoveryReason.RECOVERED_EXACT: 0,
        StructureRecoveryReason.RECOVERED_CONTEXT_VALIDATED: 0,
        StructureRecoveryReason.SUPPRESSED_NO_CANDIDATE: 0,
        StructureRecoveryReason.SUPPRESSED_AMBIGUOUS: 0,
    }
    for asset in excluded_assets:
        reason = getattr(asset, "reason", None)
        if reason in counts:
            counts[reason] += 1
    return counts


def finalize_page_statuses(page_results: list[PageResult], warnings: list[WarningEntry]) -> tuple[list[PageResult], dict[str, int]]:
    warning_count_by_page: dict[int, int] = {}
    for warning in warnings:
        if warning.page is None:
            continue
        warning_count_by_page[warning.page] = warning_count_by_page.get(warning.page, 0) + 1

    page_status_counts = {
        "success": 0,
        "partial_success": 0,
        "failed": 0,
    }
    for page_result in page_results:
        page_result.warning_count = warning_count_by_page.get(page_result.page, 0)
        if page_result.status is not PageStatus.FAILED and page_result.warning_count > 0:
            page_result.status = PageStatus.PARTIAL_SUCCESS
        page_status_counts[page_result.status.value] += 1
    return page_results, page_status_counts


def determine_conversion_status(warnings: list[WarningEntry], failed_pages: list[int]) -> tuple[ConversionStatus, int]:
    if failed_pages or any(warning.code.endswith("_FAILED") for warning in warnings):
        return ConversionStatus.PARTIAL_SUCCESS, 2
    if any(
        warning.code.startswith("OCR_") or warning.code.startswith("TABLE_") or warning.code.startswith("IMAGE_")
        for warning in warnings
    ):
        return ConversionStatus.PARTIAL_SUCCESS, 2
    return ConversionStatus.SUCCESS, 0


def build_report(
    *,
    started_at: datetime,
    finished_at: datetime,
    status: ConversionStatus,
    warnings: list[WarningEntry],
    page_results: list[PageResult],
    failed_pages: list[int],
    engine_usage: dict[str, bool],
    ocr_confidence_by_page: dict[str, dict[str, float]] | None = None,
    excluded_image_count: int = 0,
    excluded_images: list[dict] | None = None,
    total_deduplicated_blocks: int = 0,
    total_suppressed_lines: int = 0,
    deduplicated_blocks: list[dict] | None = None,
    suppressed_lines: list[dict] | None = None,
    table_quality: list[dict] | None = None,
    table_counts: dict[str, int] | None = None,
    table_fallbacks: list[dict] | None = None,
    table_mode_requested: str | None = None,
    low_confidence_pages: list[int] | None = None,
    page_status_counts: dict[str, int] | None = None,
    structure_marker_counts: dict[str, int] | None = None,
) -> Report:
    ocr_confidence_by_page = ocr_confidence_by_page or {}
    excluded_images = excluded_images or []
    deduplicated_blocks = deduplicated_blocks or []
    suppressed_lines = suppressed_lines or []
    table_quality = table_quality or []
    table_counts = table_counts or {}
    table_fallbacks = table_fallbacks or []
    low_confidence_pages = low_confidence_pages or []
    page_status_counts = page_status_counts or {"success": 0, "partial_success": 0, "failed": 0}
    structure_marker_counts = structure_marker_counts or {}

    summary = ReportSummary(
        processed_pages=len(page_results),
        warning_count=len(warnings),
        failed_page_count=len(set(failed_pages)),
        partial_success=status == ConversionStatus.PARTIAL_SUCCESS,
        ocr_confidence_by_page=ocr_confidence_by_page,
        excluded_image_count=excluded_image_count,
        excluded_images=excluded_images,
        total_deduplicated_blocks=total_deduplicated_blocks,
        total_suppressed_lines=total_suppressed_lines,
        deduplicated_blocks=deduplicated_blocks,
        suppressed_lines=suppressed_lines,
        table_quality=table_quality,
        table_fallback_count=len(table_fallbacks),
        table_fallbacks=table_fallbacks,
        table_mode_requested=table_mode_requested,
        table_total=int(table_counts.get("table_total", 0)),
        table_html_count=int(table_counts.get("table_html_count", 0)),
        table_gfm_count=int(table_counts.get("table_gfm_count", 0)),
        table_recovered_count=int(table_counts.get("table_recovered_count", 0)),
        table_unresolved_count=int(table_counts.get("table_unresolved_count", 0)),
        table_markdown_forced_count=int(table_counts.get("table_markdown_forced_count", 0)),
        table_html_forced_count=int(table_counts.get("table_html_forced_count", 0)),
        low_confidence_pages=low_confidence_pages,
        page_status_counts=page_status_counts,
        structure_marker_suppressed_count=int(
            structure_marker_counts.get(StructureRecoveryReason.SUPPRESSED_NO_CANDIDATE, 0)
            + structure_marker_counts.get(StructureRecoveryReason.SUPPRESSED_AMBIGUOUS, 0)
        ),
        structure_marker_recovered_count=int(
            structure_marker_counts.get(StructureRecoveryReason.RECOVERED_EXACT, 0)
            + structure_marker_counts.get(StructureRecoveryReason.RECOVERED_CONTEXT_VALIDATED, 0)
        ),
        structure_marker_recovered_exact_count=int(
            structure_marker_counts.get(StructureRecoveryReason.RECOVERED_EXACT, 0)
        ),
        structure_marker_recovered_context_count=int(
            structure_marker_counts.get(StructureRecoveryReason.RECOVERED_CONTEXT_VALIDATED, 0)
        ),
        structure_marker_suppressed_no_candidate_count=int(
            structure_marker_counts.get(StructureRecoveryReason.SUPPRESSED_NO_CANDIDATE, 0)
        ),
        structure_marker_suppressed_ambiguous_count=int(
            structure_marker_counts.get(StructureRecoveryReason.SUPPRESSED_AMBIGUOUS, 0)
        ),
    )

    return Report(
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=max(int((finished_at - started_at).total_seconds() * 1000), 0),
        status=status,
        engine_usage=engine_usage,
        failed_pages=sorted(set(failed_pages)),
        warnings=warnings,
        page_results=page_results,
        summary=summary,
    )
