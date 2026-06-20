from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import logging
import time
from pathlib import Path
from typing import Callable, Literal, Optional

from pdf2md.config import Config
from pdf2md.constants import WarningCode
from pdf2md.document_ir import build_pdf2md_document_ir, ir_text_block_records, ir_text_blocks_by_page
from pdf2md.extractors.header_footer import remove_repeated_header_footer
from pdf2md.extractors.images import ImageExtractionProgressEvent, ImageExtractionResult, extract_images
from pdf2md.extractors.ocr import (
    OCR_LOW_CONFIDENCE_MEAN_THRESHOLD,
    OCR_LOW_CONFIDENCE_TOKEN_RATIO_THRESHOLD,
    run_ocr,
)
from pdf2md.extractors.page_worker import PageWorkerInput
from pdf2md.extractors.structure_normalizer import BlockRegion, normalize_page_lines
from pdf2md.extractors.tables import PageTableCandidateResult, extract_tables
from pdf2md.extractors.text import PageLayoutMetadata, TextExtractionError, TextLine, extract_page_text_layout_result
from pdf2md.models import (
    ConversionState,
    ConversionStatus,
    DomainAdapterMode,
    ImageMode,
    InterruptedConversionReport,
    Manifest,
    NormalizedLine,
    OutputProfile,
    PageResult,
    PageStatus,
    RagSidecarScope,
    RagTableOutputMode,
    Report,
    TableMode,
    WarningEntry,
)
from pdf2md.output_writers import (
    write_debug_artifacts,
    write_domain_unit_output,
    write_figure_description_output,
    write_figure_ocr_evidence_output,
    write_figure_rag_output,
    write_figure_structure_output,
    write_page_layout_output,
    write_rag_table_outputs,
    write_rag_text_block_output,
    write_requirement_traceability_output,
    write_retrieval_chunk_output,
    write_semantic_layer_outputs,
    write_technical_table_output,
)
from pdf2md.reporting import build_report, count_structure_marker_reasons, determine_conversion_status, finalize_page_statuses
from pdf2md.rag_profiles import TECHNICAL_SPEC_RAG_PROFILES
from pdf2md.serializers.manifest import serialize_manifest
from pdf2md.serializers.markdown import serialize_markdown_blocks_result
from pdf2md.serializers.rag_chunks import (
    build_retrieval_chunk_diagnostics,
    build_retrieval_chunks,
    make_token_counter,
)
from pdf2md.serializers.rag_domain_adapters import build_domain_units
from pdf2md.serializers.rag_figure_semantics import (
    augment_figure_records_with_region_ocr,
    build_figure_description_records,
    build_figure_structure_records,
)
from pdf2md.serializers.rag_figures import build_figure_records
from pdf2md.serializers.rag_layout import build_page_layout_records
from pdf2md.serializers.rag_ocr_evidence import build_region_ocr_evidence_records
from pdf2md.serializers.rag_requirements import build_requirement_traceability_records
from pdf2md.serializers.rag_tables import (
    annotate_rag_tables_with_heading_context,
    normalize_rag_table_payload,
)
from pdf2md.serializers.rag_semantics import (
    build_semantic_layer,
    extract_pdf_outline_reference_targets,
)
from pdf2md.serializers.rag_text_blocks import build_text_blocks
from pdf2md.serializers.rag_technical_tables import build_technical_table_records
from pdf2md.serializers.report import serialize_report
from pdf2md.table_quality import (
    build_table_quality_review_pack,
    count_actionable_low_quality_tables,
    count_caption_linked_tables,
    count_low_quality_tables,
    count_table_fallback_reasons,
    summarize_table_confidence_v2,
    low_quality_table_pages,
)
from pdf2md.utils.io import ensure_output_dirs, write_json, write_text
from pdf2md.utils.page_executor import effective_page_worker_count, run_page_workers
from pdf2md.utils.pdf import PdfDocumentContext, PdfOpenError


EXIT_SUCCESS = 0
EXIT_FATAL = 1
EXIT_PARTIAL = 2
logger = logging.getLogger(__name__)

SIDECAR_OMITTED_REASON = "rag_sidecar_scope_omitted"


@dataclass
class ConversionResult:
    exit_code: int
    markdown_path: Optional[Path]
    manifest_path: Optional[Path]
    report_path: Optional[Path]
    warnings: list[WarningEntry]
    status: ConversionStatus
    report: Report | None = None


@dataclass(frozen=True)
class ConversionProgressEvent:
    """Observer-only conversion progress event emitted without affecting output determinism."""

    current: int
    total: int
    page: int | None
    status: Literal[
        "pages_selected",
        "page_started",
        "page_finished",
        "image_extraction_page_started",
        "image_extraction_page_finished",
        "image_extraction_page_skipped",
        "image_extraction_stage_timeout",
    ]
    stage: str
    image_count: int | None = None
    elapsed_ms: int | None = None
    timeout_reason: str | None = None


ConversionProgressCallback = Callable[[ConversionProgressEvent], None]


class ConversionJournal:
    """Write a deterministic conversion state journal without changing conversion output semantics."""

    def __init__(self, config: Config, *, started_at: datetime) -> None:
        self.config = config
        self.started_at = started_at
        self.current_stage: str | None = "starting"
        self.current_page: int | None = None
        self.selected_pages: list[int] = []
        self.completed_pages: set[int] = set()
        self.failed_pages: set[int] = set()
        self.skipped_pages: set[int] = set()
        self.stage_durations_ms: dict[str, int] = {}
        self.last_warning_code: str | None = None
        self.resume_hint = (
            "Partial artifacts were left in place. Re-run the conversion with the same input/options, "
            "or resume from the last completed page if using a page-window workflow."
        )

    @property
    def state_path(self) -> Path:
        return self.config.output_dir / self.config.conversion_state_filename

    @property
    def interrupted_report_path(self) -> Path:
        return self.config.output_dir / self.config.interrupted_report_filename

    def set_stage(self, stage: str, *, page: int | None = None, warnings: list[WarningEntry] | None = None) -> None:
        self.current_stage = stage
        self.current_page = page
        self.remember_warnings(warnings or [])
        self.write_state()

    def set_selected_pages(self, selected_pages: list[int]) -> None:
        self.selected_pages = list(selected_pages)
        self.write_state()

    def remember_warnings(self, warnings: list[WarningEntry]) -> None:
        if warnings:
            self.last_warning_code = warnings[-1].code

    def finish_stage(self, stage: str, stage_durations_ms: dict[str, int]) -> None:
        self.current_stage = stage
        self.stage_durations_ms = dict(sorted(stage_durations_ms.items()))
        self.write_state()

    def handle_progress(self, event: ConversionProgressEvent) -> None:
        self.current_stage = event.stage
        self.current_page = event.page
        if event.status == "page_finished" and event.page is not None:
            self.completed_pages.add(event.page)
        if event.status == "image_extraction_page_skipped" and event.page is not None:
            self.skipped_pages.add(event.page)
        self.write_state()

    def mark_finished(self, result: ConversionResult) -> None:
        self.current_stage = "completed"
        self.current_page = None
        self.remember_warnings(result.warnings)
        if result.report is not None:
            self.failed_pages.update(result.report.failed_pages)
        self.write_state(status=result.status.value)

    def mark_failure(self, warning: WarningEntry) -> None:
        self.last_warning_code = warning.code
        if self.current_page is not None and self.current_page not in self.completed_pages:
            self.failed_pages.add(self.current_page)

    def last_completed_page(self) -> int | None:
        if not self.completed_pages:
            return None
        return max(self.completed_pages)

    def artifacts_written(self) -> list[str]:
        if not self.config.output_dir.exists():
            return []
        artifacts: list[str] = []
        for path in self.config.output_dir.rglob("*"):
            if not path.is_file():
                continue
            artifacts.append(path.relative_to(self.config.output_dir).as_posix())
        return sorted(artifacts)

    def interrupted_summary_extras(self) -> dict[str, object]:
        return {
            "interrupted": True,
            "interrupted_stage": self.current_stage,
            "interrupted_page": self.current_page,
            "last_completed_page": self.last_completed_page(),
            "artifacts_written": self.artifacts_written(),
            "resume_hint": self.resume_hint,
        }

    def write_state(self, *, status: str = "running") -> None:
        now = datetime.now(timezone.utc)
        payload = ConversionState(
            input_file=self._public_input_file(),
            output_dir=self._public_output_dir(),
            started_at=self.started_at,
            updated_at=now,
            elapsed_ms=max(int((now - self.started_at).total_seconds() * 1000), 0),
            status=status,
            current_stage=self.current_stage,
            current_page=self.current_page,
            selected_pages=self.selected_pages,
            completed_pages=sorted(self.completed_pages),
            failed_pages=sorted(self.failed_pages),
            skipped_pages=sorted(self.skipped_pages),
            artifacts_written=self.artifacts_written(),
            stage_durations_ms=dict(sorted(self.stage_durations_ms.items())),
            last_warning_code=self.last_warning_code,
        )
        try:
            write_json(self.state_path, payload.model_dump(mode="json"))
        except Exception:  # noqa: BLE001
            logger.exception("Failed to write conversion state journal")

    def write_interrupted_report(
        self,
        *,
        status: str,
        warning: WarningEntry,
        exc: BaseException,
    ) -> InterruptedConversionReport:
        now = datetime.now(timezone.utc)
        self.mark_failure(warning)
        report = InterruptedConversionReport(
            input_file=self._public_input_file(),
            output_dir=self._public_output_dir(),
            started_at=self.started_at,
            interrupted_at=now,
            elapsed_ms=max(int((now - self.started_at).total_seconds() * 1000), 0),
            status=status,
            interrupted_stage=self.current_stage,
            interrupted_page=self.current_page,
            last_completed_page=self.last_completed_page(),
            selected_pages=self.selected_pages,
            completed_pages=sorted(self.completed_pages),
            failed_pages=sorted(self.failed_pages),
            skipped_pages=sorted(self.skipped_pages),
            artifacts_written=self.artifacts_written(),
            stage_durations_ms=dict(sorted(self.stage_durations_ms.items())),
            last_warning_code=self.last_warning_code,
            exception_type=type(exc).__name__,
            message=str(exc),
            resume_hint=self.resume_hint,
            warnings=[warning],
        )
        write_json(self.interrupted_report_path, report.model_dump(mode="json"))
        return report

    def _public_input_file(self) -> str:
        return "redacted.pdf" if self.config.confidential_safe_mode else self.config.input_pdf.name

    def _public_output_dir(self) -> str:
        return "redacted-output-dir" if self.config.confidential_safe_mode else str(self.config.output_dir)


