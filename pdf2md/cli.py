from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from pdf2md.batch_runner import BatchConversionOptions, run_batch_conversion as run_shared_batch_conversion
from pdf2md.config import (
    Config,
    SUPPORTED_FIGURE_DESCRIPTION_BACKENDS,
    SUPPORTED_OCR_BACKENDS,
    SUPPORTED_RETRIEVAL_TOKENIZERS,
    default_output_dir_for_input,
)
from pdf2md.models import (
    DomainAdapterMode,
    ImageMode,
    OutputProfile,
    RagSidecarScope,
    RagTableOutputMode,
    TableMode,
)
from pdf2md.pipeline import run_conversion
from pdf2md.preflight import (
    PLAN_APPLY_CONFIG_OPTIONS,
    PLAN_APPLY_REPORT_FILENAME,
    apply_large_spec_plan_options,
    load_large_spec_plan,
)
from pdf2md.rag_profiles import SUPPORTED_RAG_PURPOSE_PROFILES, TECHNICAL_SPEC_RAG_PROFILES, rag_profile_options
from pdf2md.utils.logging import configure_logging


PLAN_APPLY_CLI_FLAGS = {
    "--rag-profile": "rag_profile",
    "--domain-adapter": "domain_adapter",
    "--image-mode": "image_mode",
    "--rag-sidecar-scope": "rag_sidecar_scope",
    "--page-workers": "page_workers",
    "--image-extraction-page-timeout-seconds": "image_extraction_page_timeout_seconds",
    "--image-extraction-stage-timeout-seconds": "image_extraction_stage_timeout_seconds",
    "--figure-semantics-stage-timeout-seconds": "figure_semantics_stage_timeout_seconds",
}


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
    parser.add_argument(
        "--apply-plan",
        type=Path,
        default=None,
        help=(
            "Opt-in apply a large-spec preflight plan JSON to safe conversion options. "
            "Direct CLI options keep precedence."
        ),
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
        help=(
            "Optional domain-specific RAG adapter: nvme, pcie, ocp, tcg, spdm, caliptra, "
            "customer-requirements, or manual."
        ),
    )
    parser.add_argument(
        "--manual-domain-adapter-label",
        default=None,
        help="Optional display label for --domain-adapter manual, for example a customer requirement profile name.",
    )
    parser.add_argument(
        "--manual-domain-adapter-keywords",
        default=None,
        help="Comma-, semicolon-, or newline-separated table header keywords for --domain-adapter manual.",
    )
    parser.add_argument(
        "--require-domain-adapter-for-technical-profile",
        action="store_true",
        default=False,
        help="Fail fast when a technical spec RAG profile is used without --domain-adapter.",
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
        "--ocr-backend",
        choices=SUPPORTED_OCR_BACKENDS,
        default="tesseract",
        help="OCR backend for conversion. Defaults to tesseract; optional backends report structured warnings when unavailable.",
    )
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
        "--image-extraction-page-timeout-seconds",
        type=float,
        default=None,
        help="Optional per-page image extraction timeout. Timed-out pages are skipped with structured warnings.",
    )
    parser.add_argument(
        "--image-extraction-stage-timeout-seconds",
        type=float,
        default=None,
        help="Optional image extraction stage timeout. Remaining image pages are skipped on timeout.",
    )
    parser.add_argument(
        "--figure-semantics-stage-timeout-seconds",
        type=float,
        default=None,
        help="Optional timeout for figure OCR, generated descriptions, and structure sidecars.",
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
    parser.add_argument(
        "--rag-figure-text-chunks",
        action="store_true",
        default=None,
        help="Opt-in observed-text figure retrieval chunks for assetless RAG indexing.",
    )
    parser.add_argument(
        "--figure-region-ocr",
        action="store_true",
        default=None,
        help="Opt-in figure-region OCR evidence promotion for diagram labels.",
    )
    parser.add_argument(
        "--rag-generated-figure-descriptions",
        action="store_true",
        default=None,
        help="Opt-in generated figure description sidecar/chunks from observed figure context.",
    )
    parser.add_argument(
        "--figure-description-backend",
        choices=SUPPORTED_FIGURE_DESCRIPTION_BACKENDS,
        default=None,
        help="Backend label for generated figure descriptions. Current implementation is deterministic local context.",
    )
    parser.add_argument(
        "--figure-structure-extraction",
        action="store_true",
        default=None,
        help="Opt-in conservative figure structure sidecar/chunks for diagrams, waveforms, and block/circuit figures.",
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


def _explicit_plan_apply_options(argv: list[str]) -> set[str]:
    explicit_options: set[str] = set()
    for token in argv:
        option = token.split("=", 1)[0]
        mapped = PLAN_APPLY_CLI_FLAGS.get(option)
        if mapped is not None:
            explicit_options.add(mapped)
    return explicit_options


def _plan_apply_current_options(args: argparse.Namespace) -> dict[str, object | None]:
    return {
        "rag_profile": args.rag_profile,
        "domain_adapter": args.domain_adapter,
        "image_mode": args.image_mode,
        "rag_sidecar_scope": args.rag_sidecar_scope,
        "page_workers": args.page_workers,
        "image_extraction_page_timeout_seconds": args.image_extraction_page_timeout_seconds,
        "image_extraction_stage_timeout_seconds": args.image_extraction_stage_timeout_seconds,
        "figure_semantics_stage_timeout_seconds": args.figure_semantics_stage_timeout_seconds,
    }


def _apply_plan_to_args(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    *,
    explicit_options: set[str],
) -> None:
    if args.apply_plan is None:
        args._plan_apply_audit = None
        return
    try:
        plan_path = args.apply_plan.resolve()
        plan = load_large_spec_plan(plan_path)
        applied_options, audit = apply_large_spec_plan_options(
            plan,
            current_options=_plan_apply_current_options(args),
            explicit_options=explicit_options,
            allowed_options=PLAN_APPLY_CONFIG_OPTIONS,
            source_plan_path=plan_path,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    for option, value in applied_options.items():
        setattr(args, option, value)
    args._plan_apply_audit = audit


def _write_plan_apply_report(output_dir: Path, audit: dict[str, object] | None) -> None:
    if audit is None:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / PLAN_APPLY_REPORT_FILENAME
    report_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
        manual_domain_adapter_label=args.manual_domain_adapter_label,
        manual_domain_adapter_keywords=args.manual_domain_adapter_keywords,
        confidential_safe_mode=_option_value(args.confidential_safe_mode, profile_options.confidential_safe_mode),
        force_ocr=_option_value(args.force_ocr, profile_options.force_ocr),
        ocr_lang=args.ocr_lang,
        ocr_backend=args.ocr_backend,
        keep_page_markers=_option_value(args.keep_page_markers, profile_options.keep_page_markers),
        remove_header_footer=_option_value(args.remove_header_footer, profile_options.remove_header_footer),
        dedupe_images=_option_value(args.dedupe_images, profile_options.dedupe_images),
        repair_hyphenation=_option_value(args.repair_hyphenation, profile_options.repair_hyphenation),
        figure_crop_fallback=_option_value(args.figure_crop_fallback, profile_options.figure_crop_fallback),
        image_extraction_page_timeout_seconds=args.image_extraction_page_timeout_seconds,
        image_extraction_stage_timeout_seconds=args.image_extraction_stage_timeout_seconds,
        figure_semantics_stage_timeout_seconds=args.figure_semantics_stage_timeout_seconds,
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
        rag_figure_text_chunks=_option_value(
            args.rag_figure_text_chunks,
            profile_options.rag_figure_text_chunks,
        ),
        figure_region_ocr=_option_value(args.figure_region_ocr, profile_options.figure_region_ocr),
        rag_generated_figure_descriptions=_option_value(
            args.rag_generated_figure_descriptions,
            profile_options.rag_generated_figure_descriptions,
        ),
        figure_description_backend=_option_value(
            args.figure_description_backend,
            profile_options.figure_description_backend,
        ),
        figure_structure_extraction=_option_value(
            args.figure_structure_extraction,
            profile_options.figure_structure_extraction,
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
        manual_domain_adapter_label=args.manual_domain_adapter_label,
        manual_domain_adapter_keywords=args.manual_domain_adapter_keywords,
        confidential_safe_mode=_option_value(args.confidential_safe_mode, profile_options.confidential_safe_mode),
        force_ocr=_option_value(args.force_ocr, profile_options.force_ocr),
        ocr_lang=args.ocr_lang,
        ocr_backend=args.ocr_backend,
        keep_page_markers=_option_value(args.keep_page_markers, profile_options.keep_page_markers),
        remove_header_footer=_option_value(args.remove_header_footer, profile_options.remove_header_footer),
        dedupe_images=_option_value(args.dedupe_images, profile_options.dedupe_images),
        repair_hyphenation=_option_value(args.repair_hyphenation, profile_options.repair_hyphenation),
        figure_crop_fallback=_option_value(args.figure_crop_fallback, profile_options.figure_crop_fallback),
        image_extraction_page_timeout_seconds=args.image_extraction_page_timeout_seconds,
        image_extraction_stage_timeout_seconds=args.image_extraction_stage_timeout_seconds,
        figure_semantics_stage_timeout_seconds=args.figure_semantics_stage_timeout_seconds,
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
        rag_figure_text_chunks=_option_value(
            args.rag_figure_text_chunks,
            profile_options.rag_figure_text_chunks,
        ),
        figure_region_ocr=_option_value(args.figure_region_ocr, profile_options.figure_region_ocr),
        rag_generated_figure_descriptions=_option_value(
            args.rag_generated_figure_descriptions,
            profile_options.rag_generated_figure_descriptions,
        ),
        figure_description_backend=_option_value(
            args.figure_description_backend,
            profile_options.figure_description_backend,
        ),
        figure_structure_extraction=_option_value(
            args.figure_structure_extraction,
            profile_options.figure_structure_extraction,
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
        and args.rag_profile in TECHNICAL_SPEC_RAG_PROFILES
        and _selected_domain_adapter(args) is DomainAdapterMode.NONE
    ):
        parser.error("technical spec RAG profiles require --domain-adapter when strict domain validation is enabled.")


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    argv_tokens = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(argv_tokens)
    configure_logging(verbose=args.verbose, debug=args.debug)

    if args.input_pdf and args.input_dir:
        parser.error("Use either input_pdf or --input-dir, not both.")
    if not args.input_pdf and not args.input_dir:
        parser.error("Provide an input PDF path or --input-dir.")
    if args.previous_corpus_manifest is not None and not args.input_dir:
        parser.error("--previous-corpus-manifest is only supported with --input-dir batch mode.")
    if args.reuse_unchanged and args.previous_corpus_manifest is None:
        parser.error("--reuse-unchanged requires --previous-corpus-manifest.")
    if args.apply_plan is not None and args.input_dir:
        parser.error("--apply-plan is only supported for single PDF conversion.")
    _apply_plan_to_args(args, parser, explicit_options=_explicit_plan_apply_options(argv_tokens))
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
    _write_plan_apply_report(config.output_dir, args._plan_apply_audit)
    return result.exit_code
