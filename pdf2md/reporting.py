from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from pdf2md.constants import StructureRecoveryReason, WarningCode, WarningDomain, WarningSeverity, warning_code_spec
from pdf2md.models import ConversionStatus, PageResult, PageStatus, Report, ReportSummary, WarningEntry

ADVISORY_EMPTY_OCR_REASONS = frozenset({"empty_text_layer", "low_text_density"})
EXIT_CODE_WARNING_DOMAINS = frozenset({WarningDomain.OCR, WarningDomain.TABLE, WarningDomain.IMAGE})


def _optional_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


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


def is_advisory_warning(warning: WarningEntry) -> bool:
    spec = warning_code_spec(warning.code)
    if spec.default_severity == WarningSeverity.ADVISORY:
        return True
    if warning.code == WarningCode.OCR_EMPTY_RESULT:
        details = warning.details
        if details.get("force_ocr") is True:
            return False
        attempt_reason = str(details.get("attempt_reason") or "")
        if attempt_reason not in ADVISORY_EMPTY_OCR_REASONS:
            return False
        existing_chars = _optional_int(
            details.get("existing_text_char_count", details.get("text_layer_char_count"))
        )
        image_count = _optional_int(details.get("page_image_count"))
        if attempt_reason == "low_text_density":
            return existing_chars is not None and existing_chars < 3
        return existing_chars == 0 and image_count == 0
    return False


def is_actionable_warning(warning: WarningEntry) -> bool:
    return not is_advisory_warning(warning)


def warning_affects_exit_code(warning: WarningEntry) -> bool:
    """Return whether this warning should turn a successful conversion into partial success."""
    if is_advisory_warning(warning):
        return False
    if warning.code.endswith("_FAILED"):
        return True
    spec = warning_code_spec(warning.code)
    return spec.affects_exit_code and spec.domain in EXIT_CODE_WARNING_DOMAINS


def count_actionable_warnings(warnings: Iterable[WarningEntry]) -> int:
    return sum(1 for warning in warnings if is_actionable_warning(warning))


def count_advisory_warnings(warnings: Iterable[WarningEntry]) -> int:
    return sum(1 for warning in warnings if is_advisory_warning(warning))


def count_ocr_actionable_warnings(warnings: Iterable[WarningEntry]) -> int:
    return sum(
        1
        for warning in warnings
        if warning_code_spec(warning.code).domain == WarningDomain.OCR and is_actionable_warning(warning)
    )


def count_ocr_advisory_warnings(warnings: Iterable[WarningEntry]) -> int:
    return sum(
        1
        for warning in warnings
        if warning_code_spec(warning.code).domain == WarningDomain.OCR and is_advisory_warning(warning)
    )


def count_expected_table_fallback_warnings(warnings: Iterable[WarningEntry]) -> tuple[int, dict[str, int]]:
    reason_counts: dict[str, int] = {}
    count = 0
    for warning in warnings:
        if warning.code != WarningCode.TABLE_COMPLEXITY_HTML_FALLBACK:
            continue
        count += 1
        for reason in warning.details.get("reasons", []):
            reason_counts[str(reason)] = reason_counts.get(str(reason), 0) + 1
    return count, dict(sorted(reason_counts.items()))


def finalize_page_statuses(
    page_results: list[PageResult],
    warnings: list[WarningEntry],
    actionable_pages: Iterable[int] | None = None,
) -> tuple[list[PageResult], dict[str, int]]:
    warning_count_by_page: dict[int, int] = {}
    actionable_warning_count_by_page: dict[int, int] = {}
    for warning in warnings:
        if warning.page is None:
            continue
        warning_count_by_page[warning.page] = warning_count_by_page.get(warning.page, 0) + 1
        if is_actionable_warning(warning):
            actionable_warning_count_by_page[warning.page] = actionable_warning_count_by_page.get(warning.page, 0) + 1
    actionable_page_set = set(actionable_pages or [])

    page_status_counts = {
        "success": 0,
        "partial_success": 0,
        "failed": 0,
    }
    for page_result in page_results:
        page_result.warning_count = warning_count_by_page.get(page_result.page, 0)
        if (
            page_result.status is not PageStatus.FAILED
            and (
                actionable_warning_count_by_page.get(page_result.page, 0) > 0
                or page_result.page in actionable_page_set
            )
        ):
            page_result.status = PageStatus.PARTIAL_SUCCESS
        page_status_counts[page_result.status.value] += 1
    return page_results, page_status_counts