def _emit_progress(progress: ConversionProgressCallback | None, event: ConversionProgressEvent) -> None:
    if progress is not None:
        progress(event)


def _forward_image_progress(
    progress: ConversionProgressCallback | None,
) -> Callable[[ImageExtractionProgressEvent], None] | None:
    if progress is None:
        return None

    def handle_image_progress(event: ImageExtractionProgressEvent) -> None:
        _emit_progress(
            progress,
            ConversionProgressEvent(
                current=event.current,
                total=event.total,
                page=event.page,
                status=event.status,  # type: ignore[arg-type]
                stage="image_extraction",
                image_count=event.image_count,
                elapsed_ms=event.elapsed_ms,
                timeout_reason=event.timeout_reason,
            ),
        )

    return handle_image_progress


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _output_profile(config: Config) -> OutputProfile:
    return config.output_profile if isinstance(config.output_profile, OutputProfile) else OutputProfile(config.output_profile)


def _effective_rag_sidecar_scope(config: Config, output_profile: OutputProfile) -> RagSidecarScope:
    if config.rag_sidecar_scope is not None:
        return (
            config.rag_sidecar_scope
            if isinstance(config.rag_sidecar_scope, RagSidecarScope)
            else RagSidecarScope(config.rag_sidecar_scope)
        )
    if output_profile is OutputProfile.FAST:
        return RagSidecarScope.NONE
    return RagSidecarScope.FULL


def _requested_rag_table_sidecars(config: Config, rag_table_output: RagTableOutputMode) -> set[str]:
    outputs: set[str] = set()
    if rag_table_output.writes_markdown():
        outputs.add(config.rag_tables_markdown_filename)
    if rag_table_output.writes_jsonl():
        outputs.add(config.rag_tables_jsonl_filename)
    return outputs


def _expected_full_rag_sidecars(
    config: Config,
    *,
    rag_table_output: RagTableOutputMode,
    domain_adapter: DomainAdapterMode,
    include_figure_provenance: bool,
    include_figure_ocr_evidence: bool,
    include_figure_descriptions: bool,
    include_figure_structures: bool,
    include_page_layout: bool,
) -> set[str]:
    outputs = {
        config.rag_text_blocks_jsonl_filename,
        config.semantic_units_jsonl_filename,
        config.requirements_jsonl_filename,
        config.cross_refs_jsonl_filename,
        config.requirement_traceability_jsonl_filename,
        config.technical_tables_jsonl_filename,
        config.retrieval_chunks_jsonl_filename,
    }
    if include_page_layout:
        outputs.add(config.page_layout_jsonl_filename)
    outputs.update(_requested_rag_table_sidecars(config, rag_table_output))
    if include_figure_provenance:
        outputs.add(config.figures_rag_jsonl_filename)
    if include_figure_ocr_evidence:
        outputs.add(config.figure_ocr_evidence_jsonl_filename)
    if domain_adapter is not DomainAdapterMode.NONE:
        outputs.add(config.domain_units_jsonl_filename)
    if include_figure_descriptions:
        outputs.add(config.figure_descriptions_jsonl_filename)
    if include_figure_structures:
        outputs.add(config.figure_structures_jsonl_filename)
    return outputs


def _expected_minimal_rag_sidecars(
    config: Config,
    *,
    rag_table_output: RagTableOutputMode,
    include_figure_text_chunks: bool,
    include_figure_descriptions: bool,
    include_figure_structures: bool,
) -> set[str]:
    outputs = {config.rag_text_blocks_jsonl_filename, config.retrieval_chunks_jsonl_filename}
    outputs.update(_requested_rag_table_sidecars(config, rag_table_output))
    if include_figure_text_chunks or include_figure_descriptions or include_figure_structures:
        outputs.add(config.figures_rag_jsonl_filename)
    if include_figure_descriptions:
        outputs.add(config.figure_descriptions_jsonl_filename)
    if include_figure_structures:
        outputs.add(config.figure_structures_jsonl_filename)
    return outputs


def _written_rag_sidecars_for_scope(
    config: Config,
    *,
    scope: RagSidecarScope,
    rag_table_output: RagTableOutputMode,
    domain_adapter: DomainAdapterMode,
    include_figure_provenance: bool,
    include_figure_text_chunks: bool,
    include_figure_ocr_evidence: bool,
    include_figure_descriptions: bool,
    include_figure_structures: bool,
    include_page_layout: bool,
) -> set[str]:
    if scope is RagSidecarScope.FULL:
        return _expected_full_rag_sidecars(
            config,
            rag_table_output=rag_table_output,
            domain_adapter=domain_adapter,
            include_figure_provenance=include_figure_provenance,
            include_figure_ocr_evidence=include_figure_ocr_evidence,
            include_figure_descriptions=include_figure_descriptions,
            include_figure_structures=include_figure_structures,
            include_page_layout=include_page_layout,
        )
    if scope is RagSidecarScope.MINIMAL:
        return _expected_minimal_rag_sidecars(
            config,
            rag_table_output=rag_table_output,
            include_figure_text_chunks=include_figure_text_chunks,
            include_figure_descriptions=include_figure_descriptions,
            include_figure_structures=include_figure_structures,
        )
    return set()


def _omitted_rag_sidecars(
    config: Config,
    *,
    scope: RagSidecarScope,
    rag_table_output: RagTableOutputMode,
    domain_adapter: DomainAdapterMode,
    include_figure_provenance: bool,
    include_figure_text_chunks: bool,
    include_figure_ocr_evidence: bool,
    include_figure_descriptions: bool,
    include_figure_structures: bool,
    include_page_layout: bool,
) -> list[str]:
    expected_full = _expected_full_rag_sidecars(
        config,
        rag_table_output=rag_table_output,
        domain_adapter=domain_adapter,
        include_figure_provenance=include_figure_provenance,
        include_figure_ocr_evidence=include_figure_ocr_evidence,
        include_figure_descriptions=include_figure_descriptions,
        include_figure_structures=include_figure_structures,
        include_page_layout=include_page_layout,
    )
    written = _written_rag_sidecars_for_scope(
        config,
        scope=scope,
        rag_table_output=rag_table_output,
        domain_adapter=domain_adapter,
        include_figure_provenance=include_figure_provenance,
        include_figure_text_chunks=include_figure_text_chunks,
        include_figure_ocr_evidence=include_figure_ocr_evidence,
        include_figure_descriptions=include_figure_descriptions,
        include_figure_structures=include_figure_structures,
        include_page_layout=include_page_layout,
    )
    return sorted(expected_full - written)


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


