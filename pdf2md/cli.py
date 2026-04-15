from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from pdf2md.config import Config, default_output_dir_for_input
from pdf2md.models import BatchDocumentFiles, BatchDocumentResult, BatchReport, BatchReportSummary, ConversionStatus, ImageMode, Manifest, Report, TableMode
from pdf2md.pipeline import EXIT_FATAL, EXIT_PARTIAL, run_conversion
from pdf2md.utils.io import write_json
from pdf2md.utils.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdf2md", description="Convert PDF to Markdown")
    parser.add_argument("input_pdf", nargs="?", help="Input PDF file path")
    parser.add_argument("--input-dir", default=None, help="Input directory containing PDF files for batch conversion")
    parser.add_argument("-o", "--output-dir", default=None, help="Output directory for single PDF conversion")
    parser.add_argument("--skip-existing", action="store_true", default=False, help="Skip batch documents with existing core outputs")
    parser.add_argument("--pages", default=None, help="Page ranges (example: 1-3,5)")
    parser.add_argument("--password", default=None, help="Password for encrypted PDF")
    parser.add_argument(
        "--image-mode",
        choices=[m.value for m in ImageMode],
        default=ImageMode.REFERENCED.value,
    )
    parser.add_argument(
        "--table-mode",
        choices=[m.value for m in TableMode],
        default=TableMode.AUTO.value,
        help="Table output mode: auto, html, markdown. html-only/gfm-only are legacy compatibility modes.",
    )
    parser.add_argument("--force-ocr", action="store_true", default=False)
    marker_group = parser.add_mutually_exclusive_group()
    marker_group.add_argument("--keep-page-markers", dest="keep_page_markers", action="store_true")
    marker_group.add_argument("--no-page-markers", dest="keep_page_markers", action="store_false")
    parser.set_defaults(keep_page_markers=False)
    parser.add_argument("--debug", action="store_true", default=False)
    parser.add_argument("--verbose", action="store_true", default=False)
    return parser


