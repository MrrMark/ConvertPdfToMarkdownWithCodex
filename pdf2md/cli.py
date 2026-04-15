from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from pdf2md.config import Config
from pdf2md.models import ImageMode, TableMode
from pdf2md.pipeline import run_conversion
from pdf2md.utils.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdf2md", description="Convert PDF to Markdown")
    parser.add_argument("input_pdf", help="Input PDF file path")
    parser.add_argument("-o", "--output-dir", required=True, help="Output directory")
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


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose, debug=args.debug)

    config = Config(
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

    result = run_conversion(config)
    return result.exit_code
