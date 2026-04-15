from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Optional

from pdf2md.config import Config
from pdf2md.extractors.images import extract_images
from pdf2md.extractors.ocr import run_ocr
from pdf2md.extractors.structure_normalizer import BlockRegion, normalize_page_lines
from pdf2md.extractors.tables import extract_tables
from pdf2md.extractors.text import TextExtractionError, TextLine, extract_page_text_layout
from pdf2md.models import ConversionStatus, ImageMode, Manifest, PageResult, PageStatus, Report, TableMode, WarningEntry
from pdf2md.serializers.manifest import serialize_manifest
from pdf2md.serializers.markdown import serialize_markdown
from pdf2md.serializers.report import serialize_report
from pdf2md.utils.io import ensure_output_dirs, write_json, write_text
from pdf2md.utils.pdf import PdfOpenError, open_pdf_reader


EXIT_SUCCESS = 0
EXIT_FATAL = 1
EXIT_PARTIAL = 2
logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    exit_code: int
    markdown_path: Optional[Path]
    manifest_path: Optional[Path]
    report_path: Optional[Path]
    warnings: list[WarningEntry]


def _find_anchor_index(line_tops: list[float], block_top: float) -> int:
    if not line_tops:
        return 0
    for idx, top in enumerate(line_tops):
        if block_top <= top:
            return idx
    return len(line_tops)


def _apply_structure_recoveries(
    *,
    page: int,
    lines: list[TextLine],
    recoveries: list[dict],
) -> list[TextLine]:
    if not recoveries:
        return lines
    updated = [TextLine(text=line.text, top=line.top, bottom=line.bottom, x0=line.x0, x1=line.x1) for line in lines]
    for recovery in recoveries:
        title_text = str(recovery.get("title_text", "")).strip()
        recovered_text = str(recovery.get("recovered_text", "")).strip()
        target_top = float(recovery.get("top", 0.0))
        if not title_text or not recovered_text:
            continue
        best_idx: int | None = None
        best_score: tuple[float, int] | None = None
        for idx, line in enumerate(updated):
            if title_text != line.text.strip():
                continue
            score = (abs(line.top - target_top), idx)
            if best_score is None or score < best_score:
                best_score = score
                best_idx = idx
        if best_idx is None:
            continue
        line = updated[best_idx]
        if line.text.startswith(f"{recovered_text} "):
            continue
        line.text = f"{recovered_text} {line.text}".strip()
    return updated


def _count_excluded_reason(excluded_assets: list, reason: str) -> int:
    return sum(1 for item in excluded_assets if item.reason == reason)


def _build_report(
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
) -> Report:
    ocr_confidence_by_page = ocr_confidence_by_page or {}
    excluded_images = excluded_images or []
    deduplicated_blocks = deduplicated_blocks or []
    suppressed_lines = suppressed_lines or []
    table_quality = table_quality or []
    table_counts = table_counts or {}
    table_fallbacks = table_fallbacks or []
    return Report(
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=max(int((finished_at - started_at).total_seconds() * 1000), 0),
        status=status,
        engine_usage=engine_usage,
        failed_pages=sorted(set(failed_pages)),
        warnings=warnings,
        page_results=page_results,
        summary={
            "processed_pages": len(page_results),
            "warning_count": len(warnings),
            "failed_page_count": len(set(failed_pages)),
            "partial_success": status == "partial_success",
            "ocr_confidence_by_page": ocr_confidence_by_page,
            "excluded_image_count": excluded_image_count,
            "excluded_images": excluded_images,
            "total_deduplicated_blocks": total_deduplicated_blocks,
            "total_suppressed_lines": total_suppressed_lines,
            "deduplicated_blocks": deduplicated_blocks,
            "suppressed_lines": suppressed_lines,
            "table_quality": table_quality,
            "table_fallback_count": len(table_fallbacks),
            "table_fallbacks": table_fallbacks,
            "table_mode_requested": table_mode_requested,
            **table_counts,
        },
    )


