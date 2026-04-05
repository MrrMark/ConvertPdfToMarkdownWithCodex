from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pdf2md.config import Config
from pdf2md.extractors.images import extract_images
from pdf2md.extractors.ocr import run_ocr
from pdf2md.extractors.structure_normalizer import BlockRegion, normalize_page_lines
from pdf2md.extractors.tables import extract_tables
from pdf2md.extractors.text import TextExtractionError, TextLine, extract_page_text_layout
from pdf2md.models import Manifest, PageResult, Report, WarningEntry
from pdf2md.serializers.manifest import serialize_manifest
from pdf2md.serializers.markdown import serialize_markdown
from pdf2md.serializers.report import serialize_report
from pdf2md.utils.io import ensure_output_dirs, write_json, write_text
from pdf2md.utils.pdf import PdfOpenError, open_pdf_reader


EXIT_SUCCESS = 0
EXIT_FATAL = 1
EXIT_PARTIAL = 2


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


def _build_report(
    started_at: datetime,
    finished_at: datetime,
    status: str,
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
) -> Report:
    ocr_confidence_by_page = ocr_confidence_by_page or {}
    excluded_images = excluded_images or []
    deduplicated_blocks = deduplicated_blocks or []
    suppressed_lines = suppressed_lines or []
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
        },
    )


def run_conversion(config: Config) -> ConversionResult:
    """Run conversion and write document.md, manifest.json, report.json."""
    started_at = datetime.now(timezone.utc)
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

    ensure_output_dirs(config.output_dir)

    try:
        reader = open_pdf_reader(config.input_pdf, config.password)
    except PdfOpenError as exc:
        finished_at = datetime.now(timezone.utc)
        warnings.append(WarningEntry(code="PDF_OPEN_FAILED", message=str(exc)))
        report = _build_report(
            started_at=started_at,
            finished_at=finished_at,
            status="failed",
            warnings=warnings,
            page_results=[],
            failed_pages=[],
            engine_usage=engine_usage,
        )
        report_path = config.output_dir / "report.json"
        write_json(report_path, serialize_report(report))
        return ConversionResult(
            exit_code=EXIT_FATAL,
            markdown_path=None,
            manifest_path=None,
            report_path=report_path,
            warnings=warnings,
        )

    total_pages = len(reader.pages)

    try:
        selected_pages = config.selected_pages(total_pages)
    except ValueError as exc:
        finished_at = datetime.now(timezone.utc)
        warnings.append(WarningEntry(code="INVALID_PAGE_RANGE", message=str(exc)))
        report = _build_report(
            started_at=started_at,
            finished_at=finished_at,
            status="failed",
            warnings=warnings,
            page_results=[],
            failed_pages=[],
            engine_usage=engine_usage,
        )
        report_path = config.output_dir / "report.json"
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
        layout = extract_page_text_layout(config.input_pdf, selected_pages, config.password)
        for page in selected_pages:
            lines = layout.get(page, [])
            page_layout_lines[page] = lines
            page_texts[page] = "\n".join(item.text for item in lines).strip()
            page_results_map[page] = PageResult(
                page=page,
                status="success",
                char_count=len(page_texts[page]),
            )
    except TextExtractionError as exc:
        warnings.append(WarningEntry(code="TEXT_EXTRACTION_FAILED", message=str(exc)))
        for page in selected_pages:
            failed_pages.append(page)
            page_layout_lines[page] = []
            page_texts[page] = ""
            page_results_map[page] = PageResult(page=page, status="failed")

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

    table_result = extract_tables(config.input_pdf, selected_pages, config.password, config.table_mode)
    image_result = extract_images(
        reader=reader,
        pdf_path=config.input_pdf,
        selected_pages=selected_pages,
        password=config.password,
        output_dir=config.output_dir,
        image_mode=config.image_mode,
    )
    engine_usage["tables"] = len(table_result.assets) > 0
    engine_usage["images"] = len(image_result.assets) > 0
    warnings.extend(table_result.warnings)
    warnings.extend(image_result.warnings)

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
        normalization = normalize_page_lines(
            page=page,
            lines=page_layout_lines.get(page, []),
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
    markdown_path = config.output_dir / "document.md"
    write_text(markdown_path, markdown)

    manifest = Manifest(
        input_file=config.input_pdf.name,
        total_pages=total_pages,
        selected_pages=selected_pages,
        options={
            "image_mode": config.image_mode,
            "table_mode": config.table_mode,
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
    manifest_path = config.output_dir / "manifest.json"
    write_json(manifest_path, serialize_manifest(manifest))

    status = "success"
    exit_code = EXIT_SUCCESS
    if failed_pages or any(w.code.endswith("_FAILED") for w in warnings):
        status = "partial_success"
        exit_code = EXIT_PARTIAL
    elif any(w.code.startswith("OCR_") or w.code.startswith("TABLE_") or w.code.startswith("IMAGE_") for w in warnings):
        status = "partial_success"
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
    ocr_confidence_by_page = {}
    low_conf_pages: list[int] = []
    for page_result in page_results:
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
    )
    if low_conf_pages:
        report.summary["low_confidence_pages"] = low_conf_pages
    report_path = config.output_dir / "report.json"
    write_json(report_path, serialize_report(report))

    return ConversionResult(
        exit_code=exit_code,
        markdown_path=markdown_path,
        manifest_path=manifest_path,
        report_path=report_path,
        warnings=warnings,
    )
