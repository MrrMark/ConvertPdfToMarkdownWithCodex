from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Optional

from pdf2md.config import Config
from pdf2md.constants import WarningCode
from pdf2md.extractors.header_footer import remove_repeated_header_footer
from pdf2md.extractors.images import extract_images
from pdf2md.extractors.ocr import run_ocr
from pdf2md.extractors.structure_normalizer import BlockRegion, normalize_page_lines
from pdf2md.extractors.tables import extract_tables
from pdf2md.extractors.text import PageLayoutMetadata, TextExtractionError, TextLine, extract_page_text_layout_result
from pdf2md.models import (
    ConversionStatus,
    DomainAdapterMode,
    ImageMode,
    Manifest,
    NormalizedLine,
    PageResult,
    PageStatus,
    RagTableOutputMode,
    Report,
    TableMode,
    WarningEntry,
)
from pdf2md.reporting import build_report, count_structure_marker_reasons, determine_conversion_status, finalize_page_statuses
from pdf2md.serializers.manifest import serialize_manifest
from pdf2md.serializers.markdown import serialize_markdown_blocks_result
from pdf2md.serializers.rag_chunks import build_retrieval_chunks, serialize_retrieval_chunks_jsonl
from pdf2md.serializers.rag_domain_adapters import build_domain_units, serialize_domain_units_jsonl
from pdf2md.serializers.rag_figures import build_figure_records, serialize_figures_jsonl
from pdf2md.serializers.rag_tables import (
    flatten_rag_table_records,
    normalize_rag_table_payload,
    serialize_rag_tables_jsonl,
    serialize_rag_tables_markdown,
)
from pdf2md.serializers.rag_semantics import (
    build_semantic_layer,
    serialize_cross_refs_jsonl,
    serialize_requirements_jsonl,
    serialize_semantic_units_jsonl,
)
from pdf2md.serializers.rag_text_blocks import build_text_blocks, serialize_text_blocks_jsonl
from pdf2md.serializers.report import serialize_report
from pdf2md.utils.io import ensure_output_dirs, write_json, write_text
from pdf2md.utils.pdf import PdfDocumentContext, PdfOpenError


EXIT_SUCCESS = 0
EXIT_FATAL = 1
EXIT_PARTIAL = 2
LOW_TABLE_QUALITY_THRESHOLD = 0.55
logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    exit_code: int
    markdown_path: Optional[Path]
    manifest_path: Optional[Path]
    report_path: Optional[Path]
    warnings: list[WarningEntry]
    status: ConversionStatus
    report: Report | None = None


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
    updated = [
        TextLine(
            text=line.text,
            top=line.top,
            bottom=line.bottom,
            x0=line.x0,
            x1=line.x1,
            font_size=line.font_size,
            font_family=line.font_family,
            font_style_hint=line.font_style_hint,
            line_height=line.line_height,
            left_indent=line.left_indent,
            right_indent=line.right_indent,
            y_band=line.y_band,
        )
        for line in lines
    ]
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


def _write_debug_artifacts(
    *,
    config: Config,
    selected_pages: list[int],
    raw_lines_by_page: dict[int, list[dict]],
    ordered_lines_by_page: dict[int, list[TextLine]],
    normalized_lines_by_page: dict[int, list[dict]],
    text_metadata_by_page: dict[int, PageLayoutMetadata],
    table_candidates_by_page: dict[int, list[dict]],
    image_candidates_by_page: dict[int, list[dict]],
) -> None:
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