def _annotate_ocr_warning_context(
    warnings: list[WarningEntry],
    page_results: dict[int, PageResult],
    page_image_boxes: dict[int, list[object]] | None,
) -> None:
    for warning in warnings:
        if warning.code != WarningCode.OCR_EMPTY_RESULT or warning.page is None:
            continue
        page_result = page_results.get(warning.page)
        if page_result is not None:
            warning.details.setdefault("text_layer_char_count", page_result.text_layer_char_count)
            warning.details.setdefault("existing_text_char_count", page_result.text_layer_char_count)
        if page_image_boxes is not None:
            warning.details.setdefault("page_image_count", len(page_image_boxes.get(warning.page, [])))


def _technical_profile_domain_adapter_missing(config: Config, domain_adapter: DomainAdapterMode) -> bool:
    return config.rag_profile in TECHNICAL_SPEC_RAG_PROFILES and domain_adapter is DomainAdapterMode.NONE


def _technical_profile_domain_adapter_warning(config: Config, domain_adapter: DomainAdapterMode) -> WarningEntry:
    return WarningEntry(
        code=WarningCode.TECHNICAL_PROFILE_DOMAIN_ADAPTER_MISSING,
        message=(
            "technical spec RAG profile was selected without a domain adapter; "
            "domain_units_rag.jsonl and domain_unit retrieval chunks will not be generated."
        ),
        details={
            "rag_profile": config.rag_profile,
            "domain_adapter": domain_adapter.value,
            "recommended_domain_adapters": ["nvme", "pcie", "ocp", "tcg", "spdm", "customer-requirements", "manual"],
        },
    )


def _no_image_visual_sidecar_warning(config: Config) -> WarningEntry:
    return WarningEntry(
        code=WarningCode.IMAGE_EXTRACTION_SKIPPED,
        message="image_mode=none skipped image extraction and visual figure sidecars.",
        details={
            "image_mode": ImageMode.NONE.value,
            "skip_reason": "image_mode_none",
            "rag_profile": config.rag_profile,
            "rag_figure_text_chunks_requested": config.rag_figure_text_chunks,
            "figure_region_ocr_requested": config.figure_region_ocr,
            "rag_generated_figure_descriptions_requested": config.rag_generated_figure_descriptions,
            "figure_structure_extraction_requested": config.figure_structure_extraction,
        },
    )


def _order_warnings_by_selected_page(
    warning_entries: list[WarningEntry],
    selected_pages: list[int],
) -> list[WarningEntry]:
    page_order = {page: idx for idx, page in enumerate(selected_pages)}
    return [
        warning
        for _, warning in sorted(
            enumerate(warning_entries),
            key=lambda item: (page_order.get(item[1].page, len(page_order)), item[0]),
        )
    ]


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