def _iter_pdf_paths(input_dir: Path) -> list[Path]:
    return sorted(
        [path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"],
        key=lambda path: path.name.lower(),
    )


def _detect_duplicate_stems(pdf_paths: list[Path]) -> list[str]:
    stem_map: dict[str, list[str]] = {}
    for path in pdf_paths:
        key = path.stem.casefold()
        stem_map.setdefault(key, []).append(path.name)
    duplicates = []
    for names in stem_map.values():
        if len(names) > 1:
            duplicates.append(", ".join(sorted(names)))
    return sorted(duplicates)


def _build_single_config(args: argparse.Namespace) -> Config:
    input_pdf = Path(args.input_pdf)
    output_dir = Path(args.output_dir) if args.output_dir is not None else default_output_dir_for_input(input_pdf)
    return Config(
        input_pdf=input_pdf,
        output_dir=output_dir,
        pages=args.pages,
        password=args.password,
        image_mode=ImageMode(args.image_mode),
        table_mode=TableMode(args.table_mode),
        force_ocr=args.force_ocr,
        keep_page_markers=args.keep_page_markers,
        debug=args.debug,
        verbose=args.verbose,
        skip_existing=args.skip_existing,
    )


def _build_batch_config(args: argparse.Namespace, pdf_path: Path, output_dir: Path) -> Config:
    stem = pdf_path.stem
    return Config(
        input_pdf=pdf_path,
        output_dir=output_dir,
        pages=args.pages,
        password=args.password,
        image_mode=ImageMode(args.image_mode),
        table_mode=TableMode(args.table_mode),
        force_ocr=args.force_ocr,
        keep_page_markers=args.keep_page_markers,
        debug=args.debug,
        verbose=args.verbose,
        skip_existing=args.skip_existing,
        markdown_filename=f"{stem}.md",
        manifest_filename=f"{stem}_manifest.json",
        report_filename=f"{stem}_report.json",
        assets_dirname=f"{stem}_assets",
    )


def _core_output_paths(config: Config) -> BatchDocumentFiles:
    return BatchDocumentFiles(
        markdown=str(config.output_dir / config.markdown_filename),
        manifest=str(config.output_dir / config.manifest_filename),
        report=str(config.output_dir / config.report_filename),
    )


def _batch_config_has_existing_outputs(config: Config) -> bool:
    paths = _core_output_paths(config)
    return all(path is not None and Path(path).exists() for path in (paths.markdown, paths.manifest, paths.report))


def _load_json_model(path: Path, model_cls):
    return model_cls.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _build_skipped_batch_document(pdf_path: Path, config: Config) -> BatchDocumentResult:
    files = _core_output_paths(config)
    report = _load_json_model(Path(files.report or ""), Report)
    manifest = _load_json_model(Path(files.manifest or ""), Manifest)
    return BatchDocumentResult(
        input_pdf=str(pdf_path),
        status="skipped",
        exit_code=0,
        output_dir=str(config.output_dir),
        started_at=report.started_at,
        finished_at=report.finished_at,
        duration_ms=report.duration_ms,
        warning_count=len(report.warnings),
        table_count=len(manifest.tables),
        image_count=len(manifest.images),
        used_ocr=bool(report.engine_usage.get("ocr", False)),
        skipped=True,
        files=files,
    )


def _build_batch_document_result(pdf_path: Path, config: Config, result) -> BatchDocumentResult:
    report = result.report
    assert report is not None
    manifest_path = config.output_dir / config.manifest_filename
    manifest = _load_json_model(manifest_path, Manifest) if manifest_path.exists() else None
    return BatchDocumentResult(
        input_pdf=str(pdf_path),
        status=result.status.value,
        exit_code=result.exit_code,
        output_dir=str(config.output_dir),
        started_at=report.started_at,
        finished_at=report.finished_at,
        duration_ms=report.duration_ms,
        warning_count=len(report.warnings),
        table_count=len(manifest.tables) if manifest is not None else 0,
        image_count=len(manifest.images) if manifest is not None else 0,
        used_ocr=bool(report.engine_usage.get("ocr", False)),
        skipped=False,
        files=BatchDocumentFiles(
            markdown=str(result.markdown_path) if result.markdown_path else None,
            manifest=str(result.manifest_path) if result.manifest_path else None,
            report=str(result.report_path) if result.report_path else None,
        ),
    )


def _run_batch_conversion(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir)
    if not input_dir.exists() or not input_dir.is_dir():
        raise ValueError(f"Input directory does not exist or is not a directory: {input_dir}")
    pdf_paths = _iter_pdf_paths(input_dir)
    if not pdf_paths:
        raise ValueError(f"No PDF files found in directory: {input_dir}")
    duplicate_stems = _detect_duplicate_stems(pdf_paths)
    if duplicate_stems:
        raise ValueError(f"Duplicate PDF stems found: {'; '.join(duplicate_stems)}")

    batch_output_root = input_dir / "output"
    batch_output_root.mkdir(parents=True, exist_ok=True)

    documents: list[BatchDocumentResult] = []
    success_count = 0
    partial_count = 0
    failed_count = 0
    skipped_count = 0
    final_exit_code = 0

    for pdf_path in pdf_paths:
        document_output_dir = batch_output_root / pdf_path.stem
        config = _build_batch_config(args, pdf_path, document_output_dir)
        if args.skip_existing and _batch_config_has_existing_outputs(config):
            documents.append(_build_skipped_batch_document(pdf_path, config))
            skipped_count += 1
            continue
        result = run_conversion(config)
        if result.status == ConversionStatus.FAILED:
            failed_count += 1
            final_exit_code = EXIT_PARTIAL
        elif result.status == ConversionStatus.PARTIAL_SUCCESS:
            partial_count += 1
            final_exit_code = EXIT_PARTIAL
        else:
            success_count += 1
        documents.append(_build_batch_document_result(pdf_path, config, result))

    batch_report = BatchReport(
        input_dir=str(input_dir),
        output_dir=str(batch_output_root),
        pdf_files=[str(path) for path in pdf_paths],
        documents=documents,
        summary=BatchReportSummary(
            total_documents=len(pdf_paths),
            success_count=success_count,
            partial_success_count=partial_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
        ),
    )
    write_json(batch_output_root / "batch_report.json", batch_report.model_dump(mode="json"))
    return final_exit_code


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose, debug=args.debug)

    if args.input_pdf and args.input_dir:
        parser.error("Use either input_pdf or --input-dir, not both.")
    if not args.input_pdf and not args.input_dir:
        parser.error("Provide an input PDF path or --input-dir.")

    if args.input_dir:
        if args.output_dir is not None:
            parser.error("--output-dir is not supported with --input-dir batch mode.")
        try:
            return _run_batch_conversion(args)
        except ValueError as exc:
            parser.error(str(exc))

    config = _build_single_config(args)
    result = run_conversion(config)
    return result.exit_code
