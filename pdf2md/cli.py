from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from pdf2md.batch_runner import BatchConversionOptions, run_batch_conversion as run_shared_batch_conversion
from pdf2md.config import Config, SUPPORTED_RETRIEVAL_TOKENIZERS, default_output_dir_for_input
from pdf2md.models import (
    DomainAdapterMode,
    ImageMode,
    OutputProfile,
    RagSidecarScope,
    RagTableOutputMode,
    TableMode,
)
from pdf2md.pipeline import run_conversion
from pdf2md.rag_profiles import SUPPORTED_RAG_PURPOSE_PROFILES, rag_profile_options
from pdf2md.utils.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdf2md", description="Convert PDF to Markdown")
    parser.add_argument("input_pdf", nargs="?", help="Input PDF file path")
    parser.add_argument("--input-dir", default=None, help="Input directory containing PDF files for batch conversion")
    parser.add_argument("-o", "--output-dir", default=None, help="Output directory for single PDF conversion")
    parser.add_argument(
        "--rag-profile",
        choices=SUPPORTED_RAG_PURPOSE_PROFILES,
        default="preserve",
        help="Purpose-specific local option bundle for RAG-oriented conversion.",
    )
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
        default=None,
    )
    parser.add_argument(
        "--table-mode",
        choices=[m.value for m in TableMode],
        default=None,
        help="Table output mode: auto, html, markdown. html-only/gfm-only are legacy compatibility modes.",
    )
    parser.add_argument(
        "--rag-table-output",
        choices=[m.value for m in RagTableOutputMode],
        default=None,
        help="Optional RAG sidecar table output: none, markdown, jsonl, or both.",
    )
    parser.add_argument(
        "--output-profile",
        choices=[m.value for m in OutputProfile],
        default=OutputProfile.FULL.value,
        help="Output profile. full preserves the default artifact contract; fast omits RAG sidecars unless overridden.",
    )
    parser.add_argument(
        "--rag-sidecar-scope",
        choices=[m.value for m in RagSidecarScope],
        default=None,
        help="Opt-in RAG sidecar scope: full, minimal, or none. Defaults to full, or none with --output-profile fast.",
    )
    parser.add_argument(
        "--domain-adapter",
        choices=[m.value for m in DomainAdapterMode],
        default=None,
        help="Optional domain-specific RAG adapter: nvme, pcie, ocp, tcg, spdm, or customer-requirements.",
    )
    parser.add_argument(
        "--require-domain-adapter-for-technical-profile",
        action="store_true",
        default=False,
        help="Fail fast when --rag-profile technical_spec_rag is used without --domain-adapter.",
    )
    parser.add_argument(
        "--confidential-safe-mode",
        action="store_true",
        default=None,
        help="Redact source filenames/paths in public metadata and emit sanitized_report.json.",
    )
    parser.add_argument("--force-ocr", action="store_true", default=None)
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
        default=None,
        help="Conservatively suppress repeated page headers and footers.",
    )
    parser.add_argument(
        "--dedupe-images",
        action="store_true",
        default=None,
        help="Reuse the first extracted file for repeated image objects with the same sha256.",
    )
    parser.add_argument(
        "--repair-hyphenation",
        action="store_true",
        default=None,
        help="Opt-in repair for clear line-break hyphenation.",
    )
    parser.add_argument(
        "--figure-crop-fallback",
        action="store_true",
        default=None,
        help="Opt-in page crop fallback for captioned figures without embedded image objects.",
    )
    parser.add_argument(
        "--retrieval-chunk-max-tokens",
        type=int,
        default=None,
        help="Maximum token budget for deterministic retrieval chunk splitting.",
    )
    parser.add_argument(
        "--retrieval-tokenizer",
        choices=SUPPORTED_RETRIEVAL_TOKENIZERS,
        default=None,
        help="Token counter used for retrieval chunk budget diagnostics.",
    )
    parser.add_argument(
        "--rag-contextual-embedding-text",
        action="store_true",
        default=None,
        help="Add optional context-prefixed embedding_text for table-like retrieval chunks without changing text.",
    )
    parser.add_argument(
        "--rag-merge-sibling-text-chunks",
        action="store_true",
        default=None,
        help="Merge adjacent same-section text_block retrieval chunks when the combined text fits the token budget.",
    )
    parser.add_argument(
        "--rag-chunk-relationship-metadata",
        action="store_true",
        default=None,
        help="Add optional previous/next/section anchor metadata to retrieval chunks.",
    )
    marker_group = parser.add_mutually_exclusive_group()
    marker_group.add_argument("--keep-page-markers", dest="keep_page_markers", action="store_true")
    marker_group.add_argument("--no-page-markers", dest="keep_page_markers", action="store_false")
    parser.set_defaults(keep_page_markers=None)
    parser.add_argument("--debug", action="store_true", default=False)
    parser.add_argument("--verbose", action="store_true", default=False)
    return parser


def _option_value(value: object | None, default: object) -> object:
    return default if value is None else value