def _run_conversion_impl(
    config: Config,
    *,
    progress: ConversionProgressCallback | None = None,
    journal: ConversionJournal | None = None,
) -> ConversionResult:
    """Run conversion and write markdown, manifest, and report outputs."""
    started_at = datetime.now(timezone.utc)
    logger.info("Starting conversion input=%s output_dir=%s", config.input_pdf, config.output_dir)
    source_sha256 = _file_sha256(config.input_pdf) if config.input_pdf.exists() else ""
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
    output_profile = _output_profile(config)
    rag_sidecar_scope = _effective_rag_sidecar_scope(config, output_profile)
    image_extraction_disabled = image_mode is ImageMode.NONE
    requested_figure_sidecar_features = (
        config.rag_figure_text_chunks
        or config.figure_region_ocr
        or config.rag_generated_figure_descriptions
        or config.figure_structure_extraction
    )
    effective_rag_figure_text_chunks = config.rag_figure_text_chunks and not image_extraction_disabled
    effective_figure_region_ocr = config.figure_region_ocr and not image_extraction_disabled
    effective_rag_generated_figure_descriptions = (
        config.rag_generated_figure_descriptions and not image_extraction_disabled
    )
    effective_figure_structure_extraction = config.figure_structure_extraction and not image_extraction_disabled
    include_figure_visual_semantics = (
        effective_figure_region_ocr
        or effective_rag_generated_figure_descriptions
        or effective_figure_structure_extraction
    )
    requested_page_layout_sidecar = config.rag_profile in TECHNICAL_SPEC_RAG_PROFILES
    write_page_layout_sidecar = rag_sidecar_scope is RagSidecarScope.FULL and requested_page_layout_sidecar
    rag_sidecar_omitted_outputs = _omitted_rag_sidecars(
        config,
        scope=rag_sidecar_scope,
        rag_table_output=rag_table_output,
        domain_adapter=domain_adapter,
        include_figure_provenance=not image_extraction_disabled,
        include_figure_text_chunks=effective_rag_figure_text_chunks,
        include_figure_ocr_evidence=effective_figure_region_ocr,
        include_figure_descriptions=effective_rag_generated_figure_descriptions,
        include_figure_structures=effective_figure_structure_extraction,
        include_page_layout=requested_page_layout_sidecar,
    )
    write_minimal_rag_sidecars = rag_sidecar_scope in {RagSidecarScope.FULL, RagSidecarScope.MINIMAL}
    write_full_rag_sidecars = rag_sidecar_scope is RagSidecarScope.FULL
    write_figure_rag_sidecar = not image_extraction_disabled and (
        write_full_rag_sidecars
        or (write_minimal_rag_sidecars and (effective_rag_figure_text_chunks or include_figure_visual_semantics))
    )
    write_figure_ocr_evidence_sidecar = write_full_rag_sidecars and effective_figure_region_ocr
    stage_durations_ms: dict[str, int] = {}

    def stage_start() -> datetime:
        return datetime.now(timezone.utc)

    def finish_stage(name: str, started: datetime) -> None:
        elapsed_ms = max(int((datetime.now(timezone.utc) - started).total_seconds() * 1000), 0)
        stage_durations_ms[name] = stage_durations_ms.get(name, 0) + elapsed_ms
        if journal is not None:
            journal.finish_stage(name, stage_durations_ms)

    warnings: list[WarningEntry] = []

    def mark_stage(name: str, *, page: int | None = None) -> None:
        if journal is not None:
            journal.set_stage(name, page=page, warnings=warnings)

    if _technical_profile_domain_adapter_missing(config, domain_adapter):
        warnings.append(_technical_profile_domain_adapter_warning(config, domain_adapter))
    if image_extraction_disabled and requested_figure_sidecar_features:
        warnings.append(_no_image_visual_sidecar_warning(config))
    figure_semantics_started_at: float | None = None
    figure_semantics_timed_out = False
    figure_semantics_timeout_stage: str | None = None
    figure_semantics_timeout_elapsed_ms: int | None = None

    def ensure_figure_semantics_clock() -> None:
        nonlocal figure_semantics_started_at
        if figure_semantics_started_at is None:
            figure_semantics_started_at = time.monotonic()

    def figure_semantics_elapsed_ms() -> int:
        if figure_semantics_started_at is None:
            return 0
        return max(int((time.monotonic() - figure_semantics_started_at) * 1000), 0)

    def figure_semantics_timeout_expired(stage_name: str) -> bool:
        nonlocal figure_semantics_timed_out, figure_semantics_timeout_stage, figure_semantics_timeout_elapsed_ms
        timeout_seconds = config.figure_semantics_stage_timeout_seconds
        if timeout_seconds is None:
            return False
        ensure_figure_semantics_clock()
        started_at = figure_semantics_started_at if figure_semantics_started_at is not None else time.monotonic()
        elapsed_seconds = time.monotonic() - started_at
        if elapsed_seconds < timeout_seconds:
            return False
        if not figure_semantics_timed_out:
            figure_semantics_timed_out = True
            figure_semantics_timeout_stage = stage_name
            figure_semantics_timeout_elapsed_ms = figure_semantics_elapsed_ms()
            warnings.append(
                WarningEntry(
                    code=WarningCode.FIGURE_SEMANTICS_STAGE_TIMEOUT,
                    message="Figure semantics stage timeout; skipped remaining figure semantic sidecars.",
                    details={
                        "stage": stage_name,
                        "timeout_seconds": timeout_seconds,
                        "elapsed_ms": figure_semantics_timeout_elapsed_ms,
                        "timeout_reason": "stage_timeout",
                    },
                )
            )
        return True

    page_results_map: dict[int, PageResult] = {}
    failed_pages: list[int] = []
    heading_count = 0
    list_item_count = 0
    code_block_count = 0
    hyphenation_repair_count = 0
    font_heading_candidate_count = 0
    footnote_candidate_count = 0
    structure_low_confidence_count = 0
    rag_table_record_count = 0
    rag_table_file_count = 0
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
    retrieval_chunk_diagnostics = {
        "retrieval_chunk_max_token_estimate": 0,
        "retrieval_chunk_average_token_estimate": 0.0,
        "retrieval_chunk_over_target_count": 0,
        "retrieval_chunk_duplicate_source_ref_count": 0,
    }
    page_layout_records: list[dict] = []
    page_layout_record_count = 0
    page_layout_file_count = 0
    page_layout_metrics = {
        "layout_region_ref_count": 0,
        "layout_caption_link_count": 0,
        "layout_multi_column_page_count": 0,
        "layout_header_footer_suppressed_page_count": 0,
    }
    figure_rag_record_count = 0
    figure_rag_file_count = 0
    figure_ocr_evidence_records: list[dict] = []
    figure_ocr_evidence_record_count = 0
    figure_ocr_evidence_file_count = 0
    region_ocr_evidence_metrics = {
        "figure_ocr_evidence_record_count": 0,
        "region_ocr_evidence_figure_record_count": 0,
        "region_ocr_evidence_table_record_count": 0,
        "region_ocr_evidence_accepted_count": 0,
        "region_ocr_evidence_rejected_count": 0,
        "region_ocr_evidence_runtime_unavailable_count": 0,
        "region_ocr_evidence_not_attempted_count": 0,
    }
    figure_text_chunk_record_count = 0
    figure_description_record_count = 0
    figure_description_file_count = 0
    figure_description_low_confidence_count = 0
    figure_description_skipped_no_evidence_count = 0
    figure_description_chunk_record_count = 0
    figure_structure_record_count = 0
    figure_structure_file_count = 0
    figure_structure_low_confidence_count = 0
    figure_structure_skipped_no_structure_count = 0
    figure_structure_chunk_record_count = 0
    figure_region_ocr_metrics = {
        "figure_region_ocr_attempted_count": 0,
        "figure_region_ocr_candidate_count": 0,
        "figure_region_ocr_promoted_label_count": 0,
        "figure_region_ocr_low_confidence_count": 0,
        "figure_region_ocr_render_attempted_count": 0,
        "figure_region_ocr_region_candidate_count": 0,
        "figure_region_ocr_accepted_region_count": 0,
        "figure_region_ocr_rejected_region_count": 0,
        "figure_region_ocr_crop_rejected_count": 0,
        "figure_region_ocr_runtime_unavailable_count": 0,
    }
    domain_unit_record_count = 0
    domain_unit_file_count = 0
    requirement_traceability_record_count = 0
    requirement_traceability_file_count = 0
    technical_table_record_count = 0
    technical_table_file_count = 0
    engine_usage = {
        "pypdf": True,
        "pdfplumber": True,
        "ocr": False,
        "tables": False,
        "images": False,
    }

    mark_stage("output_setup")
    output_setup_started = stage_start()
    ensure_output_dirs(config.output_dir, config.assets_dirname)
    finish_stage("output_setup", output_setup_started)

    mark_stage("pdf_open")
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

    mark_stage("page_selection")
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
    if journal is not None:
        journal.set_selected_pages(selected_pages)
    _emit_progress(
        progress,
        ConversionProgressEvent(
            current=0,
            total=len(selected_pages),
            page=None,
            status="pages_selected",
            stage="page_selection",
        ),
    )

    requested_page_workers = config.page_workers
    effective_page_workers = effective_page_worker_count(requested_page_workers, len(selected_pages))
    page_parallel_enabled = effective_page_workers > 1
    page_worker_pdf_open_count = 0
    page_layout_lines: dict[int, list[TextLine]] = {}
    page_texts: dict[int, str] = {}
    raw_lines_by_page: dict[int, list[dict]] = {}
    text_metadata_by_page: dict[int, PageLayoutMetadata] = {}
    table_candidates_by_page: dict[int, PageTableCandidateResult] = {}
    page_worker_table_warnings: list[WarningEntry] = []
    shared_plumber_pdf = None
    mark_stage("text_extraction")
    text_started = stage_start()
    try:
        logger.info(
            "Extracting text for pages=%s page_workers=%s effective=%s",
            selected_pages,
            requested_page_workers,
            effective_page_workers,
        )
        if page_parallel_enabled:
            worker_results = run_page_workers(
                [
                    PageWorkerInput(
                        pdf_path=config.input_pdf,
                        page=page,
                        password=config.password,
                        collect_table_candidates=True,
                    )
                    for page in selected_pages
                ],
                effective_page_workers,
            )
            for worker_result in worker_results:
                page_worker_pdf_open_count += worker_result.pdf_open_count
                for warning in worker_result.warnings:
                    if (
                        warning.code == WarningCode.TABLE_EXTRACTION_FAILED
                        and warning.details.get("phase") == "table_candidate_collection"
                    ):
                        page_worker_table_warnings.append(warning)
                    else:
                        warnings.append(warning)
                if worker_result.table_candidate_result is not None:
                    table_candidates_by_page[worker_result.page] = worker_result.table_candidate_result
                else:
                    table_candidates_by_page[worker_result.page] = PageTableCandidateResult(
                        page=worker_result.page,
                        page_width=0.0,
                        page_height=0.0,
                    )
                if worker_result.failed:
                    failed_pages.append(worker_result.page)
                    page_layout_lines[worker_result.page] = []
                    page_texts[worker_result.page] = ""
                    page_results_map[worker_result.page] = PageResult(
                        page=worker_result.page,
                        status=PageStatus.FAILED,
                        text_layer_char_count=0,
                    )
                    continue
                page_layout_lines[worker_result.page] = worker_result.text_lines
                raw_lines_by_page[worker_result.page] = worker_result.raw_lines
                if worker_result.text_metadata is not None:
                    text_metadata_by_page[worker_result.page] = worker_result.text_metadata
        else:
            shared_plumber_pdf = pdf_context.get_pdfplumber_pdf()
            cached_text_lines_by_page = {page: pdf_context.get_text_lines(page) for page in selected_pages}
            text_layout = extract_page_text_layout_result(
                config.input_pdf,
                selected_pages,
                config.password,
                pdf=shared_plumber_pdf,
                text_lines_by_page=cached_text_lines_by_page,
            )
            page_layout_lines = text_layout.lines_by_page
            raw_lines_by_page = text_layout.raw_lines_by_page
            text_metadata_by_page = text_layout.metadata_by_page
        layout = page_layout_lines
        for page in selected_pages:
            lines = layout.get(page, [])
            page_layout_lines[page] = lines
            page_texts[page] = "\n".join(item.text for item in lines).strip()
            if page in failed_pages and page in page_results_map:
                continue
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

    mark_stage("ocr")
    ocr_started = stage_start()
    logger.info("Running OCR target_pages=%s force=%s", selected_pages, config.force_ocr)
    ocr_result = run_ocr(
        config.input_pdf,
        selected_pages,
        page_texts,
        config.force_ocr,
        ocr_lang=config.ocr_lang,
        ocr_backend=config.ocr_backend,
        worker_count=effective_page_workers,
    )
    finish_stage("ocr", ocr_started)
    warnings.extend(ocr_result.warnings)
    engine_usage["ocr"] = ocr_result.used_ocr
    for page in ocr_result.attempted_pages:
        if page in page_results_map:
            page_results_map[page].ocr_attempted = True
            page_results_map[page].ocr_reason = ocr_result.reasons_by_page.get(page)
            page_results_map[page].ocr_runtime_available = ocr_result.runtime_available
            metrics = ocr_result.metrics_by_page.get(page)
            if metrics:
                page_results_map[page].ocr_confidence_mean = metrics.mean
                page_results_map[page].ocr_confidence_median = metrics.median
                page_results_map[page].low_conf_token_ratio = metrics.low_conf_token_ratio
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
        mark_stage("header_footer")
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

    mark_stage("table_extraction")
    table_started = stage_start()
    logger.info("Extracting tables")
    table_result = extract_tables(
        config.input_pdf,
        selected_pages,
        config.password,
        table_mode,
        pdf=shared_plumber_pdf,
        text_lines_by_page=raw_lines_by_page,
        precomputed_candidates_by_page=table_candidates_by_page if page_parallel_enabled else None,
    )
    finish_stage("table_extraction", table_started)
    table_result.rag_tables = normalize_rag_table_payload(table_result.rag_tables)
    mark_stage("image_extraction")
    image_started = stage_start()
    page_image_boxes: dict[int, list[dict]] | None = None
    if image_extraction_disabled:
        logger.info("Skipping image extraction mode=%s", image_mode)
        image_result = ImageExtractionResult()
        for index, page in enumerate(selected_pages, start=1):
            _emit_progress(
                progress,
                ConversionProgressEvent(
                    current=index,
                    total=len(selected_pages),
                    page=page,
                    status="image_extraction_page_skipped",
                    stage="image_extraction",
                    image_count=0,
                    elapsed_ms=0,
                    timeout_reason="image_mode_none",
                ),
            )
    else:
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
            image_extraction_page_timeout_seconds=config.image_extraction_page_timeout_seconds,
            image_extraction_stage_timeout_seconds=config.image_extraction_stage_timeout_seconds,
            progress=_forward_image_progress(progress),
        )
    finish_stage("image_extraction", image_started)
    engine_usage["tables"] = len(table_result.assets) > 0
    engine_usage["images"] = len(image_result.assets) > 0
    _annotate_ocr_warning_context(warnings, page_results_map, page_image_boxes)
    warnings.extend(_order_warnings_by_selected_page(page_worker_table_warnings + table_result.warnings, selected_pages))
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
    mark_stage("normalization")
    normalization_started = stage_start()
    for index, page in enumerate(selected_pages, start=1):
        mark_stage("normalization", page=page)
        logger.debug("Normalizing page=%s", page)
        _emit_progress(
            progress,
            ConversionProgressEvent(
                current=index - 1,
                total=len(selected_pages),
                page=page,
                status="page_started",
                stage="normalization",
            ),
        )
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
        _emit_progress(
            progress,
            ConversionProgressEvent(
                current=index,
                total=len(selected_pages),
                page=page,
                status="page_finished",
                stage="normalization",
            ),
        )
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

    mark_stage("rag_text_blocks")
    rag_text_started = stage_start()
    text_block_result = build_text_blocks(normalized_lines_by_page_for_blocks)
    document_ir = build_pdf2md_document_ir(
        source_sha256=source_sha256,
        selected_pages=selected_pages,
        text_blocks_by_page=text_block_result.blocks_by_page,
        page_results=page_results_map,
        table_assets=table_result.assets,
        figure_assets=image_result.assets,
    )
    text_block_records = ir_text_block_records(document_ir)
    if write_minimal_rag_sidecars:
        rag_text_block_record_count, rag_text_block_file_count = write_rag_text_block_output(
            config,
            text_block_records,
        )
    font_heading_candidate_count = text_block_result.font_heading_candidate_count
    footnote_candidate_count = text_block_result.footnote_candidate_count
    structure_low_confidence_count = text_block_result.structure_low_confidence_count
    finish_stage("rag_text_blocks", rag_text_started)
    contextual_rag_tables: list[dict] = []
    semantic_units: list[dict] = []
    requirements: list[dict] = []
    requirement_traceability_records: list[dict] = []
    technical_table_records: list[dict] = []
    figure_records: list[dict] = []
    figure_description_records: list[dict] = []
    figure_structure_records: list[dict] = []
    domain_units: list[dict] = []
    if write_minimal_rag_sidecars or config.debug:
        contextual_rag_tables = annotate_rag_tables_with_heading_context(
            table_result.rag_tables,
            text_block_records,
        )

    if write_figure_rag_sidecar and not figure_semantics_timeout_expired("rag_figures"):
        ensure_figure_semantics_clock()
        mark_stage("rag_figures")
        figure_rag_started = stage_start()
        figure_records = build_figure_records(
            images=image_result.assets,
            excluded_images=image_result.excluded_assets,
            text_block_records=text_block_records,
        )
        if effective_figure_region_ocr and not figure_semantics_timeout_expired("figure_region_ocr"):
            figure_records, figure_region_ocr_metrics = augment_figure_records_with_region_ocr(
                figure_records,
                pdf_path=config.input_pdf,
                ocr_lang=config.ocr_lang,
                ocr_backend=config.ocr_backend,
            )
        figure_rag_record_count, figure_rag_file_count = write_figure_rag_output(config, figure_records)
        finish_stage("rag_figures", figure_rag_started)

    if write_figure_ocr_evidence_sidecar and not figure_semantics_timeout_expired("rag_ocr_evidence"):
        mark_stage("rag_ocr_evidence")
        figure_ocr_evidence_started = stage_start()
        figure_ocr_evidence_records, region_ocr_evidence_metrics = build_region_ocr_evidence_records(
            figure_records=figure_records,
            rag_tables=contextual_rag_tables if rag_table_output.writes_jsonl() else [],
            source_sha256=source_sha256,
            pdf_path=config.input_pdf,
            ocr_lang=config.ocr_lang,
            ocr_backend=config.ocr_backend,
        )
        figure_ocr_evidence_record_count, figure_ocr_evidence_file_count = write_figure_ocr_evidence_output(
            config,
            figure_ocr_evidence_records,
        )
        finish_stage("rag_ocr_evidence", figure_ocr_evidence_started)

    if (
        write_minimal_rag_sidecars
        and effective_rag_generated_figure_descriptions
        and not figure_semantics_timeout_expired("rag_figure_descriptions")
    ):
        mark_stage("rag_figure_descriptions")
        figure_description_started = stage_start()
        figure_description_records, figure_description_metrics = build_figure_description_records(
            figure_records,
            backend=config.figure_description_backend,
        )
        figure_description_record_count = figure_description_metrics["figure_description_record_count"]
        figure_description_low_confidence_count = figure_description_metrics[
            "figure_description_low_confidence_count"
        ]
        figure_description_skipped_no_evidence_count = figure_description_metrics[
            "figure_description_skipped_no_evidence_count"
        ]
        figure_description_record_count, figure_description_file_count = write_figure_description_output(
            config,
            figure_description_records,
        )
        finish_stage("rag_figure_descriptions", figure_description_started)

    if (
        write_minimal_rag_sidecars
        and effective_figure_structure_extraction
        and not figure_semantics_timeout_expired("rag_figure_structures")
    ):
        mark_stage("rag_figure_structures")
        figure_structure_started = stage_start()
        figure_structure_records, figure_structure_metrics = build_figure_structure_records(figure_records)
        figure_structure_record_count = figure_structure_metrics["figure_structure_record_count"]
        figure_structure_low_confidence_count = figure_structure_metrics["figure_structure_low_confidence_count"]
        figure_structure_skipped_no_structure_count = figure_structure_metrics[
            "figure_structure_skipped_no_structure_count"
        ]
        figure_structure_record_count, figure_structure_file_count = write_figure_structure_output(
            config,
            figure_structure_records,
        )
        finish_stage("rag_figure_structures", figure_structure_started)

    if write_minimal_rag_sidecars:
        mark_stage("rag_semantics")
        semantic_started = stage_start()
        pdf_outline_targets = extract_pdf_outline_reference_targets(reader, selected_pages=set(selected_pages))
        semantic_result = build_semantic_layer(
            text_block_records=text_block_records,
            rag_tables=contextual_rag_tables,
            pdf_outline_targets=pdf_outline_targets,
            source_sha256=source_sha256,
        )
        semantic_units = semantic_result.semantic_units
        requirements = semantic_result.requirements
        if write_full_rag_sidecars:
            (
                semantic_unit_record_count,
                semantic_unit_file_count,
                requirement_record_count,
                requirement_file_count,
                cross_ref_record_count,
                cross_ref_file_count,
            ) = write_semantic_layer_outputs(
                config,
                semantic_units=semantic_result.semantic_units,
                requirements=semantic_result.requirements,
                cross_refs=semantic_result.cross_refs,
            )
        semantic_low_confidence_count = semantic_result.semantic_low_confidence_count
        unresolved_cross_ref_count = semantic_result.unresolved_cross_ref_count
        normative_requirement_count = semantic_result.normative_requirement_count
        finish_stage("rag_semantics", semantic_started)

        mark_stage("rag_requirement_traceability")
        requirement_traceability_started = stage_start()
        requirement_traceability_records = build_requirement_traceability_records(
            requirements=semantic_result.requirements,
            rag_tables=contextual_rag_tables,
            semantic_units=semantic_result.semantic_units,
            source_sha256=source_sha256,
        )
        if write_full_rag_sidecars:
            requirement_traceability_record_count, requirement_traceability_file_count = (
                write_requirement_traceability_output(
                    config,
                    requirement_traceability_records,
                )
            )
        finish_stage("rag_requirement_traceability", requirement_traceability_started)

        mark_stage("rag_technical_tables")
        technical_tables_started = stage_start()
        technical_table_records = build_technical_table_records(contextual_rag_tables, source_sha256=source_sha256)
        if write_full_rag_sidecars:
            technical_table_record_count, technical_table_file_count = write_technical_table_output(
                config,
                technical_table_records,
            )
        finish_stage("rag_technical_tables", technical_tables_started)

        if domain_adapter is not DomainAdapterMode.NONE:
            mark_stage("rag_domain_adapter")
            domain_started = stage_start()
            domain_units = build_domain_units(
                domain_adapter=domain_adapter,
                rag_tables=contextual_rag_tables,
                technical_table_records=technical_table_records,
                manual_adapter_label=config.manual_domain_adapter_label,
                manual_adapter_keywords=config.manual_domain_adapter_keywords,
                source_sha256=source_sha256,
            )
            if write_full_rag_sidecars:
                domain_unit_record_count, domain_unit_file_count = write_domain_unit_output(config, domain_units)
            finish_stage("rag_domain_adapter", domain_started)

        if write_page_layout_sidecar:
            mark_stage("rag_page_layout")
            page_layout_started = stage_start()
            page_layout_records, page_layout_metrics = build_page_layout_records(
                selected_pages=selected_pages,
                page_results=page_results_map,
                text_block_records=text_block_records,
                rag_tables=contextual_rag_tables,
                figure_records=figure_records,
                source_sha256=source_sha256,
            )
            page_layout_record_count, page_layout_file_count = write_page_layout_output(
                config,
                page_layout_records,
            )
            finish_stage("rag_page_layout", page_layout_started)

        mark_stage("rag_retrieval_chunks")
        retrieval_started = stage_start()
        retrieval_token_counter = (
            None if config.retrieval_tokenizer == "char" else make_token_counter(config.retrieval_tokenizer)
        )
        retrieval_chunks = build_retrieval_chunks(
            text_block_records=text_block_records,
            semantic_units=semantic_units,
            requirements=requirements,
            rag_tables=contextual_rag_tables,
            figure_records=figure_records,
            figure_description_records=figure_description_records,
            figure_structure_records=figure_structure_records,
            domain_units=domain_units,
            requirement_traceability_records=requirement_traceability_records,
            technical_table_records=technical_table_records,
            source_sha256=source_sha256,
            max_tokens=config.retrieval_chunk_max_tokens,
            token_counter=retrieval_token_counter,
            contextual_embedding_text=config.rag_contextual_embedding_text,
            include_figure_text_chunks=effective_rag_figure_text_chunks,
            merge_sibling_text_blocks=config.rag_merge_sibling_text_chunks,
            relationship_metadata=config.rag_chunk_relationship_metadata,
        )
        figure_text_chunk_record_count = sum(
            1 for chunk in retrieval_chunks if chunk.get("chunk_type") == "figure_text"
        )
        figure_description_chunk_record_count = sum(
            1 for chunk in retrieval_chunks if chunk.get("chunk_type") == "figure_description"
        )
        figure_structure_chunk_record_count = sum(
            1 for chunk in retrieval_chunks if chunk.get("chunk_type") == "figure_structure"
        )
        retrieval_chunk_diagnostics = build_retrieval_chunk_diagnostics(
            retrieval_chunks,
            target_tokens=config.retrieval_chunk_max_tokens,
        )
        retrieval_chunk_record_count, retrieval_chunk_file_count = write_retrieval_chunk_output(
            config,
            retrieval_chunks,
        )
        finish_stage("rag_retrieval_chunks", retrieval_started)

    mark_stage("markdown_serialization")
    markdown_started = stage_start()
    markdown_result = serialize_markdown_blocks_result(
        page_text_blocks=ir_text_blocks_by_page(document_ir),
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

    mark_stage("rag_tables")
    rag_started = stage_start()
    if write_minimal_rag_sidecars:
        rag_table_record_count, rag_table_file_count = write_rag_table_outputs(
            config=config,
            output_mode=rag_table_output,
            rag_tables=table_result.rag_tables,
        )
    finish_stage("rag_tables", rag_started)

    if config.debug:
        mark_stage("debug_artifacts")
        debug_started = stage_start()
        logger.info("Writing debug artifacts")
        write_debug_artifacts(
            config=config,
            selected_pages=selected_pages,
            raw_lines_by_page=raw_lines_by_page,
            ordered_lines_by_page=page_layout_lines,
            normalized_lines_by_page=normalized_lines_debug_by_page,
            text_metadata_by_page=text_metadata_by_page,
            table_candidates_by_page=table_result.debug_candidates_by_page,
            image_candidates_by_page=image_result.debug_candidates_by_page,
            table_quality_review_pack=build_table_quality_review_pack(
                table_quality=table_result.table_quality,
                rag_tables=contextual_rag_tables,
                technical_table_records=technical_table_records,
                domain_units=domain_units,
                table_fallbacks=table_result.fallbacks,
            ),
        )
        finish_stage("debug_artifacts", debug_started)

    mark_stage("manifest")
    manifest_started = stage_start()
    manifest_options = {
        "image_mode": image_mode,
        "table_mode": table_mode.manifest_value(),
        "force_ocr": config.force_ocr,
        "ocr_lang": config.ocr_lang,
        "ocr_backend": config.ocr_backend,
        "keep_page_markers": config.keep_page_markers,
        "remove_header_footer": config.remove_header_footer,
        "dedupe_images": config.dedupe_images,
        "repair_hyphenation": config.repair_hyphenation,
        "figure_crop_fallback": config.figure_crop_fallback,
        "page_workers": requested_page_workers,
        "page_worker_effective_count": effective_page_workers,
        "page_parallel_enabled": page_parallel_enabled,
        "rag_table_output": rag_table_output.value,
        "domain_adapter": domain_adapter.value,
        **({"rag_profile": config.rag_profile} if config.rag_profile != "preserve" else {}),
        "confidential_safe_mode": config.confidential_safe_mode,
        "local_only_processing": True,
        "external_llm_calls": False,
        "external_embedding_calls": False,
        "path_redaction": "enabled" if config.confidential_safe_mode else "disabled",
        "source_filename_masked": config.confidential_safe_mode,
        "retrieval_chunk_max_tokens": config.retrieval_chunk_max_tokens,
        "retrieval_tokenizer": config.retrieval_tokenizer,
        "rag_contextual_embedding_text": config.rag_contextual_embedding_text,
        "rag_merge_sibling_text_chunks": config.rag_merge_sibling_text_chunks,
        "rag_chunk_relationship_metadata": config.rag_chunk_relationship_metadata,
        "domain_units_jsonl_filename": config.domain_units_jsonl_filename,
        "debug": config.debug,
        "pages": config.pages,
        "version": config.version,
    }
    if image_extraction_disabled:
        manifest_options.update(
            {
                "image_extraction_skipped": True,
                "image_extraction_skip_reason": "image_mode_none",
                "figure_sidecars_skipped": True,
            }
        )
    if config.image_extraction_page_timeout_seconds is not None:
        manifest_options["image_extraction_page_timeout_seconds"] = config.image_extraction_page_timeout_seconds
    if config.image_extraction_stage_timeout_seconds is not None:
        manifest_options["image_extraction_stage_timeout_seconds"] = config.image_extraction_stage_timeout_seconds
    if config.figure_semantics_stage_timeout_seconds is not None:
        manifest_options["figure_semantics_stage_timeout_seconds"] = config.figure_semantics_stage_timeout_seconds
    if domain_adapter is DomainAdapterMode.MANUAL:
        if config.manual_domain_adapter_label:
            manifest_options["manual_domain_adapter_label"] = config.manual_domain_adapter_label
        if config.manual_domain_adapter_keywords:
            manifest_options["manual_domain_adapter_keywords"] = config.manual_domain_adapter_keywords
    if write_minimal_rag_sidecars:
        manifest_options.update(
            {
                "rag_text_blocks_output": "jsonl",
                "rag_text_blocks_jsonl_filename": config.rag_text_blocks_jsonl_filename,
                "retrieval_chunks_output": "jsonl",
                "retrieval_chunks_jsonl_filename": config.retrieval_chunks_jsonl_filename,
            }
        )
    if effective_rag_figure_text_chunks:
        manifest_options["rag_figure_text_chunks"] = True
    if effective_figure_region_ocr:
        manifest_options["figure_region_ocr"] = True
    if effective_rag_generated_figure_descriptions:
        manifest_options["rag_generated_figure_descriptions"] = True
        manifest_options["figure_description_backend"] = config.figure_description_backend
    if effective_figure_structure_extraction:
        manifest_options["figure_structure_extraction"] = True
    if write_figure_rag_sidecar:
        manifest_options.update(
            {
                "figures_rag_output": "jsonl",
                "figures_rag_jsonl_filename": config.figures_rag_jsonl_filename,
            }
        )
    if write_figure_ocr_evidence_sidecar:
        manifest_options.update(
            {
                "figure_ocr_evidence_output": "jsonl",
                "figure_ocr_evidence_jsonl_filename": config.figure_ocr_evidence_jsonl_filename,
            }
        )
    if figure_description_file_count > 0:
        manifest_options.update(
            {
                "figure_descriptions_output": "jsonl",
                "figure_descriptions_jsonl_filename": config.figure_descriptions_jsonl_filename,
            }
        )
    if figure_structure_file_count > 0:
        manifest_options.update(
            {
                "figure_structures_output": "jsonl",
                "figure_structures_jsonl_filename": config.figure_structures_jsonl_filename,
            }
        )
    if write_full_rag_sidecars:
        manifest_options.update(
            {
                "semantic_layer_output": "jsonl",
                "semantic_units_jsonl_filename": config.semantic_units_jsonl_filename,
                "requirements_jsonl_filename": config.requirements_jsonl_filename,
                "cross_refs_jsonl_filename": config.cross_refs_jsonl_filename,
                "requirement_traceability_output": "jsonl",
                "requirement_traceability_jsonl_filename": config.requirement_traceability_jsonl_filename,
                "technical_tables_output": "jsonl",
                "technical_tables_jsonl_filename": config.technical_tables_jsonl_filename,
            }
        )
    if write_page_layout_sidecar:
        manifest_options.update(
            {
                "page_layout_output": "jsonl",
                "page_layout_jsonl_filename": config.page_layout_jsonl_filename,
            }
        )
    if output_profile is not OutputProfile.FULL or rag_sidecar_scope is not RagSidecarScope.FULL:
        manifest_options.update(
            {
                "output_profile": output_profile.value,
                "rag_sidecar_scope": rag_sidecar_scope.value,
                "rag_sidecar_omitted_outputs": rag_sidecar_omitted_outputs,
                "rag_sidecar_omitted_reason": SIDECAR_OMITTED_REASON if rag_sidecar_omitted_outputs else None,
            }
        )
    manifest = Manifest(
        input_file="redacted.pdf" if config.confidential_safe_mode else config.input_pdf.name,
        total_pages=total_pages,
        selected_pages=selected_pages,
        options=manifest_options,
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
    table_fallback_reason_counts = count_table_fallback_reasons(table_result.fallbacks)
    table_low_quality_count = count_low_quality_tables(table_result.table_quality)
    table_actionable_low_quality_count = count_actionable_low_quality_tables(
        table_result.table_quality,
        table_result.fallbacks,
    )
    table_advisory_low_quality_count = max(table_low_quality_count - table_actionable_low_quality_count, 0)
    table_actionable_low_quality_pages = low_quality_table_pages(
        table_result.table_quality,
        table_fallbacks=table_result.fallbacks,
        actionable_only=True,
    )
    table_caption_linked_count = count_caption_linked_tables(table_result.table_quality)
    table_confidence_v2_buckets, table_confidence_v2_average = summarize_table_confidence_v2(
        table_result.table_quality
    )
    page_results, page_status_counts = finalize_page_statuses(
        page_results,
        warnings,
        actionable_pages=table_actionable_low_quality_pages,
    )
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
        if (
            (page_result.ocr_confidence_mean or 100.0) < OCR_LOW_CONFIDENCE_MEAN_THRESHOLD
            or (page_result.low_conf_token_ratio or 0.0) > OCR_LOW_CONFIDENCE_TOKEN_RATIO_THRESHOLD
        ):
            low_conf_pages.append(page_result.page)

    status, exit_code = determine_conversion_status(
        warnings,
        failed_pages,
        table_actionable_low_quality_count=table_actionable_low_quality_count,
    )
    mark_stage("reporting")
    reporting_started = stage_start()
    elapsed_seconds = (finished_at - started_at).total_seconds()
    pages_per_second = round(len(selected_pages) / elapsed_seconds, 4) if elapsed_seconds > 0 else None
    finish_stage("reporting", reporting_started)
    report_summary_extras: dict[str, object] = {}
    if image_extraction_disabled:
        report_summary_extras.update(
            {
                "image_extraction_skipped": True,
                "image_extraction_skip_reason": "image_mode_none",
                "figure_sidecars_skipped": True,
            }
        )
    if (
        config.image_extraction_page_timeout_seconds is not None
        or config.image_extraction_stage_timeout_seconds is not None
        or image_result.timed_out_pages
        or image_result.stage_timed_out
    ):
        report_summary_extras.update(
            {
                "image_extraction_page_timeout_seconds": config.image_extraction_page_timeout_seconds,
                "image_extraction_stage_timeout_seconds": config.image_extraction_stage_timeout_seconds,
                "image_extraction_page_timeout_count": len(image_result.timed_out_pages),
                "image_extraction_stage_timeout_count": 1 if image_result.stage_timed_out else 0,
                "image_extraction_processed_page_count": len(image_result.processed_pages),
                "image_extraction_skipped_page_count": len(image_result.skipped_pages),
                "image_extraction_timed_out_pages": image_result.timed_out_pages,
                "image_extraction_last_page": image_result.last_page,
                "image_extraction_last_image_count": image_result.last_image_count,
            }
        )
    if config.figure_semantics_stage_timeout_seconds is not None or figure_semantics_timed_out:
        report_summary_extras.update(
            {
                "figure_semantics_stage_timeout_seconds": config.figure_semantics_stage_timeout_seconds,
                "figure_semantics_stage_timeout_count": 1 if figure_semantics_timed_out else 0,
                "figure_semantics_timeout_stage": figure_semantics_timeout_stage,
                "figure_semantics_timeout_elapsed_ms": figure_semantics_timeout_elapsed_ms,
            }
        )
    if output_profile is not OutputProfile.FULL or rag_sidecar_scope is not RagSidecarScope.FULL:
        report_summary_extras.update(
            {
                "output_profile": output_profile.value,
                "rag_sidecar_scope": rag_sidecar_scope.value,
                "rag_sidecar_omitted_outputs": rag_sidecar_omitted_outputs,
                "rag_sidecar_omitted_reason": SIDECAR_OMITTED_REASON if rag_sidecar_omitted_outputs else None,
            }
        )
    if effective_rag_figure_text_chunks:
        report_summary_extras["rag_figure_text_chunks"] = True
        report_summary_extras["figure_text_chunk_record_count"] = figure_text_chunk_record_count
    if effective_figure_region_ocr:
        report_summary_extras["figure_region_ocr"] = True
        report_summary_extras.update(figure_region_ocr_metrics)
        if write_figure_ocr_evidence_sidecar:
            report_summary_extras["figure_ocr_evidence_file_count"] = figure_ocr_evidence_file_count
            report_summary_extras.update(region_ocr_evidence_metrics)
    if effective_rag_generated_figure_descriptions:
        report_summary_extras["rag_generated_figure_descriptions"] = True
        report_summary_extras["figure_description_backend"] = config.figure_description_backend
        report_summary_extras["figure_description_record_count"] = figure_description_record_count
        report_summary_extras["figure_description_file_count"] = figure_description_file_count
        report_summary_extras["figure_description_low_confidence_count"] = figure_description_low_confidence_count
        report_summary_extras["figure_description_skipped_no_evidence_count"] = (
            figure_description_skipped_no_evidence_count
        )
        report_summary_extras["figure_description_chunk_record_count"] = figure_description_chunk_record_count
    if effective_figure_structure_extraction:
        report_summary_extras["figure_structure_extraction"] = True
        report_summary_extras["figure_structure_record_count"] = figure_structure_record_count
        report_summary_extras["figure_structure_file_count"] = figure_structure_file_count
        report_summary_extras["figure_structure_low_confidence_count"] = figure_structure_low_confidence_count
        report_summary_extras["figure_structure_skipped_no_structure_count"] = (
            figure_structure_skipped_no_structure_count
        )
        report_summary_extras["figure_structure_chunk_record_count"] = figure_structure_chunk_record_count
    if write_page_layout_sidecar:
        report_summary_extras.update(
            {
                "page_layout_record_count": page_layout_record_count,
                "page_layout_file_count": page_layout_file_count,
                "layout_region_ref_count": page_layout_metrics["layout_region_ref_count"],
                "layout_caption_link_count": page_layout_metrics["layout_caption_link_count"],
                "layout_multi_column_page_count": page_layout_metrics["layout_multi_column_page_count"],
                "layout_header_footer_suppressed_page_count": page_layout_metrics[
                    "layout_header_footer_suppressed_page_count"
                ],
            }
        )
    if domain_adapter is DomainAdapterMode.MANUAL:
        if config.manual_domain_adapter_label:
            report_summary_extras["manual_domain_adapter_label"] = config.manual_domain_adapter_label
        if config.manual_domain_adapter_keywords:
            report_summary_extras["manual_domain_adapter_keywords"] = config.manual_domain_adapter_keywords
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
        pdf_open_count=pdf_context.pdf_open_count + ocr_result.pdf_open_count + page_worker_pdf_open_count,
        pages_per_second=pages_per_second,
        page_worker_count=requested_page_workers,
        page_parallel_enabled=page_parallel_enabled,
        page_worker_effective_count=effective_page_workers,
        rag_table_output=rag_table_output.value,
        rag_table_record_count=rag_table_record_count,
        rag_table_file_count=rag_table_file_count,
        table_fallback_reason_counts=table_fallback_reason_counts,
        table_low_quality_count=table_low_quality_count,
        table_actionable_low_quality_count=table_actionable_low_quality_count,
        table_advisory_low_quality_count=table_advisory_low_quality_count,
        table_confidence_v2_buckets=table_confidence_v2_buckets,
        table_confidence_v2_average=table_confidence_v2_average,
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
        retrieval_chunk_max_token_estimate=retrieval_chunk_diagnostics["retrieval_chunk_max_token_estimate"],
        retrieval_chunk_average_token_estimate=retrieval_chunk_diagnostics["retrieval_chunk_average_token_estimate"],
        retrieval_chunk_over_target_count=retrieval_chunk_diagnostics["retrieval_chunk_over_target_count"],
        retrieval_chunk_duplicate_source_ref_count=retrieval_chunk_diagnostics[
            "retrieval_chunk_duplicate_source_ref_count"
        ],
        figure_rag_record_count=figure_rag_record_count,
        figure_rag_file_count=figure_rag_file_count,
        domain_unit_record_count=domain_unit_record_count,
        domain_unit_file_count=domain_unit_file_count,
        requirement_traceability_record_count=requirement_traceability_record_count,
        requirement_traceability_file_count=requirement_traceability_file_count,
        technical_table_record_count=technical_table_record_count,
        technical_table_file_count=technical_table_file_count,
        confidential_safe_mode=config.confidential_safe_mode,
        summary_extras=report_summary_extras or None,
    )
    report_path = config.output_dir / config.report_filename
    logger.info("Writing report path=%s status=%s exit_code=%s", report_path, status.value, exit_code)
    write_json(report_path, serialize_report(report))
    if config.confidential_safe_mode:
        write_json(config.output_dir / config.sanitized_report_filename, serialize_report(report))
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


def _page_results_for_interrupted_report(journal: ConversionJournal) -> list[PageResult]:
    page_results: list[PageResult] = []
    for page in sorted(journal.completed_pages):
        page_results.append(PageResult(page=page, status=PageStatus.SUCCESS))
    for page in sorted(journal.failed_pages - journal.completed_pages):
        page_results.append(PageResult(page=page, status=PageStatus.FAILED))
    return page_results


def _engine_usage_for_interrupted_report(journal: ConversionJournal) -> dict[str, bool]:
    stages = set(journal.stage_durations_ms)
    current_stage = journal.current_stage or ""
    return {
        "pypdf": "pdf_open" in stages or current_stage not in {"starting", "output_setup"},
        "pdfplumber": "text_extraction" in stages,
        "ocr": "ocr" in stages,
        "tables": "table_extraction" in stages,
        "images": "image_extraction" in stages,
    }


def _build_interrupted_conversion_result(
    *,
    config: Config,
    journal: ConversionJournal,
    started_at: datetime,
    exc: BaseException,
    interrupted: bool,
) -> ConversionResult:
    status_label = "interrupted" if interrupted else "failed"
    warning_code = WarningCode.CONVERSION_INTERRUPTED if interrupted else WarningCode.CONVERSION_FATAL_ERROR
    message = "Conversion interrupted before completion." if interrupted else "Conversion failed before completion."
    if str(exc):
        message = f"{message} {str(exc)}"
    warning = WarningEntry(
        code=warning_code,
        message=message,
        page=journal.current_page,
        details={
            "exception_type": type(exc).__name__,
            "stage": journal.current_stage,
            "interrupted": interrupted,
        },
    )
    logger.exception("Conversion ended before completion stage=%s", journal.current_stage)
    journal.write_interrupted_report(status=status_label, warning=warning, exc=exc)
    finished_at = datetime.now(timezone.utc)
    report = build_report(
        started_at=started_at,
        finished_at=finished_at,
        status=ConversionStatus.FAILED,
        warnings=[warning],
        page_results=_page_results_for_interrupted_report(journal),
        failed_pages=sorted(journal.failed_pages),
        engine_usage=_engine_usage_for_interrupted_report(journal),
        stage_durations_ms=journal.stage_durations_ms,
        summary_extras=journal.interrupted_summary_extras(),
    )
    report_path = config.output_dir / config.report_filename
    write_json(report_path, serialize_report(report))
    if config.confidential_safe_mode:
        write_json(config.output_dir / config.sanitized_report_filename, serialize_report(report))
    journal.write_state(status=status_label)

    markdown_path = config.output_dir / config.markdown_filename
    manifest_path = config.output_dir / config.manifest_filename
    return ConversionResult(
        exit_code=EXIT_FATAL,
        markdown_path=markdown_path if markdown_path.exists() else None,
        manifest_path=manifest_path if manifest_path.exists() else None,
        report_path=report_path,
        warnings=[warning],
        status=ConversionStatus.FAILED,
        report=report,
    )


def run_conversion(config: Config, *, progress: ConversionProgressCallback | None = None) -> ConversionResult:
    """Run conversion and write markdown, manifest, report, and conversion state outputs."""
    started_at = datetime.now(timezone.utc)
    ensure_output_dirs(config.output_dir, config.assets_dirname)
    journal = ConversionJournal(config, started_at=started_at)
    journal.write_state()

    def wrapped_progress(event: ConversionProgressEvent) -> None:
        journal.handle_progress(event)
        _emit_progress(progress, event)

    try:
        result = _run_conversion_impl(config, progress=wrapped_progress, journal=journal)
        journal.mark_finished(result)
        return result
    except KeyboardInterrupt as exc:
        return _build_interrupted_conversion_result(
            config=config,
            journal=journal,
            started_at=started_at,
            exc=exc,
            interrupted=True,
        )
    except Exception as exc:  # noqa: BLE001
        return _build_interrupted_conversion_result(
            config=config,
            journal=journal,
            started_at=started_at,
            exc=exc,
            interrupted=False,
        )
