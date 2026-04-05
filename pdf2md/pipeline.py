from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pdf2md.config import Config
from pdf2md.extractors.images import extract_images
from pdf2md.extractors.ocr import run_ocr
from pdf2md.extractors.tables import extract_tables
from pdf2md.extractors.text import TextExtractionError, extract_page_texts
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


def _build_report(
    started_at: datetime,
    finished_at: datetime,
    status: str,
    warnings: list[WarningEntry],
    page_results: list[PageResult],
    failed_pages: list[int],
    engine_usage: dict[str, bool],
) -> Report:
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

    page_texts: dict[int, str] = {}
    try:
        page_texts = extract_page_texts(config.input_pdf, selected_pages, config.password)
    except TextExtractionError as exc:
        warnings.append(WarningEntry(code="TEXT_EXTRACTION_FAILED", message=str(exc)))
        for page in selected_pages:
            failed_pages.append(page)
            page_texts[page] = ""
            page_results_map[page] = PageResult(page=page, status="failed")

    for page in selected_pages:
        text = page_texts.get(page, "")
        if page in page_results_map and page_results_map[page].status == "failed":
            continue
        page_results_map[page] = PageResult(
            page=page,
            status="success",
            char_count=len(text),
        )

    ocr_result = run_ocr(config.input_pdf, selected_pages, page_texts, config.force_ocr)
    warnings.extend(ocr_result.warnings)
    engine_usage["ocr"] = ocr_result.used_ocr
    for page, text in ocr_result.page_texts.items():
        page_texts[page] = text
        if page in page_results_map:
            page_results_map[page].used_ocr = True
            page_results_map[page].char_count = len(text)

    table_result = extract_tables(config.input_pdf, selected_pages, config.password, config.table_mode)
    image_result = extract_images(reader, selected_pages, config.output_dir, config.image_mode)
    engine_usage["tables"] = len(table_result.assets) > 0
    engine_usage["images"] = len(image_result.assets) > 0
    warnings.extend(table_result.warnings)
    warnings.extend(image_result.warnings)

    table_blocks_by_page = {
        page: [block.markdown for block in blocks]
        for page, blocks in table_result.blocks_by_page.items()
    }
    image_blocks_by_page = {
        page: [block.markdown for block in blocks]
        for page, blocks in image_result.blocks_by_page.items()
    }

    markdown = serialize_markdown(
        page_texts,
        keep_page_markers=config.keep_page_markers,
        table_blocks_by_page=table_blocks_by_page,
        image_blocks_by_page=image_blocks_by_page,
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
    report = _build_report(
        started_at=started_at,
        finished_at=finished_at,
        status=status,
        warnings=warnings,
        page_results=page_results,
        failed_pages=failed_pages,
        engine_usage=engine_usage,
    )
    report_path = config.output_dir / "report.json"
    write_json(report_path, serialize_report(report))

    return ConversionResult(
        exit_code=exit_code,
        markdown_path=markdown_path,
        manifest_path=manifest_path,
        report_path=report_path,
        warnings=warnings,
    )