def _build_single_config(args: argparse.Namespace) -> Config:
    input_pdf = Path(args.input_pdf)
    output_dir = Path(args.output_dir) if args.output_dir is not None else default_output_dir_for_input(input_pdf)
    profile_options = rag_profile_options(args.rag_profile)
    return Config(
        input_pdf=input_pdf,
        output_dir=output_dir,
        pages=args.pages,
        password=args.password,
        image_mode=ImageMode(_option_value(args.image_mode, profile_options.image_mode)),
        table_mode=TableMode(_option_value(args.table_mode, profile_options.table_mode)),
        rag_table_output=RagTableOutputMode(_option_value(args.rag_table_output, profile_options.rag_table_output)),
        output_profile=OutputProfile(args.output_profile),
        rag_sidecar_scope=RagSidecarScope(args.rag_sidecar_scope) if args.rag_sidecar_scope is not None else None,
        rag_profile=args.rag_profile,
        domain_adapter=DomainAdapterMode(_option_value(args.domain_adapter, profile_options.domain_adapter)),
        confidential_safe_mode=_option_value(args.confidential_safe_mode, profile_options.confidential_safe_mode),
        force_ocr=_option_value(args.force_ocr, profile_options.force_ocr),
        ocr_lang=args.ocr_lang,
        keep_page_markers=_option_value(args.keep_page_markers, profile_options.keep_page_markers),
        remove_header_footer=_option_value(args.remove_header_footer, profile_options.remove_header_footer),
        dedupe_images=_option_value(args.dedupe_images, profile_options.dedupe_images),
        repair_hyphenation=_option_value(args.repair_hyphenation, profile_options.repair_hyphenation),
        figure_crop_fallback=_option_value(args.figure_crop_fallback, profile_options.figure_crop_fallback),
        retrieval_chunk_max_tokens=_option_value(
            args.retrieval_chunk_max_tokens,
            profile_options.retrieval_chunk_max_tokens,
        ),
        retrieval_tokenizer=_option_value(args.retrieval_tokenizer, profile_options.retrieval_tokenizer),
        rag_contextual_embedding_text=_option_value(
            args.rag_contextual_embedding_text,
            profile_options.rag_contextual_embedding_text,
        ),
        rag_merge_sibling_text_chunks=_option_value(
            args.rag_merge_sibling_text_chunks,
            profile_options.rag_merge_sibling_text_chunks,
        ),
        rag_chunk_relationship_metadata=_option_value(
            args.rag_chunk_relationship_metadata,
            profile_options.rag_chunk_relationship_metadata,
        ),
        page_workers=args.page_workers,
        debug=args.debug,
        verbose=args.verbose,
        skip_existing=args.skip_existing,
    )


def _run_batch_conversion(args: argparse.Namespace) -> int:
    profile_options = rag_profile_options(args.rag_profile)
    options = BatchConversionOptions(
        pages=args.pages,
        password=args.password,
        image_mode=ImageMode(_option_value(args.image_mode, profile_options.image_mode)),
        table_mode=TableMode(_option_value(args.table_mode, profile_options.table_mode)),
        rag_table_output=RagTableOutputMode(_option_value(args.rag_table_output, profile_options.rag_table_output)),
        output_profile=OutputProfile(args.output_profile),
        rag_sidecar_scope=RagSidecarScope(args.rag_sidecar_scope) if args.rag_sidecar_scope is not None else None,
        rag_profile=args.rag_profile,
        domain_adapter=DomainAdapterMode(_option_value(args.domain_adapter, profile_options.domain_adapter)),
        confidential_safe_mode=_option_value(args.confidential_safe_mode, profile_options.confidential_safe_mode),
        force_ocr=_option_value(args.force_ocr, profile_options.force_ocr),
        ocr_lang=args.ocr_lang,
        keep_page_markers=_option_value(args.keep_page_markers, profile_options.keep_page_markers),
        remove_header_footer=_option_value(args.remove_header_footer, profile_options.remove_header_footer),
        dedupe_images=_option_value(args.dedupe_images, profile_options.dedupe_images),
        repair_hyphenation=_option_value(args.repair_hyphenation, profile_options.repair_hyphenation),
        figure_crop_fallback=_option_value(args.figure_crop_fallback, profile_options.figure_crop_fallback),
        retrieval_chunk_max_tokens=_option_value(
            args.retrieval_chunk_max_tokens,
            profile_options.retrieval_chunk_max_tokens,
        ),
        retrieval_tokenizer=_option_value(args.retrieval_tokenizer, profile_options.retrieval_tokenizer),
        rag_contextual_embedding_text=_option_value(
            args.rag_contextual_embedding_text,
            profile_options.rag_contextual_embedding_text,
        ),
        rag_merge_sibling_text_chunks=_option_value(
            args.rag_merge_sibling_text_chunks,
            profile_options.rag_merge_sibling_text_chunks,
        ),
        rag_chunk_relationship_metadata=_option_value(
            args.rag_chunk_relationship_metadata,
            profile_options.rag_chunk_relationship_metadata,
        ),
        page_workers=args.page_workers,
        debug=args.debug,
        verbose=args.verbose,
        skip_existing=args.skip_existing,
        previous_corpus_manifest=args.previous_corpus_manifest,
        reuse_unchanged=args.reuse_unchanged,
    )
    return run_shared_batch_conversion(input_dir=Path(args.input_dir), options=options).exit_code


def _selected_domain_adapter(args: argparse.Namespace) -> DomainAdapterMode:
    profile_options = rag_profile_options(args.rag_profile)
    return DomainAdapterMode(_option_value(args.domain_adapter, profile_options.domain_adapter))


def _validate_profile_contract(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if (
        args.require_domain_adapter_for_technical_profile
        and args.rag_profile == "technical_spec_rag"
        and _selected_domain_adapter(args) is DomainAdapterMode.NONE
    ):
        parser.error("--rag-profile technical_spec_rag requires --domain-adapter when strict domain validation is enabled.")


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
    _validate_profile_contract(args, parser)

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
