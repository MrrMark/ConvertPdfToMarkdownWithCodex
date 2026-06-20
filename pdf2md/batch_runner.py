from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pdf2md.config import Config
from pdf2md.models import (
    BatchDocumentFiles,
    BatchDocumentResult,
    BatchReport,
    BatchReportSummary,
    ConversionStatus,
    CorpusDiffEntry,
    CorpusDiffReport,
    CorpusDiffSummary,
    CorpusDocument,
    CorpusManifest,
    DomainAdapterMode,
    ImageMode,
    OutputProfile,
    RagSidecarScope,
    Manifest,
    RagTableOutputMode,
    Report,
    RequirementChangeImpactEntry,
    RequirementChangeImpactReport,
    RequirementChangeImpactSummary,
    TableMode,
)
from pdf2md.pipeline import EXIT_FATAL, EXIT_PARTIAL, ConversionResult, run_conversion
from pdf2md.rag_profiles import DEFAULT_RAG_PURPOSE_PROFILE
from pdf2md.utils.io import write_json


BatchDocumentRunner = Callable[[Config], ConversionResult]
BatchProgressCallback = Callable[["BatchDocumentEvent"], None]
BatchCancelCallback = Callable[[], bool]


@dataclass(frozen=True)
class BatchConversionOptions:
    """Options shared by CLI and GUI batch conversion paths."""

    pages: str | None = None
    password: str | None = None
    image_mode: ImageMode = ImageMode.REFERENCED
    table_mode: TableMode = TableMode.AUTO
    rag_table_output: RagTableOutputMode = RagTableOutputMode.NONE
    output_profile: OutputProfile = OutputProfile.FULL
    rag_sidecar_scope: RagSidecarScope | None = None
    rag_profile: str = DEFAULT_RAG_PURPOSE_PROFILE
    domain_adapter: DomainAdapterMode = DomainAdapterMode.NONE
    manual_domain_adapter_label: str | None = None
    manual_domain_adapter_keywords: str | None = None
    confidential_safe_mode: bool = False
    force_ocr: bool = False
    ocr_lang: str = "eng"
    ocr_backend: str = "tesseract"
    keep_page_markers: bool = False
    remove_header_footer: bool = False
    dedupe_images: bool = False
    repair_hyphenation: bool = False
    figure_crop_fallback: bool = False
    image_extraction_page_timeout_seconds: float | None = None
    image_extraction_stage_timeout_seconds: float | None = None
    figure_semantics_stage_timeout_seconds: float | None = None
    retrieval_chunk_max_tokens: int = 512
    retrieval_tokenizer: str = "char"
    rag_contextual_embedding_text: bool = False
    rag_merge_sibling_text_chunks: bool = False
    rag_chunk_relationship_metadata: bool = False
    rag_figure_text_chunks: bool = False
    figure_region_ocr: bool = False
    rag_generated_figure_descriptions: bool = False
    figure_description_backend: str = "local-vlm"
    figure_structure_extraction: bool = False
    page_workers: int = 1
    debug: bool = False
    verbose: bool = False
    skip_existing: bool = False
    previous_corpus_manifest: Path | None = None
    reuse_unchanged: bool = False


@dataclass(frozen=True)
class BatchDocumentEvent:
    """Document-level batch event for GUI progress and headless smoke evidence."""

    current: int
    total: int
    input_pdf: Path
    status: str


@dataclass(frozen=True)
class BatchRunResult:
    """Batch conversion result plus generated corpus-level artifact paths."""

    exit_code: int
    output_root: Path
    pdf_paths: list[Path]
    documents: list[BatchDocumentResult]
    batch_report: BatchReport
    corpus_manifest: CorpusManifest
    batch_report_path: Path
    corpus_manifest_path: Path
    corpus_diff_report_path: Path | None = None
    requirement_change_impact_report_path: Path | None = None