def run_conversion(config: Config) -> ConversionResult:
    """Run conversion and write markdown, manifest, and report outputs."""
    started_at = datetime.now(timezone.utc)
    logger.info("Starting conversion input=%s output_dir=%s", config.input_pdf, config.output_dir)
    image_mode = config.image_mode if isinstance(config.image_mode, ImageMode) else ImageMode(config.image_mode)
    table_mode = config.table_mode if isinstance(config.table_mode, TableMode) else TableMode(config.table_mode)
    warnings: list[WarningEntry] = []
    page_results_map: dict[int, PageResult] = {}
    failed_pages: list[int] = []
    engine_usage = {
        "pypdf": True,
        "pdfplumber": True,
        "ocr": False,
        "tables": False,
        "images": False,
    }

    ensure_output_dirs(config.output_dir, config.assets_dirname)

    try:
        reader = open_pdf_reader(config.input_pdf, config.password)
    except PdfOpenError as exc:
        logger.error("Failed to open PDF: %s", exc)
        finished_at = datetime.now(timezone.utc)
        warnings.append(WarningEntry(code="PDF_OPEN_FAILED", message=str(exc)))
        report = _build_report(
            started_at=started_at,
            finished_at=finished_at,
            status=ConversionStatus.FAILED,
            warnings=warnings,
            page_results=[],
            failed_pages=[],
            engine_usage=engine_usage,
        )
        report_path = config.output_dir / config.report_filename
        write_json(report_path, serialize_report(report))
        return ConversionResult(
            exit_code=EXIT_FATAL,
            markdown_path=None,
            manifest_path=None,
            report_path=report_path,
            warnings=warnings,
        )

    total_pages = len(reader.pages)
    logger.info("Opened PDF total_pages=%s", total_pages)

    try:
        selected_pages = config.selected_pages(total_pages)
    except ValueError as exc:
        logger.error("Invalid page range: %s", exc)
        finished_at = datetime.now(timezone.utc)
        warnings.append(WarningEntry(code="INVALID_PAGE_RANGE", message=str(exc)))
        report = _build_report(
            started_at=started_at,
            finished_at=finished_at,
            status=ConversionStatus.FAILED,
            warnings=warnings,
            page_results=[],
            failed_pages=[],
            engine_usage=engine_usage,
        )
        report_path = config.output_dir / config.report_filename
        write_json(report_path, serialize_report(report))
        return ConversionResult(
            exit_code=EXIT_FATAL,
            markdown_path=None,
            manifest_path=None,
            report_path=report_path,
            warnings=warnings,
        )

    page_layout_lines: dict[int, list[TextLine]] = {}
    page_texts: dict[int, str] = {}
    try:
        logger.info("Extracting text for pages=%s", selected_pages)
        layout = extract_page_text_layout(config.input_pdf, selected_pages, config.password)
        for page in selected_pages:
            lines = layout.get(page, [])
            page_layout_lines[page] = lines
            page_texts[page] = "\n".join(item.text for item in lines).strip()
            page_results_map[page] = PageResult(
                page=page,
                status=PageStatus.SUCCESS,
                char_count=len(page_texts[page]),
            )
    except TextExtractionError as exc:
        logger.exception("Text extraction failed")
        warnings.append(WarningEntry(code="TEXT_EXTRACTION_FAILED", message=str(exc)))
        for page in selected_pages:
            failed_pages.append(page)
            page_layout_lines[page] = []
            page_texts[page] = ""
            page_results_map[page] = PageResult(page=page, status=PageStatus.FAILED)

    logger.info("Running OCR target_pages=%s force=%s", selected_pages, config.force_ocr)
    ocr_result = run_ocr(config.input_pdf, selected_pages, page_texts, config.force_ocr)
    warnings.extend(ocr_result.warnings)
    engine_usage["ocr"] = ocr_result.used_ocr
    for page, text in ocr_result.page_texts.items():
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        page_layout_lines[page] = [
            TextLine(
                text=line,
                top=float(idx * 12),
                bottom=float((idx + 1) * 12),
                x0=0.0,
                x1=max(float(len(line) * 6), 1.0),
            )
            for idx, line in enumerate(lines)
        ]
        page_texts[page] = "\n".join(lines)
        if page in page_results_map:
            metrics = ocr_result.metrics_by_page.get(page)
            page_results_map[page].used_ocr = True
            page_results_map[page].char_count = len(page_texts[page])
            if metrics:
                page_results_map[page].ocr_confidence_mean = metrics.mean
                page_results_map[page].ocr_confidence_median = metrics.median
                page_results_map[page].low_conf_token_ratio = metrics.low_conf_token_ratio

    logger.info("Extracting tables")
    table_result = extract_tables(config.input_pdf, selected_pages, config.password, table_mode)
    logger.info("Extracting images mode=%s", image_mode)
    image_result = extract_images(
        reader=reader,
        pdf_path=config.input_pdf,
        selected_pages=selected_pages,
        password=config.password,
        output_dir=config.output_dir,
        image_mode=image_mode,
        assets_dirname=config.assets_dirname,
    )
    engine_usage["tables"] = len(table_result.assets) > 0
    engine_usage["images"] = len(image_result.assets) > 0
    warnings.extend(table_result.warnings)
    warnings.extend(image_result.warnings)
    structure_marker_recovered_exact_count = _count_excluded_reason(
        image_result.excluded_assets,
        "STRUCTURE_MARKER_RECOVERED_EXACT",
    )
    structure_marker_recovered_context_count = _count_excluded_reason(
        image_result.excluded_assets,
        "STRUCTURE_MARKER_RECOVERED_CONTEXT_VALIDATED",
    )
    structure_marker_suppressed_no_candidate_count = _count_excluded_reason(
        image_result.excluded_assets,
        "STRUCTURE_MARKER_SUPPRESSED_NO_CANDIDATE",
    )
    structure_marker_suppressed_ambiguous_count = _count_excluded_reason(
        image_result.excluded_assets,
        "STRUCTURE_MARKER_SUPPRESSED_AMBIGUOUS",
    )
    structure_marker_recovered_count = structure_marker_recovered_exact_count + structure_marker_recovered_context_count
    structure_marker_suppressed_count = (
        structure_marker_suppressed_no_candidate_count + structure_marker_suppressed_ambiguous_count
    )

    block_regions_by_page: dict[int, list[BlockRegion]] = {}
    for page, blocks in table_result.blocks_by_page.items():
        for block in blocks:
            block_regions_by_page.setdefault(page, []).append(
                BlockRegion(
                    block_type="table",
                    block_index=block.index,
                    bbox=block.bbox,
                )
            )
    for page, blocks in image_result.blocks_by_page.items():
        for block in blocks:
            if block.bbox is None:
                continue
            block_regions_by_page.setdefault(page, []).append(
                BlockRegion(
                    block_type="image",
                    block_index=block.index,
                    bbox=block.bbox,
                )
            )

    page_text_lines: dict[int, list[str]] = {}
    page_line_tops: dict[int, list[float]] = {}
    deduplicated_blocks_payload: list[dict] = []
    suppressed_lines_payload: list[dict] = []
    total_deduplicated_blocks = 0
    total_suppressed_lines = 0
    for page in selected_pages:
        logger.debug("Normalizing page=%s", page)
        recovered_lines = _apply_structure_recoveries(
            page=page,
            lines=page_layout_lines.get(page, []),
            recoveries=[item for item in image_result.structure_recoveries if item.get("page") == page],
        )
        normalization = normalize_page_lines(
            page=page,
            lines=recovered_lines,
            block_regions=block_regions_by_page.get(page, []),
        )
        page_text_lines[page] = [line.text for line in normalization.lines]
        page_line_tops[page] = [line.top for line in normalization.lines]
        page_texts[page] = "\n".join(page_text_lines[page]).strip()
        page_result = page_results_map.get(page)
        if page_result is not None:
            page_result.char_count = len(page_texts[page])
            page_result.line_merge_count = normalization.line_merge_count
            page_result.structure_line_count = normalization.structure_line_count
            page_result.dedupe_count = normalization.dedupe_count
            page_result.suppressed_line_count = normalization.suppressed_line_count
        total_deduplicated_blocks += normalization.dedupe_count
        total_suppressed_lines += normalization.suppressed_line_count
        deduplicated_blocks_payload.extend(
            [item.model_dump(mode="json") for item in normalization.deduplicated_blocks]
        )
        suppressed_lines_payload.extend([item.model_dump(mode="json") for item in normalization.suppressed_lines])

    page_blocks_with_anchor: dict[int, list[tuple[int, float, str]]] = {}
    for page, blocks in table_result.blocks_by_page.items():
        line_tops = page_line_tops.get(page, [])
        for block in blocks:
            anchor_index = _find_anchor_index(line_tops, block.top)
            page_blocks_with_anchor.setdefault(page, []).append((anchor_index, block.top, block.markdown))
            for asset in table_result.assets:
                if asset.page == block.page and asset.index == block.index:
                    asset.anchor_line_index = anchor_index
                    asset.anchor_top = block.top
                    break

    for page, blocks in image_result.blocks_by_page.items():
        line_tops = page_line_tops.get(page, [])
        for block in blocks:
            anchor_index = _find_anchor_index(line_tops, block.top)
            block.anchor_line_index = anchor_index
            page_blocks_with_anchor.setdefault(page, []).append((anchor_index, block.top, block.markdown))
            for asset in image_result.assets:
                if asset.page == block.page and asset.index == block.index:
                    asset.anchor_line_index = anchor_index
                    asset.anchor_top = block.top
                    break

    ordered_page_blocks: dict[int, list[tuple[int, str]]] = {}
    for page, entries in page_blocks_with_anchor.items():
        entries.sort(key=lambda item: (item[0], item[1]))
        ordered_page_blocks[page] = [(anchor_idx, markdown) for anchor_idx, _, markdown in entries]

    markdown = serialize_markdown(
        page_text_lines=page_text_lines,
        keep_page_markers=config.keep_page_markers,
        page_blocks_by_page=ordered_page_blocks,
    )
    markdown_path = config.output_dir / config.markdown_filename
    logger.info("Writing markdown path=%s", markdown_path)
    write_text(markdown_path, markdown)

    manifest = Manifest(
        input_file=config.input_pdf.name,
        total_pages=total_pages,
        selected_pages=selected_pages,
        options={
            "image_mode": image_mode,
            "table_mode": table_mode.manifest_value(),
            "force_ocr": config.force_ocr,
            "keep_page_markers": config.keep_page_markers,
            "pages": config.pages,
            "version": config.version,
        },
        images=image_result.assets,
        excluded_images=image_result.excluded_assets,
        tables=table_result.assets,
        ocr_pages=sorted(ocr_result.ocr_pages),
        warnings=warnings,
    )
    manifest_path = config.output_dir / config.manifest_filename
    logger.info("Writing manifest path=%s", manifest_path)
    write_json(manifest_path, serialize_manifest(manifest))

    status = ConversionStatus.SUCCESS
    exit_code = EXIT_SUCCESS
    if failed_pages or any(w.code.endswith("_FAILED") for w in warnings):
        status = ConversionStatus.PARTIAL_SUCCESS
        exit_code = EXIT_PARTIAL
    elif any(w.code.startswith("OCR_") or w.code.startswith("TABLE_") or w.code.startswith("IMAGE_") for w in warnings):
        status = ConversionStatus.PARTIAL_SUCCESS
        exit_code = EXIT_PARTIAL

    finished_at = datetime.now(timezone.utc)
    page_results = [page_results_map[page] for page in sorted(page_results_map)]
    warning_count_by_page: dict[int, int] = {}
    for warning in warnings:
        if warning.page is None:
            continue
        warning_count_by_page[warning.page] = warning_count_by_page.get(warning.page, 0) + 1
    for page_result in page_results:
        page_result.warning_count = warning_count_by_page.get(page_result.page, 0)
        if page_result.status is PageStatus.FAILED:
            continue
        if page_result.warning_count > 0:
            page_result.status = PageStatus.PARTIAL_SUCCESS
    ocr_confidence_by_page = {}
    low_conf_pages: list[int] = []
    page_status_counts = {
        "success": 0,
        "partial_success": 0,
        "failed": 0,
    }
    for page_result in page_results:
        page_status_counts[page_result.status.value] += 1
        if page_result.ocr_confidence_mean is None:
            continue
        ocr_confidence_by_page[str(page_result.page)] = {
            "ocr_confidence_mean": float(page_result.ocr_confidence_mean),
            "ocr_confidence_median": float(page_result.ocr_confidence_median or 0.0),
            "low_conf_token_ratio": float(page_result.low_conf_token_ratio or 0.0),
        }
        if (page_result.low_conf_token_ratio or 0.0) > 0.25:
            low_conf_pages.append(page_result.page)

    report = _build_report(
        started_at=started_at,
        finished_at=finished_at,
        status=status,
        warnings=warnings,
        page_results=page_results,
        failed_pages=failed_pages,
        engine_usage=engine_usage,
        ocr_confidence_by_page=ocr_confidence_by_page,
        excluded_image_count=len(image_result.excluded_assets),
        excluded_images=[item.model_dump(mode="json") for item in image_result.excluded_assets],
        total_deduplicated_blocks=total_deduplicated_blocks,
        total_suppressed_lines=total_suppressed_lines,
        deduplicated_blocks=deduplicated_blocks_payload,
        suppressed_lines=suppressed_lines_payload,
        table_quality=table_result.table_quality,
        table_counts=table_result.table_counts,
        table_fallbacks=table_result.fallbacks,
        table_mode_requested=table_mode.requested_mode(),
    )
    if low_conf_pages:
        report.summary["low_confidence_pages"] = low_conf_pages
    report.summary["page_status_counts"] = page_status_counts
    report.summary["structure_marker_suppressed_count"] = structure_marker_suppressed_count
    report.summary["structure_marker_recovered_count"] = structure_marker_recovered_count
    report.summary["structure_marker_recovered_exact_count"] = structure_marker_recovered_exact_count
    report.summary["structure_marker_recovered_context_count"] = structure_marker_recovered_context_count
    report.summary["structure_marker_suppressed_no_candidate_count"] = structure_marker_suppressed_no_candidate_count
    report.summary["structure_marker_suppressed_ambiguous_count"] = structure_marker_suppressed_ambiguous_count
    report_path = config.output_dir / config.report_filename
    logger.info("Writing report path=%s status=%s exit_code=%s", report_path, status.value, exit_code)
    write_json(report_path, serialize_report(report))

    return ConversionResult(
        exit_code=exit_code,
        markdown_path=markdown_path,
        manifest_path=manifest_path,
        report_path=report_path,
        warnings=warnings,
    )
