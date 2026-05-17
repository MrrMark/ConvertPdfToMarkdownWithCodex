from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from pdf2md.batch_runner import BatchConversionOptions, run_batch_conversion as run_shared_batch_conversion
from pdf2md.config import Config, default_output_dir_for_input
from pdf2md.models import (
    DomainAdapterMode,
    ImageMode,
    RagTableOutputMode,
    TableMode,
)
from pdf2md.pipeline import run_conversion
from pdf2md.utils.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdf2md", description="Convert PDF to Markdown")
    parser.add_argument("input_pdf", nargs="?", help="Input PDF file path")
    parser.add_argument("--input-dir", default=None, help="Input directory containing PDF files for batch conversion")
    parser.add_argument("-o", "--output-dir", default=None, help="Output directory for single PDF conversion")
    parser.add_argument("--skip-existing", action="store_true", default=False, help="Skip batch documents with existing core outputs")
    parser.add_argument(
        "--previous-corpus-manifest",
        type=Path,
        default=None,
        help="Previous corpus_manifest.json for incremental RAG ingest diff in batch mode.",
    )
    parser.add_argument(
        "--reuse-unchanged",
        action="store_true",
        default=False,
        help="Reuse previous batch outputs for unchanged PDFs when --previous-corpus-manifest is provided.",
    )
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
    parser.add_argument(
        "--rag-table-output",
        choices=[m.value for m in RagTableOutputMode],
        default=RagTableOutputMode.NONE.value,
        help="Optional RAG sidecar table output: none, markdown, jsonl, or both.",
    )
    parser.add_argument(
        "--domain-adapter",
        choices=[m.value for m in DomainAdapterMode],
        default=DomainAdapterMode.NONE.value,
        help="Optional domain-specific RAG adapter: nvme, pcie, ocp, tcg, or customer-requirements.",
    )
    parser.add_argument(
        "--confidential-safe-mode",
        action="store_true",
        default=False,
        help="Redact source filenames/paths in public metadata and emit sanitized_report.json.",
    )
    parser.add_argument("--force-ocr", action="store_true", default=False)
    parser.add_argument("--ocr-lang", default="eng", help="Tesseract language code for OCR, for example eng or kor+eng.")
    parser.add_argument(
        "--page-workers",
        type=int,
        default=1,
        help="Opt-in page-level text/read-order/table-candidate workers. Use 1 for the deterministic single-worker path.",
    )
    parser.add_argument(
        "--remove-header-footer",
        action="store_true",
        default=False,
        help="Conservatively suppress repeated page headers and footers.",
    )
    parser.add_argument(
        "--dedupe-images",
        action="store_true",
        default=False,
        help="Reuse the first extracted file for repeated image objects with the same sha256.",
    )
    parser.add_argument(
        "--repair-hyphenation",
        action="store_true",
        default=False,
        help="Opt-in repair for clear line-break hyphenation.",
    )
    parser.add_argument(
        "--figure-crop-fallback",
        action="store_true",
        default=False,
        help="Opt-in page crop fallback for captioned figures without embedded image objects.",
    )
    marker_group = parser.add_mutually_exclusive_group()
    marker_group.add_argument("--keep-page-markers", dest="keep_page_markers", action="store_true")
    marker_group.add_argument("--no-page-markers", dest="keep_page_markers", action="store_false")
    parser.set_defaults(keep_page_markers=False)
    parser.add_argument("--debug", action="store_true", default=False)
    parser.add_argument("--verbose", action="store_true", default=False)
    return parser


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
        rag_table_output=RagTableOutputMode(args.rag_table_output),
        domain_adapter=DomainAdapterMode(args.domain_adapter),
        confidential_safe_mode=args.confidential_safe_mode,
        force_ocr=args.force_ocr,
        ocr_lang=args.ocr_lang,
        keep_page_markers=args.keep_page_markers,
        remove_header_footer=args.remove_header_footer,
        dedupe_images=args.dedupe_images,
        repair_hyphenation=args.repair_hyphenation,
        figure_crop_fallback=args.figure_crop_fallback,
        page_workers=args.page_workers,
        debug=args.debug,
        verbose=args.verbose,
        skip_existing=args.skip_existing,
    )


def _run_batch_conversion(args: argparse.Namespace) -> int:
    options = BatchConversionOptions(
        pages=args.pages,
        password=args.password,
        image_mode=ImageMode(args.image_mode),
        table_mode=TableMode(args.table_mode),
        rag_table_output=RagTableOutputMode(args.rag_table_output),
        domain_adapter=DomainAdapterMode(args.domain_adapter),
        confidential_safe_mode=args.confidential_safe_mode,
        force_ocr=args.force_ocr,
        ocr_lang=args.ocr_lang,
        keep_page_markers=args.keep_page_markers,
        remove_header_footer=args.remove_header_footer,
        dedupe_images=args.dedupe_images,
        repair_hyphenation=args.repair_hyphenation,
        figure_crop_fallback=args.figure_crop_fallback,
        page_workers=args.page_workers,
        debug=args.debug,
        verbose=args.verbose,
        skip_existing=args.skip_existing,
        previous_corpus_manifest=args.previous_corpus_manifest,
        reuse_unchanged=args.reuse_unchanged,
    )
    return run_shared_batch_conversion(input_dir=Path(args.input_dir), options=options).exit_code


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose, debug=args.debug)

    if args.input_pdf and args.input_dir:
        parser.error("Use either input_pdf or --input-dir, not both.")
    if not args.input_pdf and not args.input_dir:
        parser.error("Provide an input PDF path or --input-dir.")
    if args.previous_corpus_manifest is not None and not args.input_dir:
        parser.error("--previous-corpus-manifest is only supported with --input-dir batch mode.")
    if args.reuse_unchanged and args.previous_corpus_manifest is None:
        parser.error("--reuse-unchanged requires --previous-corpus-manifest.")

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