def iter_pdf_paths(input_dir: Path) -> list[Path]:
    """Return direct child PDF files in deterministic order."""
    return sorted(
        [path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"],
        key=lambda path: (path.name.lower(), path.name),
    )


def detect_duplicate_stems(pdf_paths: list[Path]) -> list[str]:
    """Return case-insensitive duplicate PDF stems that would collide in batch output."""
    stem_map: dict[str, list[str]] = {}
    for path in pdf_paths:
        stem_map.setdefault(path.stem.casefold(), []).append(path.name)
    return sorted(", ".join(sorted(names)) for names in stem_map.values() if len(names) > 1)


def batch_doc_id(pdf_path: Path, index: int, *, confidential_safe_mode: bool) -> str:
    """Return the public corpus document id for a batch input PDF."""
    return f"doc-{index:04d}" if confidential_safe_mode else pdf_path.stem


def build_batch_config(pdf_path: Path, output_root: Path, options: BatchConversionOptions) -> Config:
    """Build a per-document Config using the stable CLI batch naming contract."""
    stem = pdf_path.stem
    return Config(
        input_pdf=pdf_path,
        output_dir=output_root / stem,
        pages=options.pages,
        password=options.password,
        image_mode=options.image_mode,
        table_mode=options.table_mode,
        rag_table_output=options.rag_table_output,
        output_profile=options.output_profile,
        rag_sidecar_scope=options.rag_sidecar_scope,
        rag_profile=options.rag_profile,
        domain_adapter=options.domain_adapter,
        manual_domain_adapter_label=options.manual_domain_adapter_label,
        manual_domain_adapter_keywords=options.manual_domain_adapter_keywords,
        confidential_safe_mode=options.confidential_safe_mode,
        force_ocr=options.force_ocr,
        ocr_lang=options.ocr_lang,
        ocr_backend=options.ocr_backend,
        keep_page_markers=options.keep_page_markers,
        remove_header_footer=options.remove_header_footer,
        dedupe_images=options.dedupe_images,
        repair_hyphenation=options.repair_hyphenation,
        figure_crop_fallback=options.figure_crop_fallback,
        image_extraction_page_timeout_seconds=options.image_extraction_page_timeout_seconds,
        image_extraction_stage_timeout_seconds=options.image_extraction_stage_timeout_seconds,
        figure_semantics_stage_timeout_seconds=options.figure_semantics_stage_timeout_seconds,
        retrieval_chunk_max_tokens=options.retrieval_chunk_max_tokens,
        retrieval_tokenizer=options.retrieval_tokenizer,
        rag_contextual_embedding_text=options.rag_contextual_embedding_text,
        rag_merge_sibling_text_chunks=options.rag_merge_sibling_text_chunks,
        rag_chunk_relationship_metadata=options.rag_chunk_relationship_metadata,
        rag_figure_text_chunks=options.rag_figure_text_chunks,
        figure_region_ocr=options.figure_region_ocr,
        rag_generated_figure_descriptions=options.rag_generated_figure_descriptions,
        figure_description_backend=options.figure_description_backend,
        figure_structure_extraction=options.figure_structure_extraction,
        page_workers=options.page_workers,
        debug=options.debug,
        verbose=options.verbose,
        skip_existing=options.skip_existing,
        markdown_filename=f"{stem}.md",
        manifest_filename=f"{stem}_manifest.json",
        report_filename=f"{stem}_report.json",
        assets_dirname="assets",
    )


def batch_config_has_existing_outputs(config: Config) -> bool:
    """Return true when all core batch outputs already exist."""
    paths = _core_output_paths(config)
    return all(path is not None and Path(path).exists() for path in (paths.markdown, paths.manifest, paths.report))


def run_batch_conversion(
    *,
    input_dir: Path,
    options: BatchConversionOptions,
    output_root: Path | None = None,
    run_document: BatchDocumentRunner = run_conversion,
    progress: BatchProgressCallback | None = None,
    cancel_requested: BatchCancelCallback | None = None,
    catch_document_exceptions: bool = False,
) -> BatchRunResult:
    """Run a deterministic PDF folder conversion and write batch/corpus artifacts."""
    if not input_dir.exists() or not input_dir.is_dir():
        raise ValueError(f"Input directory does not exist or is not a directory: {input_dir}")
    pdf_paths = iter_pdf_paths(input_dir)
    if not pdf_paths:
        raise ValueError(f"No PDF files found in directory: {input_dir}")
    duplicate_stems = detect_duplicate_stems(pdf_paths)
    if duplicate_stems:
        raise ValueError(f"Duplicate PDF stems found: {'; '.join(duplicate_stems)}")

    batch_output_root = output_root if output_root is not None else input_dir / "output"
    batch_output_root.mkdir(parents=True, exist_ok=True)

    documents: list[BatchDocumentResult] = []
    success_count = 0
    partial_count = 0
    failed_count = 0
    skipped_count = 0
    final_exit_code = 0
    total = len(pdf_paths)
    previous_manifest: CorpusManifest | None = None
    previous_by_id: dict[str, CorpusDocument] = {}
    if options.reuse_unchanged and options.previous_corpus_manifest is not None:
        previous_manifest = _load_json_model(options.previous_corpus_manifest, CorpusManifest)
        previous_by_id = {document.doc_id: document for document in previous_manifest.documents}

    for index, pdf_path in enumerate(pdf_paths, start=1):
        config = build_batch_config(pdf_path, batch_output_root, options)
        if cancel_requested is not None and cancel_requested():
            final_exit_code = EXIT_PARTIAL
            for cancel_index, cancelled_path in enumerate(pdf_paths[index - 1 :], start=index):
                cancelled_config = build_batch_config(cancelled_path, batch_output_root, options)
                documents.append(_build_cancelled_batch_document(cancelled_path, cancelled_config))
                _emit_event(progress, current=cancel_index, total=total, input_pdf=cancelled_path, status="cancelled")
            break
        if options.skip_existing and batch_config_has_existing_outputs(config):
            documents.append(_build_skipped_batch_document(pdf_path, config))
            skipped_count += 1
            _emit_event(progress, current=index, total=total, input_pdf=pdf_path, status="skipped")
            continue
        if previous_manifest is not None:
            doc_id = batch_doc_id(pdf_path, index, confidential_safe_mode=options.confidential_safe_mode)
            previous_doc = previous_by_id.get(doc_id)
            if previous_doc is not None and previous_doc.source_sha256 == _file_sha256(pdf_path):
                previous_output_dir = _resolve_previous_output_dir(
                    manifest_path=options.previous_corpus_manifest,
                    manifest=previous_manifest,
                    document=previous_doc,
                )
                if (
                    previous_output_dir is not None
                    and _previous_output_has_expected_core(previous_output_dir, config)
                    and _reuse_previous_output(source_dir=previous_output_dir, target_dir=config.output_dir)
                    and batch_config_has_existing_outputs(config)
                ):
                    documents.append(_build_skipped_batch_document(pdf_path, config))
                    skipped_count += 1
                    _emit_event(progress, current=index, total=total, input_pdf=pdf_path, status="skipped")
                    continue
        _emit_event(progress, current=index, total=total, input_pdf=pdf_path, status="started")
        try:
            result = run_document(config)
        except Exception:  # noqa: BLE001
            if not catch_document_exceptions:
                raise
            failed_count += 1
            final_exit_code = EXIT_PARTIAL
            documents.append(_build_failed_batch_document(pdf_path, config))
            _emit_event(progress, current=index, total=total, input_pdf=pdf_path, status=ConversionStatus.FAILED.value)
            continue
        if result.status == ConversionStatus.FAILED:
            failed_count += 1
            final_exit_code = EXIT_PARTIAL
        elif result.status == ConversionStatus.PARTIAL_SUCCESS:
            partial_count += 1
            final_exit_code = EXIT_PARTIAL
        else:
            success_count += 1
        documents.append(_build_batch_document_result(pdf_path, config, result))
        _emit_event(progress, current=index, total=total, input_pdf=pdf_path, status=result.status.value)

    batch_report = BatchReport(
        input_dir="redacted-input-dir" if options.confidential_safe_mode else str(input_dir),
        output_dir="redacted-output-dir" if options.confidential_safe_mode else str(batch_output_root),
        pdf_files=["redacted.pdf" for _ in pdf_paths]
        if options.confidential_safe_mode
        else [str(path) for path in pdf_paths],
        documents=documents,
        summary=BatchReportSummary(
            total_documents=len(pdf_paths),
            success_count=success_count,
            partial_success_count=partial_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
        ),
    )
    batch_report_path = batch_output_root / "batch_report.json"
    write_json(batch_report_path, batch_report.model_dump(mode="json"))
    corpus_manifest = _build_corpus_manifest(
        input_dir=input_dir,
        output_dir=batch_output_root,
        pdf_paths=pdf_paths,
        documents=documents,
        confidential_safe_mode=options.confidential_safe_mode,
    )
    corpus_manifest_path = batch_output_root / "corpus_manifest.json"
    write_json(corpus_manifest_path, corpus_manifest.model_dump(mode="json"))

    corpus_diff_report_path: Path | None = None
    requirement_change_impact_report_path: Path | None = None
    if options.previous_corpus_manifest is not None:
        diff_report = _build_corpus_diff_report(
            previous_manifest_path=options.previous_corpus_manifest,
            current_manifest_path=corpus_manifest_path,
            current_manifest=corpus_manifest,
        )
        corpus_diff_report_path = batch_output_root / "corpus_diff_report.json"
        write_json(corpus_diff_report_path, diff_report.model_dump(mode="json"))
        requirement_impact_report = _build_requirement_change_impact_report(
            previous_manifest_path=options.previous_corpus_manifest,
            current_manifest_path=corpus_manifest_path,
            current_manifest=corpus_manifest,
        )
        requirement_change_impact_report_path = batch_output_root / "requirement_change_impact_report.json"
        write_json(requirement_change_impact_report_path, requirement_impact_report.model_dump(mode="json"))

    return BatchRunResult(
        exit_code=final_exit_code,
        output_root=batch_output_root,
        pdf_paths=pdf_paths,
        documents=documents,
        batch_report=batch_report,
        corpus_manifest=corpus_manifest,
        batch_report_path=batch_report_path,
        corpus_manifest_path=corpus_manifest_path,
        corpus_diff_report_path=corpus_diff_report_path,
        requirement_change_impact_report_path=requirement_change_impact_report_path,
    )


def build_requirement_change_impact_report(
    *,
    previous_manifest_path: Path,
    current_manifest_path: Path,
    current_manifest: CorpusManifest,
) -> RequirementChangeImpactReport:
    """Build the corpus requirement impact report used by batch incremental outputs."""
    return _build_requirement_change_impact_report(
        previous_manifest_path=previous_manifest_path,
        current_manifest_path=current_manifest_path,
        current_manifest=current_manifest,
    )


def _emit_event(
    progress: BatchProgressCallback | None,
    *,
    current: int,
    total: int,
    input_pdf: Path,
    status: str,
) -> None:
    if progress is not None:
        progress(BatchDocumentEvent(current=current, total=total, input_pdf=input_pdf, status=status))


def _core_output_paths(config: Config) -> BatchDocumentFiles:
    return BatchDocumentFiles(
        markdown=str(config.output_dir / config.markdown_filename),
        manifest=str(config.output_dir / config.manifest_filename),
        report=str(config.output_dir / config.report_filename),
    )


def _public_path(path: Path, *, confidential_safe_mode: bool) -> str:
    return path.name if confidential_safe_mode else str(path)


def _document_files(
    config: Config,
    *,
    markdown_path: Path | None = None,
    manifest_path: Path | None = None,
    report_path: Path | None = None,
    include_expected_core: bool = False,
) -> BatchDocumentFiles:
    markdown = markdown_path or (config.output_dir / config.markdown_filename if include_expected_core else None)
    manifest = manifest_path or (config.output_dir / config.manifest_filename if include_expected_core else None)
    report = report_path or (config.output_dir / config.report_filename if include_expected_core else None)

    files = BatchDocumentFiles(
        markdown=_public_path(markdown, confidential_safe_mode=config.confidential_safe_mode)
        if markdown is not None
        else None,
        manifest=_public_path(manifest, confidential_safe_mode=config.confidential_safe_mode)
        if manifest is not None
        else None,
        report=_public_path(report, confidential_safe_mode=config.confidential_safe_mode) if report is not None else None,
    )
    sidecar_fields = {
        "text_blocks_rag": config.output_dir / config.rag_text_blocks_jsonl_filename,
        "semantic_units_rag": config.output_dir / config.semantic_units_jsonl_filename,
        "requirements_rag": config.output_dir / config.requirements_jsonl_filename,
        "cross_refs_rag": config.output_dir / config.cross_refs_jsonl_filename,
        "retrieval_chunks_rag": config.output_dir / config.retrieval_chunks_jsonl_filename,
        "page_layout_rag": config.output_dir / config.page_layout_jsonl_filename,
        "figures_rag": config.output_dir / config.figures_rag_jsonl_filename,
        "figure_ocr_evidence_rag": config.output_dir / config.figure_ocr_evidence_jsonl_filename,
        "figure_descriptions_rag": config.output_dir / config.figure_descriptions_jsonl_filename,
        "figure_structures_rag": config.output_dir / config.figure_structures_jsonl_filename,
        "domain_units_rag": config.output_dir / config.domain_units_jsonl_filename,
        "requirement_traceability_rag": config.output_dir / config.requirement_traceability_jsonl_filename,
        "technical_tables_rag": config.output_dir / config.technical_tables_jsonl_filename,
        "rag_tables_markdown": config.output_dir / config.rag_tables_markdown_filename,
        "tables_rag_jsonl": config.output_dir / config.rag_tables_jsonl_filename,
        "sanitized_report": config.output_dir / config.sanitized_report_filename,
    }
    for field_name, path in sidecar_fields.items():
        if path.exists():
            setattr(files, field_name, _public_path(path, confidential_safe_mode=config.confidential_safe_mode))
    return files


def _load_json_model(path: Path, model_cls):
    return model_cls.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _build_skipped_batch_document(pdf_path: Path, config: Config) -> BatchDocumentResult:
    actual_files = _core_output_paths(config)
    files = _document_files(config, include_expected_core=True)
    report = _load_json_model(Path(actual_files.report or ""), Report)
    manifest = _load_json_model(Path(actual_files.manifest or ""), Manifest)
    return BatchDocumentResult(
        input_pdf="redacted.pdf" if config.confidential_safe_mode else str(pdf_path),
        status="skipped",
        exit_code=0,
        output_dir=config.output_dir.name if config.confidential_safe_mode else str(config.output_dir),
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


def _build_cancelled_batch_document(pdf_path: Path, config: Config) -> BatchDocumentResult:
    return BatchDocumentResult(
        input_pdf="redacted.pdf" if config.confidential_safe_mode else str(pdf_path),
        status="cancelled",
        exit_code=EXIT_PARTIAL,
        output_dir=config.output_dir.name if config.confidential_safe_mode else str(config.output_dir),
        skipped=False,
        files=_document_files(config, include_expected_core=True),
    )


def _build_failed_batch_document(pdf_path: Path, config: Config) -> BatchDocumentResult:
    return BatchDocumentResult(
        input_pdf="redacted.pdf" if config.confidential_safe_mode else str(pdf_path),
        status=ConversionStatus.FAILED.value,
        exit_code=EXIT_FATAL,
        output_dir=config.output_dir.name if config.confidential_safe_mode else str(config.output_dir),
        skipped=False,
        files=_document_files(config, include_expected_core=True),
    )


def _build_batch_document_result(pdf_path: Path, config: Config, result: ConversionResult) -> BatchDocumentResult:
    report = result.report
    manifest_path = config.output_dir / config.manifest_filename
    manifest = _load_json_model(manifest_path, Manifest) if manifest_path.exists() else None
    return BatchDocumentResult(
        input_pdf="redacted.pdf" if config.confidential_safe_mode else str(pdf_path),
        status=result.status.value,
        exit_code=result.exit_code,
        output_dir=config.output_dir.name if config.confidential_safe_mode else str(config.output_dir),
        started_at=report.started_at if report is not None else None,
        finished_at=report.finished_at if report is not None else None,
        duration_ms=report.duration_ms if report is not None else 0,
        warning_count=len(report.warnings) if report is not None else len(result.warnings),
        table_count=len(manifest.tables) if manifest is not None else 0,
        image_count=len(manifest.images) if manifest is not None else 0,
        used_ocr=bool(report.engine_usage.get("ocr", False)) if report is not None else False,
        skipped=False,
        files=_document_files(
            config,
            markdown_path=result.markdown_path,
            manifest_path=result.manifest_path,
            report_path=result.report_path,
        ),
    )


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _build_corpus_manifest(
    *,
    input_dir: Path,
    output_dir: Path,
    pdf_paths: list[Path],
    documents: list[BatchDocumentResult],
    confidential_safe_mode: bool = False,
) -> CorpusManifest:
    corpus_documents: list[CorpusDocument] = []
    for idx, document in enumerate(documents, start=1):
        pdf_path = pdf_paths[idx - 1]
        actual_manifest = output_dir / pdf_path.stem / f"{pdf_path.stem}_manifest.json"
        selected_pages = []
        if actual_manifest.exists():
            try:
                selected_pages = list(_load_json_model(actual_manifest, Manifest).selected_pages)
            except Exception:  # noqa: BLE001
                selected_pages = []
        corpus_documents.append(
            CorpusDocument(
                doc_id=batch_doc_id(pdf_path, idx, confidential_safe_mode=confidential_safe_mode),
                input_pdf="redacted.pdf" if confidential_safe_mode else str(pdf_path),
                source_sha256=_file_sha256(pdf_path) if pdf_path.exists() else "",
                output_dir=document.output_dir if not confidential_safe_mode else f"doc-{idx:04d}",
                status=document.status,
                selected_pages=selected_pages,
                skipped=document.skipped,
                files=document.files,
            )
        )
    return CorpusManifest(
        input_dir="redacted-input-dir" if confidential_safe_mode else str(input_dir),
        output_dir="redacted-output-dir" if confidential_safe_mode else str(output_dir),
        documents=corpus_documents,
    )


def _build_corpus_diff_report(
    *,
    previous_manifest_path: Path,
    current_manifest_path: Path,
    current_manifest: CorpusManifest,
) -> CorpusDiffReport:
    previous = _load_json_model(previous_manifest_path, CorpusManifest)
    previous_by_id = {document.doc_id: document for document in previous.documents}
    current_by_id = {document.doc_id: document for document in current_manifest.documents}
    entries: list[CorpusDiffEntry] = []

    for doc_id in sorted(current_by_id):
        current = current_by_id[doc_id]
        previous_doc = previous_by_id.get(doc_id)
        if previous_doc is None:
            status = "added"
            previous_hash = None
            previous_output = None
        elif previous_doc.source_sha256 == current.source_sha256:
            status = "unchanged"
            previous_hash = previous_doc.source_sha256
            previous_output = previous_doc.output_dir
        else:
            status = "changed"
            previous_hash = previous_doc.source_sha256
            previous_output = previous_doc.output_dir
        entries.append(
            CorpusDiffEntry(
                doc_id=doc_id,
                status=status,
                previous_source_sha256=previous_hash,
                current_source_sha256=current.source_sha256,
                previous_output_dir=previous_output,
                current_output_dir=current.output_dir,
            )
        )

    for doc_id in sorted(set(previous_by_id) - set(current_by_id)):
        previous_doc = previous_by_id[doc_id]
        entries.append(
            CorpusDiffEntry(
                doc_id=doc_id,
                status="removed",
                previous_source_sha256=previous_doc.source_sha256,
                current_source_sha256=None,
                previous_output_dir=previous_doc.output_dir,
                current_output_dir=None,
            )
        )

    return CorpusDiffReport(
        previous_manifest=str(previous_manifest_path),
        current_manifest=str(current_manifest_path),
        entries=entries,
        summary=CorpusDiffSummary(
            changed_count=sum(1 for entry in entries if entry.status == "changed"),
            unchanged_count=sum(1 for entry in entries if entry.status == "unchanged"),
            removed_count=sum(1 for entry in entries if entry.status == "removed"),
            added_count=sum(1 for entry in entries if entry.status == "added"),
        ),
    )


def _read_jsonl_records(path: Path) -> list[dict]:
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _path_candidates(
    path_text: str,
    *,
    manifest_path: Path,
    manifest: CorpusManifest,
    document: CorpusDocument,
) -> list[Path]:
    raw = Path(path_text)
    if raw.is_absolute():
        return [raw]

    candidates = [raw, manifest_path.parent / raw]
    output_root = Path(manifest.output_dir)
    document_output = Path(document.output_dir)
    if output_root.is_absolute():
        candidates.extend([output_root / raw, output_root / document.doc_id / raw.name])
    else:
        candidates.extend(
            [
                manifest_path.parent / output_root / raw,
                manifest_path.parent / output_root / document.doc_id / raw.name,
            ]
        )
    if document_output.is_absolute():
        candidates.append(document_output / raw.name)
    else:
        candidates.append(manifest_path.parent / document_output / raw.name)
    return candidates


def _resolve_requirement_traceability_path(
    *,
    manifest_path: Path,
    manifest: CorpusManifest,
    document: CorpusDocument,
) -> Path | None:
    path_text = document.files.requirement_traceability_rag
    if not path_text:
        return None
    seen: set[Path] = set()
    for candidate in _path_candidates(path_text, manifest_path=manifest_path, manifest=manifest, document=document):
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _resolve_previous_output_dir(
    *,
    manifest_path: Path,
    manifest: CorpusManifest,
    document: CorpusDocument,
) -> Path | None:
    candidates: list[Path] = []
    raw = Path(document.output_dir)
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append(manifest_path.parent / raw)
        output_root = Path(manifest.output_dir)
        if output_root.is_absolute():
            candidates.append(output_root / document.doc_id)
        else:
            candidates.append(manifest_path.parent / output_root / document.doc_id)
    if document.files.manifest:
        candidates.extend(
            candidate.parent
            for candidate in _path_candidates(
                document.files.manifest,
                manifest_path=manifest_path,
                manifest=manifest,
                document=document,
            )
        )
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def _output_dir_is_empty_or_missing(path: Path) -> bool:
    return not path.exists() or not any(path.iterdir())


def _reuse_previous_output(
    *,
    source_dir: Path,
    target_dir: Path,
) -> bool:
    if source_dir.resolve() == target_dir.resolve():
        return True
    if not _output_dir_is_empty_or_missing(target_dir):
        return False
    shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
    return True


def _previous_output_has_expected_core(source_dir: Path, config: Config) -> bool:
    return all(
        (source_dir / filename).exists()
        for filename in (config.markdown_filename, config.manifest_filename, config.report_filename)
    )


def _source_id_fallback(record: dict) -> str | None:
    for ref in record.get("source_refs") or []:
        if isinstance(ref, dict) and ref.get("source_id"):
            return str(ref["source_id"])
    return None


def _requirement_key(record: dict) -> tuple[str, str | None]:
    requirement_id = str(record.get("requirement_id") or "").strip() or None
    if requirement_id:
        return requirement_id, requirement_id
    fallback = _source_id_fallback(record) or str(record.get("trace_id") or "").strip()
    return f"unidentified:{fallback or 'unknown'}", None


def _stable_json_key(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _append_unique(target: list, value: object) -> None:
    if value is None or value == "":
        return
    key = _stable_json_key(value)
    if all(_stable_json_key(existing) != key for existing in target):
        target.append(value)


def _aggregate_requirement_records(records: list[dict]) -> dict[str, dict]:
    grouped: dict[str, dict] = {}
    sorted_records = sorted(records, key=lambda item: int(item.get("trace_index") or 0))
    for record in sorted_records:
        key, requirement_id = _requirement_key(record)
        aggregate = grouped.setdefault(
            key,
            {
                "requirement_key": key,
                "requirement_id": requirement_id,
                "trace_ids": [],
                "texts": [],
                "source_refs": [],
                "normative_strengths": [],
                "testability_hints": [],
            },
        )
        if aggregate["requirement_id"] is None and requirement_id is not None:
            aggregate["requirement_id"] = requirement_id
        _append_unique(aggregate["trace_ids"], str(record.get("trace_id") or ""))
        _append_unique(aggregate["texts"], str(record.get("text") or ""))
        for ref in record.get("source_refs") or []:
            if isinstance(ref, dict):
                _append_unique(aggregate["source_refs"], ref)
        _append_unique(aggregate["normative_strengths"], str(record.get("normative_strength") or ""))
        _append_unique(aggregate["testability_hints"], str(record.get("testability_hint") or ""))
    for aggregate in grouped.values():
        aggregate["source_refs"] = sorted(aggregate["source_refs"], key=_stable_json_key)
    return grouped


def _changed_requirement_fields(previous: dict, current: dict) -> list[str]:
    changed_fields: list[str] = []
    for field in ("texts", "source_refs", "normative_strengths", "testability_hints"):
        if previous.get(field) != current.get(field):
            changed_fields.append(field)
    return changed_fields


def _requirement_change_entry(
    *,
    doc_id: str,
    status: str,
    requirement_key: str,
    previous: dict | None,
    current: dict | None,
    changed_fields: list[str],
) -> RequirementChangeImpactEntry:
    previous = previous or {}
    current = current or {}
    return RequirementChangeImpactEntry(
        doc_id=doc_id,
        requirement_key=requirement_key,
        requirement_id=current.get("requirement_id") or previous.get("requirement_id"),
        status=status,
        changed_fields=changed_fields,
        previous_trace_ids=list(previous.get("trace_ids") or []),
        current_trace_ids=list(current.get("trace_ids") or []),
        previous_texts=list(previous.get("texts") or []),
        current_texts=list(current.get("texts") or []),
        previous_source_refs=list(previous.get("source_refs") or []),
        current_source_refs=list(current.get("source_refs") or []),
        previous_normative_strengths=list(previous.get("normative_strengths") or []),
        current_normative_strengths=list(current.get("normative_strengths") or []),
        previous_testability_hints=list(previous.get("testability_hints") or []),
        current_testability_hints=list(current.get("testability_hints") or []),
    )


def _load_requirement_trace_records(
    *,
    manifest_path: Path,
    manifest: CorpusManifest,
    document: CorpusDocument | None,
) -> list[dict]:
    if document is None:
        return []
    path = _resolve_requirement_traceability_path(
        manifest_path=manifest_path,
        manifest=manifest,
        document=document,
    )
    if path is None:
        return []
    return _read_jsonl_records(path)


def _build_requirement_change_impact_report(
    *,
    previous_manifest_path: Path,
    current_manifest_path: Path,
    current_manifest: CorpusManifest,
) -> RequirementChangeImpactReport:
    previous_manifest = _load_json_model(previous_manifest_path, CorpusManifest)
    previous_by_id = {document.doc_id: document for document in previous_manifest.documents}
    current_by_id = {document.doc_id: document for document in current_manifest.documents}
    entries: list[RequirementChangeImpactEntry] = []
    changed_count = 0
    removed_count = 0
    added_count = 0
    unchanged_count = 0

    for doc_id in sorted(set(previous_by_id) | set(current_by_id)):
        previous_records = _aggregate_requirement_records(
            _load_requirement_trace_records(
                manifest_path=previous_manifest_path,
                manifest=previous_manifest,
                document=previous_by_id.get(doc_id),
            )
        )
        current_records = _aggregate_requirement_records(
            _load_requirement_trace_records(
                manifest_path=current_manifest_path,
                manifest=current_manifest,
                document=current_by_id.get(doc_id),
            )
        )
        for requirement_key in sorted(set(previous_records) | set(current_records)):
            previous = previous_records.get(requirement_key)
            current = current_records.get(requirement_key)
            if previous is None:
                added_count += 1
                entries.append(
                    _requirement_change_entry(
                        doc_id=doc_id,
                        status="added",
                        requirement_key=requirement_key,
                        previous=None,
                        current=current,
                        changed_fields=["texts", "source_refs"],
                    )
                )
                continue
            if current is None:
                removed_count += 1
                entries.append(
                    _requirement_change_entry(
                        doc_id=doc_id,
                        status="removed",
                        requirement_key=requirement_key,
                        previous=previous,
                        current=None,
                        changed_fields=["texts", "source_refs"],
                    )
                )
                continue
            changed_fields = _changed_requirement_fields(previous, current)
            if changed_fields:
                changed_count += 1
                entries.append(
                    _requirement_change_entry(
                        doc_id=doc_id,
                        status="changed",
                        requirement_key=requirement_key,
                        previous=previous,
                        current=current,
                        changed_fields=changed_fields,
                    )
                )
            else:
                unchanged_count += 1

    return RequirementChangeImpactReport(
        previous_manifest=str(previous_manifest_path),
        current_manifest=str(current_manifest_path),
        entries=entries,
        summary=RequirementChangeImpactSummary(
            changed_count=changed_count,
            removed_count=removed_count,
            added_count=added_count,
            unchanged_count=unchanged_count,
            documents_compared=len(set(previous_by_id) | set(current_by_id)),
            documents_with_requirement_changes=len({entry.doc_id for entry in entries}),
        ),
    )
