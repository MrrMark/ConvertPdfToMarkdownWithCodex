from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from pdf2md.config import Config
from pdf2md.models import ImageMode, TableMode
from pdf2md.pipeline import EXIT_FATAL, EXIT_PARTIAL, run_conversion
from pdf2md.utils.io import write_json
from pdf2md.utils.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdf2md", description="Convert PDF to Markdown")
    parser.add_argument("input_pdf", nargs="?", help="Input PDF file path")
    parser.add_argument("--input-dir", default=None, help="Input directory containing PDF files for batch conversion")
    parser.add_argument("-o", "--output-dir", default=None, help="Output directory for single PDF conversion")
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
    return Config(
        input_pdf=Path(args.input_pdf),
        output_dir=Path(args.output_dir),
        pages=args.pages,
        password=args.password,
        image_mode=ImageMode(args.image_mode),
        table_mode=TableMode(args.table_mode),
        force_ocr=args.force_ocr,
        keep_page_markers=args.keep_page_markers,
        debug=args.debug,
        verbose=args.verbose,
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
        markdown_filename=f"{stem}.md",
        manifest_filename=f"{stem}_manifest.json",
        report_filename=f"{stem}_report.json",
        assets_dirname=f"{stem}_assets",
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

    documents: list[dict[str, object]] = []
    success_count = 0
    partial_count = 0
    failed_count = 0
    final_exit_code = 0

    for pdf_path in pdf_paths:
        document_output_dir = batch_output_root / pdf_path.stem
        config = _build_batch_config(args, pdf_path, document_output_dir)
        result = run_conversion(config)
        status = "success"
        if result.exit_code == EXIT_FATAL:
            status = "failed"
            failed_count += 1
            final_exit_code = EXIT_PARTIAL
        elif result.exit_code == EXIT_PARTIAL:
            status = "partial_success"
            partial_count += 1
            final_exit_code = EXIT_PARTIAL
        else:
            success_count += 1
        documents.append(
            {
                "input_pdf": str(pdf_path),
                "status": status,
                "exit_code": result.exit_code,
                "output_dir": str(document_output_dir),
                "files": {
                    "markdown": str(result.markdown_path) if result.markdown_path else None,
                    "manifest": str(result.manifest_path) if result.manifest_path else None,
                    "report": str(result.report_path) if result.report_path else None,
                },
            }
        )

    batch_report = {
        "input_dir": str(input_dir),
        "output_dir": str(batch_output_root),
        "pdf_files": [str(path) for path in pdf_paths],
        "documents": documents,
        "summary": {
            "total_documents": len(pdf_paths),
            "success_count": success_count,
            "partial_success_count": partial_count,
            "failed_count": failed_count,
        },
    }
    write_json(batch_output_root / "batch_report.json", batch_report)
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

    if args.output_dir is None:
        parser.error("--output-dir is required for single PDF conversion.")

    config = _build_single_config(args)
    result = run_conversion(config)
    return result.exit_code