def _count_table_fallback_reasons(table_fallbacks: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for fallback in table_fallbacks:
        for reason in fallback.get("reasons", []):
            counts[str(reason)] = counts.get(str(reason), 0) + 1
    return dict(sorted(counts.items()))


def _count_low_quality_tables(table_quality: list[dict]) -> int:
    count = 0
    for item in table_quality:
        try:
            score = float(item.get("quality_score", 1.0))
        except (TypeError, ValueError):
            continue
        if score < LOW_TABLE_QUALITY_THRESHOLD:
            count += 1
    return count


def _count_caption_linked_tables(table_quality: list[dict]) -> int:
    return sum(1 for item in table_quality if str(item.get("caption_text") or "").strip())


def _write_rag_table_outputs(
    *,
    config: Config,
    output_mode: RagTableOutputMode,
    rag_tables: list[dict],
) -> tuple[int, int]:
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


def _repair_hyphenated_normalized_lines(lines: list[NormalizedLine]) -> tuple[list[NormalizedLine], int]:
    repaired: list[NormalizedLine] = []
    repair_count = 0
    idx = 0
    while idx < len(lines):
        current = lines[idx].model_copy(deep=True)
        if idx + 1 < len(lines):
            next_line = lines[idx + 1]
            current_text = current.text.rstrip()
            next_text = next_line.text.lstrip()
            if (
                current.line_type.value == "BODY_LINE"
                and next_line.line_type.value == "BODY_LINE"
                and len(current_text) >= 2
                and current_text.endswith("-")
                and current_text[-2].isalpha()
                and next_text
                and next_text[0].islower()
            ):
                current.text = f"{current_text[:-1]}{next_text}"
                current.bottom = max(current.bottom, next_line.bottom)
                current.x1 = max(current.x1, next_line.x1)
                current.source_line_indices.extend(next_line.source_line_indices or [next_line.index])
                repaired.append(current)
                repair_count += 1
                idx += 2
                continue
        repaired.append(current)
        idx += 1
    return repaired, repair_count


def _write_rag_text_block_output(config: Config, records: list[dict]) -> tuple[int, int]:
    write_text(config.output_dir / config.rag_text_blocks_jsonl_filename, serialize_text_blocks_jsonl(records))
    return len(records), 1


def _write_semantic_layer_outputs(
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


def _write_retrieval_chunk_output(config: Config, records: list[dict]) -> tuple[int, int]:
    write_text(config.output_dir / config.retrieval_chunks_jsonl_filename, serialize_retrieval_chunks_jsonl(records))
    return len(records), 1


def _write_figure_rag_output(config: Config, records: list[dict]) -> tuple[int, int]:
    write_text(config.output_dir / config.figures_rag_jsonl_filename, serialize_figures_jsonl(records))
    return len(records), 1


def _write_domain_unit_output(config: Config, records: list[dict]) -> tuple[int, int]:
    write_text(config.output_dir / config.domain_units_jsonl_filename, serialize_domain_units_jsonl(records))
    return len(records), 1


def run_conversion(config: Config) -> ConversionResult:
    """Run conversion and write markdown, manifest, and report outputs."""
    started_at = datetime.now(timezone.utc)
    logger.info("Starting conversion input=%s output_dir=%s", config.input_pdf, config.output_dir)
    image_mode = config.image_mode if isinstance(config.image_mode, ImageMode) else ImageMode(config.image_mode)
    table_mode = config.table_mode if isinstance(config.table_mode, TableMode) else TableMode(config.table_mode)
    rag_table_output = (
        config.rag_table_output
        if isinstance(config.rag_table_output, RagTableOutputMode)
        else RagTableOutputMode(config.rag_table_output)
    )
    domain_adapter = (
        config.domain_adapter
        if isinstance(config.domain_adapter, DomainAdapterMode)
        else DomainAdapterMode(config.domain_adapter)
    )
    stage_durations_ms: dict[str, int] = {}

    def stage_start() -> datetime:
        return datetime.now(timezone.utc)

    def finish_stage(name: str, started: datetime) -> None:
        elapsed_ms = max(int((datetime.now(timezone.utc) - started).total_seconds() * 1000), 0)
        stage_durations_ms[name] = stage_durations_ms.get(name, 0) + elapsed_ms

    warnings: list[WarningEntry] = []
    page_results_map: dict[int, PageResult] = {}
    failed_pages: list[int] = []
    heading_count = 0
    list_item_count = 0
    code_block_count = 0
    hyphenation_repair_count = 0
    font_heading_candidate_count = 0
    footnote_candidate_count = 0
    structure_low_confidence_count = 0
    rag_text_block_record_count = 0
    rag_text_block_file_count = 0
    semantic_unit_record_count = 0
    semantic_unit_file_count = 0
    requirement_record_count = 0
    requirement_file_count = 0
    cross_ref_record_count = 0
    cross_ref_file_count = 0
    semantic_low_confidence_count = 0
    unresolved_cross_ref_count = 0
    normative_requirement_count = 0
    retrieval_chunk_record_count = 0
    retrieval_chunk_file_count = 0
    figure_rag_record_count = 0
    figure_rag_file_count = 0
    domain_unit_record_count = 0
    domain_unit_file_count = 0
    engine_usage = {
        "pypdf": True,
        "pdfplumber": True,
        "ocr": False,
        "tables": False,
        "images": False,
    }

    output_setup_started = stage_start()
    ensure_output_dirs(config.output_dir, config.assets_dirname)
    finish_stage("output_setup", output_setup_started)

    pdf_open_started = stage_start()
    try:
        pdf_context = PdfDocumentContext.open(config.input_pdf, config.password)
    except PdfOpenError as exc:
        finish_stage("pdf_open", pdf_open_started)
        logger.error("Failed to open PDF: %s", exc)
        finished_at = datetime.now(timezone.utc)
        warnings.append(WarningEntry(code=WarningCode.PDF_OPEN_FAILED, message=str(exc)))
        report = build_report(
            started_at=started_at,
            finished_at=finished_at,
            status=ConversionStatus.FAILED,
            warnings=warnings,
            page_results=[],
            failed_pages=[],
            engine_usage=engine_usage,
            stage_durations_ms=stage_durations_ms,
        )
        report_path = config.output_dir / config.report_filename
        write_json(report_path, serialize_report(report))
        return ConversionResult(
            exit_code=EXIT_FATAL,
            markdown_path=None,
            manifest_path=None,
            report_path=report_path,
            warnings=warnings,
            status=ConversionStatus.FAILED,
            report=report,
        )
    finish_stage("pdf_open", pdf_open_started)

    reader = pdf_context.reader
    total_pages = pdf_context.total_pages
    logger.info("Opened PDF total_pages=%s", total_pages)

    page_selection_started = stage_start()
    try:
        selected_pages = config.selected_pages(total_pages)
    except ValueError as exc:
        finish_stage("page_selection", page_selection_started)
        pdf_context.close()
        logger.error("Invalid page range: %s", exc)
        finished_at = datetime.now(timezone.utc)
        warnings.append(WarningEntry(code=WarningCode.INVALID_PAGE_RANGE, message=str(exc)))
        report = build_report(
            started_at=started_at,
            finished_at=finished_at,
            status=ConversionStatus.FAILED,
            warnings=warnings,
            page_results=[],
            failed_pages=[],
            engine_usage=engine_usage,
            stage_durations_ms=stage_durations_ms,
            pdf_open_count=pdf_context.pdf_open_count,
        )
        report_path = config.output_dir / config.report_filename
        write_json(report_path, serialize_report(report))
        return ConversionResult(
            exit_code=EXIT_FATAL,
            markdown_path=None,
            manifest_path=None,
            report_path=report_path,
            warnings=warnings,
            status=ConversionStatus.FAILED,
            report=report,
        )
    finish_stage("page_selection", page_selection_started)

    page_layout_lines: dict[int, list[TextLine]] = {}
    page_texts: dict[int, str] = {}
    raw_lines_by_page: dict[int, list[dict]] = {}
    text_metadata_by_page: dict[int, PageLayoutMetadata] = {}
    shared_plumber_pdf = None
    text_started = stage_start()
    try:
        logger.info("Extracting text for pages=%s", selected_pages)
        shared_plumber_pdf = pdf_context.get_pdfplumber_pdf()
        cached_text_lines_by_page = {page: pdf_context.get_text_lines(page) for page in selected_pages}
        text_layout = extract_page_text_layout_result(
            config.input_pdf,
            selected_pages,
            config.password,
            pdf=shared_plumber_pdf,
            text_lines_by_page=cached_text_lines_by_page,
        )
        layout = text_layout.lines_by_page
        raw_lines_by_page = text_layout.raw_lines_by_page
        text_metadata_by_page = text_layout.metadata_by_page
        for page in selected_pages:
            lines = layout.get(page, [])
            page_layout_lines[page] = lines
            page_texts[page] = "\n".join(item.text for item in lines).strip()
            metadata = text_metadata_by_page.get(page)
            page_results_map[page] = PageResult(
                page=page,
                status=PageStatus.SUCCESS,
                char_count=len(page_texts[page]),
                text_layer_char_count=len(page_texts[page]),
                reading_order_strategy=metadata.reading_order_strategy if metadata else "top",
                column_count_estimate=metadata.column_count_estimate if metadata else 1,
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Text extraction failed")
        warnings.append(WarningEntry(code=WarningCode.TEXT_EXTRACTION_FAILED, message=str(exc)))
        for page in selected_pages:
            failed_pages.append(page)
            page_layout_lines[page] = []
            page_texts[page] = ""
            page_results_map[page] = PageResult(page=page, status=PageStatus.FAILED, text_layer_char_count=0)
    finally:
        finish_stage("text_extraction", text_started)

    ocr_started = stage_start()
    logger.info("Running OCR target_pages=%s force=%s", selected_pages, config.force_ocr)
    ocr_result = run_ocr(config.input_pdf, selected_pages, page_texts, config.force_ocr, ocr_lang=config.ocr_lang)
    finish_stage("ocr", ocr_started)
    warnings.extend(ocr_result.warnings)
    engine_usage["ocr"] = ocr_result.used_ocr
    for page in ocr_result.attempted_pages:
        if page in page_results_map:
            page_results_map[page].ocr_attempted = True
            page_results_map[page].ocr_reason = ocr_result.reasons_by_page.get(page)
            page_results_map[page].ocr_runtime_available = ocr_result.runtime_available
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
            page_results_map[page].reading_order_strategy = "ocr_line_order"
            page_results_map[page].column_count_estimate = 1
            if metrics:
                page_results_map[page].ocr_confidence_mean = metrics.mean
                page_results_map[page].ocr_confidence_median = metrics.median
                page_results_map[page].low_conf_token_ratio = metrics.low_conf_token_ratio

    page_heights = {page: metadata.page_height for page, metadata in text_metadata_by_page.items()}
    header_footer_suppressed_payload: list[dict] = []
    header_footer_suppressed_by_page: dict[int, int] = {}
    if config.remove_header_footer:
        header_footer_started = stage_start()
        logger.info("Removing repeated headers/footers")
        header_footer_result = remove_repeated_header_footer(page_layout_lines, page_heights)
        page_layout_lines = header_footer_result.lines_by_page
        header_footer_suppressed_payload = [
            item.model_dump(mode="json") for item in header_footer_result.suppressed_lines
        ]
        for decision in header_footer_result.suppressed_lines:
            header_footer_suppressed_by_page[decision.page] = header_footer_suppressed_by_page.get(decision.page, 0) + 1
        finish_stage("header_footer", header_footer_started)

    table_started = stage_start()
    logger.info("Extracting tables")
    table_result = extract_tables(
        config.input_pdf,
        selected_pages,
        config.password,
        table_mode,
        pdf=shared_plumber_pdf,
        text_lines_by_page=raw_lines_by_page,
    )
    finish_stage("table_extraction", table_started)
    table_result.rag_tables = normalize_rag_table_payload(table_result.rag_tables)
    image_started = stage_start()
    logger.info("Extracting images mode=%s", image_mode)
    page_image_boxes = {page: pdf_context.get_image_boxes(page) for page in selected_pages}
    image_result = extract_images(
        reader=reader,
        pdf_path=config.input_pdf,
        selected_pages=selected_pages,
        password=config.password,
        output_dir=config.output_dir,
        image_mode=image_mode,
        assets_dirname=config.assets_dirname,
        dedupe_images=config.dedupe_images,
        figure_crop_fallback=config.figure_crop_fallback,
        pdf=shared_plumber_pdf,
        page_image_boxes=page_image_boxes,
        page_text_lines=raw_lines_by_page,
    )
    finish_stage("image_extraction", image_started)
    engine_usage["tables"] = len(table_result.assets) > 0
    engine_usage["images"] = len(image_result.assets) > 0
    warnings.extend(table_result.warnings)
    warnings.extend(image_result.warnings)
    structure_marker_counts = count_structure_marker_reasons(image_result.excluded_assets)

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
    normalized_lines_by_page_for_blocks: dict[int, list[NormalizedLine]] = {}
    deduplicated_blocks_payload: list[dict] = []
    suppressed_lines_payload: list[dict] = list(header_footer_suppressed_payload)
    normalized_lines_debug_by_page: dict[int, list[dict]] = {}
    total_deduplicated_blocks = 0
    total_suppressed_lines = len(header_footer_suppressed_payload)
    normalization_started = stage_start()
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
        normalized_lines = normalization.lines
        if config.repair_hyphenation:
            normalized_lines, repair_count = _repair_hyphenated_normalized_lines(normalized_lines)
            hyphenation_repair_count += repair_count
        normalized_lines_by_page_for_blocks[page] = normalized_lines
        page_text_lines[page] = [line.text for line in normalized_lines]
        page_line_tops[page] = [line.top for line in normalized_lines]
        page_texts[page] = "\n".join(page_text_lines[page]).strip()
        normalized_lines_debug_by_page[page] = [line.model_dump(mode="json") for line in normalized_lines]
        page_result = page_results_map.get(page)
        if page_result is not None:
            header_footer_count = header_footer_suppressed_by_page.get(page, 0)
            page_result.char_count = len(page_texts[page])
            page_result.line_merge_count = normalization.line_merge_count
            page_result.structure_line_count = normalization.structure_line_count
            page_result.dedupe_count = normalization.dedupe_count
            page_result.header_footer_suppressed_count = header_footer_count
            page_result.suppressed_line_count = normalization.suppressed_line_count + header_footer_count
        total_deduplicated_blocks += normalization.dedupe_count
        total_suppressed_lines += normalization.suppressed_line_count
        deduplicated_blocks_payload.extend(
            [item.model_dump(mode="json") for item in normalization.deduplicated_blocks]
        )
        suppressed_lines_payload.extend([item.model_dump(mode="json") for item in normalization.suppressed_lines])
    finish_stage("normalization", normalization_started)

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

    rag_text_started = stage_start()
    text_block_result = build_text_blocks(normalized_lines_by_page_for_blocks)
    rag_text_block_record_count, rag_text_block_file_count = _write_rag_text_block_output(
        config,
        text_block_result.records,
    )
    font_heading_candidate_count = text_block_result.font_heading_candidate_count
    footnote_candidate_count = text_block_result.footnote_candidate_count
    structure_low_confidence_count = text_block_result.structure_low_confidence_count
    finish_stage("rag_text_blocks", rag_text_started)

    figure_rag_started = stage_start()
    figure_records = build_figure_records(
        images=image_result.assets,
        excluded_images=image_result.excluded_assets,
        text_block_records=text_block_result.records,
    )
    figure_rag_record_count, figure_rag_file_count = _write_figure_rag_output(config, figure_records)
    finish_stage("rag_figures", figure_rag_started)

    semantic_started = stage_start()
    semantic_result = build_semantic_layer(
        text_block_records=text_block_result.records,
        rag_tables=table_result.rag_tables,
    )
    (
        semantic_unit_record_count,
        semantic_unit_file_count,
        requirement_record_count,
        requirement_file_count,
        cross_ref_record_count,
        cross_ref_file_count,
    ) = _write_semantic_layer_outputs(
        config,
        semantic_units=semantic_result.semantic_units,
        requirements=semantic_result.requirements,
        cross_refs=semantic_result.cross_refs,
    )
    semantic_low_confidence_count = semantic_result.semantic_low_confidence_count
    unresolved_cross_ref_count = semantic_result.unresolved_cross_ref_count
    normative_requirement_count = semantic_result.normative_requirement_count
    finish_stage("rag_semantics", semantic_started)

    domain_units: list[dict] = []
    if domain_adapter is not DomainAdapterMode.NONE:
        domain_started = stage_start()
        domain_units = build_domain_units(
            domain_adapter=domain_adapter,
            rag_tables=table_result.rag_tables,
        )
        domain_unit_record_count, domain_unit_file_count = _write_domain_unit_output(config, domain_units)
        finish_stage("rag_domain_adapter", domain_started)

    retrieval_started = stage_start()
    retrieval_chunks = build_retrieval_chunks(
        text_block_records=text_block_result.records,
        semantic_units=semantic_result.semantic_units,
        requirements=semantic_result.requirements,
        rag_tables=table_result.rag_tables,
        domain_units=domain_units,
    )
    retrieval_chunk_record_count, retrieval_chunk_file_count = _write_retrieval_chunk_output(
        config,
        retrieval_chunks,
    )
    finish_stage("rag_retrieval_chunks", retrieval_started)

    markdown_started = stage_start()
    markdown_result = serialize_markdown_blocks_result(
        page_text_blocks={
            page: [block.to_record() for block in blocks]
            for page, blocks in text_block_result.blocks_by_page.items()
        },
        keep_page_markers=config.keep_page_markers,
        page_blocks_by_page=ordered_page_blocks,
    )
    markdown = markdown_result.markdown
    heading_count = markdown_result.heading_count
    list_item_count = markdown_result.list_item_count
    code_block_count = markdown_result.code_block_count
    markdown_path = config.output_dir / config.markdown_filename
    logger.info("Writing markdown path=%s", markdown_path)
    write_text(markdown_path, markdown)
    finish_stage("markdown_serialization", markdown_started)

    rag_started = stage_start()
    rag_table_record_count, rag_table_file_count = _write_rag_table_outputs(
        config=config,
        output_mode=rag_table_output,
        rag_tables=table_result.rag_tables,
    )
    finish_stage("rag_tables", rag_started)

    if config.debug:
        debug_started = stage_start()
        logger.info("Writing debug artifacts")
        _write_debug_artifacts(
            config=config,
            selected_pages=selected_pages,
            raw_lines_by_page=raw_lines_by_page,
            ordered_lines_by_page=page_layout_lines,
            normalized_lines_by_page=normalized_lines_debug_by_page,
            text_metadata_by_page=text_metadata_by_page,
            table_candidates_by_page=table_result.debug_candidates_by_page,
            image_candidates_by_page=image_result.debug_candidates_by_page,
        )
        finish_stage("debug_artifacts", debug_started)

    manifest_started = stage_start()
    manifest = Manifest(
        input_file=config.input_pdf.name,
        total_pages=total_pages,
        selected_pages=selected_pages,
        options={
            "image_mode": image_mode,
            "table_mode": table_mode.manifest_value(),
            "force_ocr": config.force_ocr,
            "ocr_lang": config.ocr_lang,
            "keep_page_markers": config.keep_page_markers,
            "remove_header_footer": config.remove_header_footer,
            "dedupe_images": config.dedupe_images,
            "repair_hyphenation": config.repair_hyphenation,
            "figure_crop_fallback": config.figure_crop_fallback,
            "rag_table_output": rag_table_output.value,
            "domain_adapter": domain_adapter.value,
            "rag_text_blocks_output": "jsonl",
            "rag_text_blocks_jsonl_filename": config.rag_text_blocks_jsonl_filename,
            "semantic_layer_output": "jsonl",
            "semantic_units_jsonl_filename": config.semantic_units_jsonl_filename,
            "requirements_jsonl_filename": config.requirements_jsonl_filename,
            "cross_refs_jsonl_filename": config.cross_refs_jsonl_filename,
            "retrieval_chunks_output": "jsonl",
            "retrieval_chunks_jsonl_filename": config.retrieval_chunks_jsonl_filename,
            "figures_rag_output": "jsonl",
            "figures_rag_jsonl_filename": config.figures_rag_jsonl_filename,
            "domain_units_jsonl_filename": config.domain_units_jsonl_filename,
            "debug": config.debug,
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
    finish_stage("manifest", manifest_started)

    finished_at = datetime.now(timezone.utc)
    page_results = [page_results_map[page] for page in sorted(page_results_map)]
    page_results, page_status_counts = finalize_page_statuses(page_results, warnings)
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

    status, exit_code = determine_conversion_status(warnings, failed_pages)
    reporting_started = stage_start()
    elapsed_seconds = (finished_at - started_at).total_seconds()
    pages_per_second = round(len(selected_pages) / elapsed_seconds, 4) if elapsed_seconds > 0 else None
    table_fallback_reason_counts = _count_table_fallback_reasons(table_result.fallbacks)
    table_low_quality_count = _count_low_quality_tables(table_result.table_quality)
    table_caption_linked_count = _count_caption_linked_tables(table_result.table_quality)
    finish_stage("reporting", reporting_started)
    report = build_report(
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
        low_confidence_pages=low_conf_pages,
        page_status_counts=page_status_counts,
        structure_marker_counts=structure_marker_counts,
        stage_durations_ms=stage_durations_ms,
        pdf_open_count=pdf_context.pdf_open_count + ocr_result.pdf_open_count,
        pages_per_second=pages_per_second,
        rag_table_output=rag_table_output.value,
        rag_table_record_count=rag_table_record_count,
        rag_table_file_count=rag_table_file_count,
        table_fallback_reason_counts=table_fallback_reason_counts,
        table_low_quality_count=table_low_quality_count,
        table_caption_linked_count=table_caption_linked_count,
        page_cache_hits=pdf_context.page_cache_hits,
        page_cache_misses=pdf_context.page_cache_misses,
        text_line_extract_count=pdf_context.text_line_extract_count,
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
        figure_rag_record_count=figure_rag_record_count,
        figure_rag_file_count=figure_rag_file_count,
        domain_unit_record_count=domain_unit_record_count,
        domain_unit_file_count=domain_unit_file_count,
    )
    report_path = config.output_dir / config.report_filename
    logger.info("Writing report path=%s status=%s exit_code=%s", report_path, status.value, exit_code)
    write_json(report_path, serialize_report(report))
    pdf_context.close()

    return ConversionResult(
        exit_code=exit_code,
        markdown_path=markdown_path,
        manifest_path=manifest_path,
        report_path=report_path,
        warnings=warnings,
        status=status,
        report=report,
    )