def determine_conversion_status(
    warnings: list[WarningEntry],
    failed_pages: list[int],
    *,
    table_actionable_low_quality_count: int = 0,
) -> tuple[ConversionStatus, int]:
    if failed_pages or any(warning.code.endswith("_FAILED") for warning in warnings):
        return ConversionStatus.PARTIAL_SUCCESS, 2
    if table_actionable_low_quality_count > 0:
        return ConversionStatus.PARTIAL_SUCCESS, 2
    if any(warning_affects_exit_code(warning) for warning in warnings):
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
    stage_durations_ms: dict[str, int] | None = None,
    pdf_open_count: int = 0,
    pages_per_second: float | None = None,
    page_worker_count: int = 1,
    page_parallel_enabled: bool = False,
    page_worker_effective_count: int = 1,
    rag_table_output: str = "none",
    rag_table_record_count: int = 0,
    rag_table_file_count: int = 0,
    table_fallback_reason_counts: dict[str, int] | None = None,
    table_low_quality_count: int = 0,
    table_actionable_low_quality_count: int = 0,
    table_advisory_low_quality_count: int = 0,
    table_caption_linked_count: int = 0,
    page_cache_hits: int = 0,
    page_cache_misses: int = 0,
    text_line_extract_count: int = 0,
    heading_count: int = 0,
    list_item_count: int = 0,
    code_block_count: int = 0,
    hyphenation_repair_count: int = 0,
    font_heading_candidate_count: int = 0,
    footnote_candidate_count: int = 0,
    structure_low_confidence_count: int = 0,
    rag_text_block_record_count: int = 0,
    rag_text_block_file_count: int = 0,
    semantic_unit_record_count: int = 0,
    semantic_unit_file_count: int = 0,
    requirement_record_count: int = 0,
    requirement_file_count: int = 0,
    cross_ref_record_count: int = 0,
    cross_ref_file_count: int = 0,
    semantic_low_confidence_count: int = 0,
    unresolved_cross_ref_count: int = 0,
    normative_requirement_count: int = 0,
    retrieval_chunk_record_count: int = 0,
    retrieval_chunk_file_count: int = 0,
    retrieval_chunk_max_token_estimate: int = 0,
    retrieval_chunk_average_token_estimate: float = 0.0,
    retrieval_chunk_over_target_count: int = 0,
    retrieval_chunk_duplicate_source_ref_count: int = 0,
    figure_rag_record_count: int = 0,
    figure_rag_file_count: int = 0,
    domain_unit_record_count: int = 0,
    domain_unit_file_count: int = 0,
    requirement_traceability_record_count: int = 0,
    requirement_traceability_file_count: int = 0,
    technical_table_record_count: int = 0,
    technical_table_file_count: int = 0,
    confidential_safe_mode: bool = False,
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
    stage_durations_ms = stage_durations_ms or {}
    table_fallback_reason_counts = table_fallback_reason_counts or {}
    expected_table_fallback_count, expected_table_fallback_reason_counts = count_expected_table_fallback_warnings(warnings)

    summary = ReportSummary(
        processed_pages=len(page_results),
        warning_count=len(warnings),
        actionable_warning_count=count_actionable_warnings(warnings),
        advisory_warning_count=count_advisory_warnings(warnings),
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
        stage_durations_ms=stage_durations_ms,
        pdf_open_count=pdf_open_count,
        pages_per_second=pages_per_second,
        page_worker_count=page_worker_count,
        page_parallel_enabled=page_parallel_enabled,
        page_worker_effective_count=page_worker_effective_count,
        rag_table_output=rag_table_output,
        rag_table_record_count=rag_table_record_count,
        rag_table_file_count=rag_table_file_count,
        table_fallback_reason_counts=table_fallback_reason_counts,
        table_expected_fallback_count=expected_table_fallback_count,
        table_expected_fallback_reason_counts=expected_table_fallback_reason_counts,
        table_actionable_fallback_count=max(len(table_fallbacks) - expected_table_fallback_count, 0),
        table_low_quality_count=table_low_quality_count,
        table_actionable_low_quality_count=table_actionable_low_quality_count,
        table_advisory_low_quality_count=table_advisory_low_quality_count,
        ocr_actionable_warning_count=count_ocr_actionable_warnings(warnings),
        ocr_advisory_warning_count=count_ocr_advisory_warnings(warnings),
        technical_profile_domain_adapter_missing=any(
            warning.code == WarningCode.TECHNICAL_PROFILE_DOMAIN_ADAPTER_MISSING for warning in warnings
        ),
        table_caption_linked_count=table_caption_linked_count,
        page_cache_hits=page_cache_hits,
        page_cache_misses=page_cache_misses,
        text_line_extract_count=text_line_extract_count,
        heading_count=heading_count,
        list_item_count=list_item_count,
        code_block_count=code_block_count,
        hyphenation_repair_count=hyphenation_repair_count,
        font_heading_candidate_count=font_heading_candidate_count,
        footnote_candidate_count=footnote_candidate_count,
        structure_low_confidence_count=structure_low_confidence_count,
        rag_text_block_record_count=rag_text_block_record_count,
        rag_text_block_file_count=rag_text_block_file_count,
        semantic_unit_record_count=semantic_unit_record_count,
        semantic_unit_file_count=semantic_unit_file_count,
        requirement_record_count=requirement_record_count,
        requirement_file_count=requirement_file_count,
        cross_ref_record_count=cross_ref_record_count,
        cross_ref_file_count=cross_ref_file_count,
        semantic_low_confidence_count=semantic_low_confidence_count,
        unresolved_cross_ref_count=unresolved_cross_ref_count,
        normative_requirement_count=normative_requirement_count,
        retrieval_chunk_record_count=retrieval_chunk_record_count,
        retrieval_chunk_file_count=retrieval_chunk_file_count,
        retrieval_chunk_max_token_estimate=retrieval_chunk_max_token_estimate,
        retrieval_chunk_average_token_estimate=retrieval_chunk_average_token_estimate,
        retrieval_chunk_over_target_count=retrieval_chunk_over_target_count,
        retrieval_chunk_duplicate_source_ref_count=retrieval_chunk_duplicate_source_ref_count,
        figure_rag_record_count=figure_rag_record_count,
        figure_rag_file_count=figure_rag_file_count,
        domain_unit_record_count=domain_unit_record_count,
        domain_unit_file_count=domain_unit_file_count,
        requirement_traceability_record_count=requirement_traceability_record_count,
        requirement_traceability_file_count=requirement_traceability_file_count,
        technical_table_record_count=technical_table_record_count,
        technical_table_file_count=technical_table_file_count,
        confidential_safe_mode=confidential_safe_mode,
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
