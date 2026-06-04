from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ImageMode(str, Enum):
    REFERENCED = "referenced"
    EMBEDDED = "embedded"
    PLACEHOLDER = "placeholder"


class TableMode(str, Enum):
    AUTO = "auto"
    MARKDOWN = "markdown"
    HTML = "html"
    GFM_ONLY = "gfm-only"
    HTML_ONLY = "html-only"

    def manifest_value(self) -> str:
        if self is TableMode.HTML_ONLY:
            return TableMode.HTML.value
        return self.value

    def requested_mode(self) -> str:
        if self in {TableMode.HTML, TableMode.HTML_ONLY}:
            return TableMode.HTML.value
        if self is TableMode.MARKDOWN:
            return TableMode.MARKDOWN.value
        if self is TableMode.GFM_ONLY:
            return TableMode.GFM_ONLY.value
        return TableMode.AUTO.value


class RagTableOutputMode(str, Enum):
    NONE = "none"
    MARKDOWN = "markdown"
    JSONL = "jsonl"
    BOTH = "both"

    def writes_markdown(self) -> bool:
        return self in {RagTableOutputMode.MARKDOWN, RagTableOutputMode.BOTH}

    def writes_jsonl(self) -> bool:
        return self in {RagTableOutputMode.JSONL, RagTableOutputMode.BOTH}


class OutputProfile(str, Enum):
    FULL = "full"
    FAST = "fast"


class RagSidecarScope(str, Enum):
    FULL = "full"
    MINIMAL = "minimal"
    NONE = "none"


class DomainAdapterMode(str, Enum):
    NONE = "none"
    NVME = "nvme"
    PCIE = "pcie"
    OCP = "ocp"
    TCG = "tcg"
    SPDM = "spdm"
    CUSTOMER_REQUIREMENTS = "customer-requirements"
    MANUAL = "manual"


class ConversionStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class PageStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class LineType(str, Enum):
    HEADING_INDEX = "HEADING_INDEX"
    FIGURE_CAPTION = "FIGURE_CAPTION"
    TABLE_CAPTION = "TABLE_CAPTION"
    TOC_LINE = "TOC_LINE"
    LIST_ITEM = "LIST_ITEM"
    BODY_LINE = "BODY_LINE"


class WarningEntry(BaseModel):
    code: str
    message: str
    page: Optional[int] = None
    details: dict[str, Any] = Field(default_factory=dict)


class PageResult(BaseModel):
    page: int
    status: PageStatus = PageStatus.SUCCESS
    char_count: int = 0
    warning_count: int = 0
    used_ocr: bool = False
    ocr_confidence_mean: Optional[float] = None
    ocr_confidence_median: Optional[float] = None
    low_conf_token_ratio: Optional[float] = None
    text_layer_char_count: int = 0
    ocr_attempted: bool = False
    ocr_reason: Optional[str] = None
    ocr_runtime_available: Optional[bool] = None
    line_merge_count: int = 0
    structure_line_count: int = 0
    dedupe_count: int = 0
    suppressed_line_count: int = 0
    reading_order_strategy: str = "top"
    column_count_estimate: int = 1
    header_footer_suppressed_count: int = 0


class ReportSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    processed_pages: int = 0
    warning_count: int = 0
    actionable_warning_count: int = 0
    advisory_warning_count: int = 0
    failed_page_count: int = 0
    partial_success: bool = False
    ocr_confidence_by_page: dict[str, dict[str, float]] = Field(default_factory=dict)
    excluded_image_count: int = 0
    excluded_images: list[dict[str, Any]] = Field(default_factory=list)
    total_deduplicated_blocks: int = 0
    total_suppressed_lines: int = 0
    deduplicated_blocks: list[dict[str, Any]] = Field(default_factory=list)
    suppressed_lines: list[dict[str, Any]] = Field(default_factory=list)
    table_quality: list[dict[str, Any]] = Field(default_factory=list)
    table_fallback_count: int = 0
    table_fallbacks: list[dict[str, Any]] = Field(default_factory=list)
    table_mode_requested: Optional[str] = None
    table_total: int = 0
    table_html_count: int = 0
    table_gfm_count: int = 0
    table_recovered_count: int = 0
    table_unresolved_count: int = 0
    table_markdown_forced_count: int = 0
    table_html_forced_count: int = 0
    low_confidence_pages: list[int] = Field(default_factory=list)
    page_status_counts: dict[str, int] = Field(
        default_factory=lambda: {
            "success": 0,
            "partial_success": 0,
            "failed": 0,
        }
    )
    structure_marker_suppressed_count: int = 0
    structure_marker_recovered_count: int = 0
    structure_marker_recovered_exact_count: int = 0
    structure_marker_recovered_context_count: int = 0
    structure_marker_suppressed_no_candidate_count: int = 0
    structure_marker_suppressed_ambiguous_count: int = 0
    stage_durations_ms: dict[str, int] = Field(default_factory=dict)
    pdf_open_count: int = 0
    pages_per_second: Optional[float] = None
    page_worker_count: int = 1
    page_parallel_enabled: bool = False
    page_worker_effective_count: int = 1
    rag_table_output: str = "none"
    rag_table_record_count: int = 0
    rag_table_file_count: int = 0
    table_fallback_reason_counts: dict[str, int] = Field(default_factory=dict)
    table_expected_fallback_count: int = 0
    table_expected_fallback_reason_counts: dict[str, int] = Field(default_factory=dict)
    table_actionable_fallback_count: int = 0
    table_low_quality_count: int = 0
    table_actionable_low_quality_count: int = 0
    table_advisory_low_quality_count: int = 0
    ocr_actionable_warning_count: int = 0
    ocr_advisory_warning_count: int = 0
    technical_profile_domain_adapter_missing: bool = False
    table_caption_linked_count: int = 0
    page_cache_hits: int = 0
    page_cache_misses: int = 0
    text_line_extract_count: int = 0
    heading_count: int = 0
    list_item_count: int = 0
    code_block_count: int = 0
    hyphenation_repair_count: int = 0
    font_heading_candidate_count: int = 0
    footnote_candidate_count: int = 0
    structure_low_confidence_count: int = 0
    rag_text_block_record_count: int = 0
    rag_text_block_file_count: int = 0
    semantic_unit_record_count: int = 0
    semantic_unit_file_count: int = 0
    requirement_record_count: int = 0
    requirement_file_count: int = 0
    cross_ref_record_count: int = 0
    cross_ref_file_count: int = 0
    semantic_low_confidence_count: int = 0
    unresolved_cross_ref_count: int = 0
    normative_requirement_count: int = 0
    retrieval_chunk_record_count: int = 0
    retrieval_chunk_file_count: int = 0
    retrieval_chunk_max_token_estimate: int = 0
    retrieval_chunk_average_token_estimate: float = 0.0
    retrieval_chunk_over_target_count: int = 0
    retrieval_chunk_duplicate_source_ref_count: int = 0
    figure_rag_record_count: int = 0
    figure_rag_file_count: int = 0
    domain_unit_record_count: int = 0
    domain_unit_file_count: int = 0
    requirement_traceability_record_count: int = 0
    requirement_traceability_file_count: int = 0
    technical_table_record_count: int = 0
    technical_table_file_count: int = 0
    confidential_safe_mode: bool = False


class ImageAsset(BaseModel):
    page: int
    index: int
    path: str
    alt_text: Optional[str] = None
    caption_text: Optional[str] = None
    caption_source: Optional[str] = None
    bbox: Optional[list[float]] = None
    width: Optional[int] = None
    height: Optional[int] = None
    sha256: Optional[str] = None
    dedupe_of: Optional[str] = None
    anchor_line_index: Optional[int] = None
    anchor_top: Optional[float] = None
    source: str = "embedded"
    caption_confidence: Optional[float] = None
    crop_reason: Optional[str] = None
    crop_content_ratio: Optional[float] = None
    crop_rejected_reason: Optional[str] = None


class ExcludedImageAsset(BaseModel):
    page: int
    index: int
    reason: str
    classification: Optional[str] = None
    recovered_text: Optional[str] = None
    recovered_confidence: Optional[float] = None
    ocr_candidates: list[dict[str, Any]] = Field(default_factory=list)
    recovery_strategy: Optional[str] = None
    context_validated: bool = False
    parent_heading_index: Optional[str] = None
    bbox: Optional[list[float]] = None
    width: Optional[int] = None
    height: Optional[int] = None
    sha256: Optional[str] = None


class TableAsset(BaseModel):
    page: int
    index: int
    mode: str
    bbox: Optional[list[float]] = None
    anchor_line_index: Optional[int] = None
    anchor_top: Optional[float] = None
    quality_score: Optional[float] = None
    fallback_reasons: list[str] = Field(default_factory=list)
    caption_text: Optional[str] = None
    caption_source: Optional[str] = None
    continuation_group: Optional[str] = None
    continued_from_page: Optional[int] = None
    continued_to_page: Optional[int] = None
    continuation_confidence: Optional[float] = None
    continuation_reasons: list[str] = Field(default_factory=list)
    continuation_rejected_reasons: list[str] = Field(default_factory=list)
    continuation_features: dict[str, Any] = Field(default_factory=dict)


class NormalizedLine(BaseModel):
    page: int
    index: int
    text: str
    line_type: LineType
    top: float
    bottom: float
    x0: float
    x1: float
    font_size: Optional[float] = None
    font_family: Optional[str] = None
    font_style_hint: Optional[str] = None
    line_height: Optional[float] = None
    left_indent: Optional[float] = None
    right_indent: Optional[float] = None
    y_band: Optional[str] = None
    source_line_indices: list[int] = Field(default_factory=list)


class DedupDecision(BaseModel):
    page: int
    line_index: int
    line_type: LineType
    text: str
    reason: str


class SuppressDecision(BaseModel):
    page: int
    line_index: int
    block_type: str
    block_index: int
    reason: str


class Manifest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    schema_version: str = "1.0"
    input_file: str
    total_pages: int
    selected_pages: list[int]
    options: dict[str, Any]
    images: list[ImageAsset] = Field(default_factory=list)
    excluded_images: list[ExcludedImageAsset] = Field(default_factory=list)
    tables: list[TableAsset] = Field(default_factory=list)
    ocr_pages: list[int] = Field(default_factory=list)
    warnings: list[WarningEntry] = Field(default_factory=list)


class Report(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    schema_version: str = "1.0"
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    status: ConversionStatus
    engine_usage: dict[str, bool]
    failed_pages: list[int] = Field(default_factory=list)
    warnings: list[WarningEntry] = Field(default_factory=list)
    page_results: list[PageResult] = Field(default_factory=list)
    summary: ReportSummary = Field(default_factory=ReportSummary)


class BatchDocumentFiles(BaseModel):
    markdown: Optional[str] = None
    manifest: Optional[str] = None
    report: Optional[str] = None
    text_blocks_rag: Optional[str] = None
    semantic_units_rag: Optional[str] = None
    requirements_rag: Optional[str] = None
    cross_refs_rag: Optional[str] = None
    retrieval_chunks_rag: Optional[str] = None
    figures_rag: Optional[str] = None
    figure_descriptions_rag: Optional[str] = None
    figure_structures_rag: Optional[str] = None
    domain_units_rag: Optional[str] = None
    requirement_traceability_rag: Optional[str] = None
    technical_tables_rag: Optional[str] = None
    rag_tables_markdown: Optional[str] = None
    tables_rag_jsonl: Optional[str] = None
    sanitized_report: Optional[str] = None


class BatchDocumentResult(BaseModel):
    input_pdf: str
    status: str
    exit_code: int
    output_dir: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0
    warning_count: int = 0
    table_count: int = 0
    image_count: int = 0
    used_ocr: bool = False
    skipped: bool = False
    files: BatchDocumentFiles = Field(default_factory=BatchDocumentFiles)


class BatchReportSummary(BaseModel):
    total_documents: int = 0
    success_count: int = 0
    partial_success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0


class BatchReport(BaseModel):
    schema_version: str = "1.0"
    input_dir: str
    output_dir: str
    pdf_files: list[str] = Field(default_factory=list)
    documents: list[BatchDocumentResult] = Field(default_factory=list)
    summary: BatchReportSummary = Field(default_factory=BatchReportSummary)


class CorpusDocument(BaseModel):
    doc_id: str
    input_pdf: str
    source_sha256: str
    output_dir: str
    status: str
    selected_pages: list[int] = Field(default_factory=list)
    skipped: bool = False
    files: BatchDocumentFiles = Field(default_factory=BatchDocumentFiles)


class CorpusManifest(BaseModel):
    schema_version: str = "1.0"
    purpose: str = "rag_corpus_ingest"
    input_dir: str
    output_dir: str
    documents: list[CorpusDocument] = Field(default_factory=list)


class CorpusDiffEntry(BaseModel):
    doc_id: str
    status: str
    previous_source_sha256: Optional[str] = None
    current_source_sha256: Optional[str] = None
    previous_output_dir: Optional[str] = None
    current_output_dir: Optional[str] = None


class CorpusDiffSummary(BaseModel):
    changed_count: int = 0
    unchanged_count: int = 0
    removed_count: int = 0
    added_count: int = 0


class CorpusDiffReport(BaseModel):
    schema_version: str = "1.0"
    purpose: str = "rag_corpus_incremental_diff"
    previous_manifest: str
    current_manifest: str
    entries: list[CorpusDiffEntry] = Field(default_factory=list)
    summary: CorpusDiffSummary = Field(default_factory=CorpusDiffSummary)


class RequirementChangeImpactEntry(BaseModel):
    doc_id: str
    requirement_key: str
    requirement_id: Optional[str] = None
    status: str
    changed_fields: list[str] = Field(default_factory=list)
    previous_trace_ids: list[str] = Field(default_factory=list)
    current_trace_ids: list[str] = Field(default_factory=list)
    previous_texts: list[str] = Field(default_factory=list)
    current_texts: list[str] = Field(default_factory=list)
    previous_source_refs: list[dict[str, Any]] = Field(default_factory=list)
    current_source_refs: list[dict[str, Any]] = Field(default_factory=list)
    previous_normative_strengths: list[str] = Field(default_factory=list)
    current_normative_strengths: list[str] = Field(default_factory=list)
    previous_testability_hints: list[str] = Field(default_factory=list)
    current_testability_hints: list[str] = Field(default_factory=list)


class RequirementChangeImpactSummary(BaseModel):
    changed_count: int = 0
    removed_count: int = 0
    added_count: int = 0
    unchanged_count: int = 0
    documents_compared: int = 0
    documents_with_requirement_changes: int = 0


class RequirementChangeImpactReport(BaseModel):
    schema_version: str = "1.0"
    purpose: str = "rag_requirement_change_impact"
    previous_manifest: str
    current_manifest: str
    entries: list[RequirementChangeImpactEntry] = Field(default_factory=list)
    summary: RequirementChangeImpactSummary = Field(default_factory=RequirementChangeImpactSummary)


class IndexContractFinding(BaseModel):
    severity: str
    code: str
    target: str
    file: Optional[str] = None
    line: Optional[int] = None
    record_id: Optional[str] = None
    field: Optional[str] = None
    message: str


class IndexContractFileSummary(BaseModel):
    file: str
    exists: bool
    record_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0


class IndexContractSummary(BaseModel):
    checked_files: int = 0
    checked_records: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0


class IndexContractReport(BaseModel):
    schema_version: str = "1.0"
    purpose: str = "rag_index_contract_validation"
    status: str
    passed: bool
    output_dir: str
    targets: list[str] = Field(default_factory=list)
    summary: IndexContractSummary = Field(default_factory=IndexContractSummary)
    files: list[IndexContractFileSummary] = Field(default_factory=list)
    findings: list[IndexContractFinding] = Field(default_factory=list)


class ProvenanceIntegrityFinding(BaseModel):
    severity: str
    code: str
    file: Optional[str] = None
    line: Optional[int] = None
    record_id: Optional[str] = None
    field: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    message: str


class ProvenanceIntegrityFileSummary(BaseModel):
    file: str
    exists: bool
    record_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0


class ProvenanceIntegritySummary(BaseModel):
    checked_files: int = 0
    checked_records: int = 0
    checked_source_refs: int = 0
    resolved_source_refs: int = 0
    unresolved_source_refs: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0


class ProvenanceIntegrityReport(BaseModel):
    schema_version: str = "1.0"
    purpose: str = "rag_provenance_integrity_validation"
    status: str
    passed: bool
    output_dir: str
    summary: ProvenanceIntegritySummary = Field(default_factory=ProvenanceIntegritySummary)
    files: list[ProvenanceIntegrityFileSummary] = Field(default_factory=list)
    findings: list[ProvenanceIntegrityFinding] = Field(default_factory=list)


class ArtifactIntegrityFinding(BaseModel):
    severity: str
    code: str
    file: Optional[str] = None
    line: Optional[int] = None
    record_id: Optional[str] = None
    field: Optional[str] = None
    path: Optional[str] = None
    message: str


class ArtifactIntegrityFileSummary(BaseModel):
    file: str
    exists: bool
    record_count: int = 0
    link_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0


class ArtifactIntegritySummary(BaseModel):
    checked_files: int = 0
    checked_records: int = 0
    checked_links: int = 0
    checked_assets: int = 0
    missing_assets: int = 0
    orphan_assets: int = 0
    sidecar_count_mismatches: int = 0
    file_map_missing_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0


class ArtifactIntegrityReport(BaseModel):
    schema_version: str = "1.0"
    purpose: str = "output_artifact_integrity_validation"
    status: str
    passed: bool
    output_dir: str
    summary: ArtifactIntegritySummary = Field(default_factory=ArtifactIntegritySummary)
    files: list[ArtifactIntegrityFileSummary] = Field(default_factory=list)
    findings: list[ArtifactIntegrityFinding] = Field(default_factory=list)


class DoclingBenchmarkFinding(BaseModel):
    severity: str
    code: str
    tool: Optional[str] = None
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class DoclingBenchmarkRun(BaseModel):
    tool: str
    status: str
    output_dir: Optional[str] = None
    duration_ms: int = 0
    pages_per_second: Optional[float] = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifact_hashes: dict[str, str] = Field(default_factory=dict)
    error_code: Optional[str] = None
    advisory: Optional[str] = None


class DoclingBenchmarkSummary(BaseModel):
    compared: bool = False
    current_tool_status: str = "not_run"
    docling_status: str = "not_run"
    docling_available: bool = False
    finding_count: int = 0
    error_count: int = 0
    warning_count: int = 0


class DoclingBenchmarkReport(BaseModel):
    schema_version: str = "1.0"
    purpose: str = "docling_benchmark_comparison"
    document_label: str
    source_sha256: str
    local_only: bool = True
    raw_content_included: bool = False
    image_bytes_included: bool = False
    customer_paths_included: bool = False
    summary: DoclingBenchmarkSummary = Field(default_factory=DoclingBenchmarkSummary)
    runs: list[DoclingBenchmarkRun] = Field(default_factory=list)
    findings: list[DoclingBenchmarkFinding] = Field(default_factory=list)


class DoclingArtifactMetricDelta(BaseModel):
    metric: str
    current_tool: Optional[Any] = None
    docling: Optional[Any] = None
    delta: Optional[float] = None


class DoclingArtifactSummary(BaseModel):
    current_artifact_count: int = 0
    docling_artifact_count: int = 0
    comparable_metric_count: int = 0
    hash_match_count: int = 0
    hash_mismatch_count: int = 0


class DoclingArtifactComparisonReport(BaseModel):
    schema_version: str = "1.0"
    purpose: str = "docling_sanitized_artifact_comparison"
    document_label: str
    source_sha256: str
    local_only: bool = True
    raw_content_included: bool = False
    image_bytes_included: bool = False
    customer_paths_included: bool = False
    summary: DoclingArtifactSummary = Field(default_factory=DoclingArtifactSummary)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    metric_deltas: list[DoclingArtifactMetricDelta] = Field(default_factory=list)
    findings: list[DoclingBenchmarkFinding] = Field(default_factory=list)


class OCRBackendDependency(BaseModel):
    name: str
    kind: str
    available: bool
    detail: Optional[str] = None


class OCRBackendLanguageData(BaseModel):
    checked: bool = False
    requested: list[str] = Field(default_factory=list)
    available: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    error: Optional[str] = None


class OCRBackendProbe(BaseModel):
    backend: str
    status: str
    ready: bool
    module: Optional[str] = None
    module_available: Optional[bool] = None
    executable: Optional[str] = None
    executable_available: Optional[bool] = None
    platform_supported: bool = True
    confidence_normalization: dict[str, Any] = Field(default_factory=dict)
    language_data: OCRBackendLanguageData = Field(default_factory=OCRBackendLanguageData)
    dependencies: list[OCRBackendDependency] = Field(default_factory=list)
    hints: list[str] = Field(default_factory=list)


class OCRBackendProbeSummary(BaseModel):
    total_backend_count: int = 0
    available_backend_count: int = 0
    ready_backend_count: int = 0
    requested_languages: list[str] = Field(default_factory=list)
    ready_backends: list[str] = Field(default_factory=list)
    unavailable_backends: list[str] = Field(default_factory=list)
    recommended_backend: Optional[str] = None
    require_ready: bool = False


class OCRBackendProbeReport(BaseModel):
    schema_version: str = "1.0"
    purpose: str = "multi_ocr_backend_probe"
    ocr_lang: str = "eng"
    local_only: bool = True
    raw_content_included: bool = False
    image_bytes_included: bool = False
    customer_paths_included: bool = False
    summary: OCRBackendProbeSummary = Field(default_factory=OCRBackendProbeSummary)
    backends: list[OCRBackendProbe] = Field(default_factory=list)


class FigureDescriptionEvalFinding(BaseModel):
    severity: str
    code: str
    description_id: Optional[str] = None
    figure_id: Optional[str] = None
    chunk_id: Optional[str] = None
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class FigureDescriptionEvalSummary(BaseModel):
    figure_record_count: int = 0
    description_record_count: int = 0
    figure_description_chunk_count: int = 0
    generated_text_record_count: int = 0
    evidence_backed_record_count: int = 0
    low_confidence_count: int = 0
    missing_source_ref_count: int = 0
    missing_source_evidence_count: int = 0
    visual_pixels_interpreted_count: int = 0
    backend_invoked_count: int = 0
    missing_retrieval_chunk_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    passed: bool = True


class FigureDescriptionEvalReport(BaseModel):
    schema_version: str = "1.0"
    purpose: str = "local_figure_description_eval"
    local_only: bool = True
    raw_images_included: bool = False
    raw_pdf_text_included: bool = False
    customer_paths_included: bool = False
    min_confidence: float = 0.65
    summary: FigureDescriptionEvalSummary = Field(default_factory=FigureDescriptionEvalSummary)
    findings: list[FigureDescriptionEvalFinding] = Field(default_factory=list)


class LocalCorpusEvidenceRedactionPolicy(BaseModel):
    raw_paths_included: bool = False
    commands_included: bool = False
    document_names_included: bool = False
    query_text_included: bool = False
    source_filenames_included: bool = False
    document_label_policy: str = "order_preserving_redacted_labels"


class LocalCorpusEvidenceSummary(BaseModel):
    document_count: int = 0
    failed_document_count: int = 0
    failure_signature_count: int = 0
    conversion_failure_count: int = 0
    contract_error_count: int = 0
    contract_warning_count: int = 0
    rag_threshold_failure_count: int = 0
    budget_failure_count: int = 0


class LocalCorpusEvidenceDomain(BaseModel):
    domain_adapter: str
    ssd_agent_domain: str
    ssd_agent_spec_type: str
    document_count: int = 0
    failed_document_count: int = 0
    signature_ids: list[str] = Field(default_factory=list)


class LocalCorpusEvidenceDocument(BaseModel):
    document_label: str
    domain_adapter: str
    ssd_agent_domain: str
    ssd_agent_spec_type: str
    conversion_exit_code: Optional[int] = None
    contract_passed: Optional[bool] = None
    rag_eval_passed: Optional[bool] = None
    rag_eval_metrics: dict[str, float] = Field(default_factory=dict)
    signature_ids: list[str] = Field(default_factory=list)


class LocalCorpusEvidenceSignature(BaseModel):
    signature_id: str
    severity: str
    category: str
    domain_adapter: str
    ssd_agent_domain: str
    ssd_agent_spec_type: str
    code: Optional[str] = None
    path: Optional[str] = None
    metric: Optional[str] = None
    direction: Optional[str] = None
    document_count: int = 0
    document_labels: list[str] = Field(default_factory=list)
    observed_values: list[Any] = Field(default_factory=list)
    limits: list[Any] = Field(default_factory=list)


class LocalCorpusEvidencePack(BaseModel):
    schema_version: str = "1.0"
    purpose: str = "local_technical_corpus_evidence_pack"
    profile_label: str
    profile_fingerprint: str
    redaction_policy: LocalCorpusEvidenceRedactionPolicy = Field(default_factory=LocalCorpusEvidenceRedactionPolicy)
    summary: LocalCorpusEvidenceSummary = Field(default_factory=LocalCorpusEvidenceSummary)
    domains: list[LocalCorpusEvidenceDomain] = Field(default_factory=list)
    documents: list[LocalCorpusEvidenceDocument] = Field(default_factory=list)
    failure_signatures: list[LocalCorpusEvidenceSignature] = Field(default_factory=list)


class CorpusEvidenceHotspot(BaseModel):
    key: str
    category: Optional[str] = None
    domain_adapter: Optional[str] = None
    ssd_agent_domain: Optional[str] = None
    ssd_agent_spec_type: Optional[str] = None
    signature_count: int = 0
    document_count: int = 0
    severity_counts: dict[str, int] = Field(default_factory=dict)
    signature_ids: list[str] = Field(default_factory=list)


class CorpusEvidenceFollowupHint(BaseModel):
    hint_id: str
    priority: str
    reason: str
    categories: list[str] = Field(default_factory=list)
    matching_signature_ids: list[str] = Field(default_factory=list)


class CorpusEvidenceAnalysisSummary(BaseModel):
    document_count: int = 0
    failed_document_count: int = 0
    failure_signature_count: int = 0
    error_signature_count: int = 0
    warning_signature_count: int = 0
    followup_hint_count: int = 0


class CorpusEvidenceAnalysisReport(BaseModel):
    schema_version: str = "1.0"
    purpose: str = "corpus_evidence_signature_analysis"
    source_profile_label: str
    source_profile_fingerprint: str
    summary: CorpusEvidenceAnalysisSummary = Field(default_factory=CorpusEvidenceAnalysisSummary)
    category_hotspots: list[CorpusEvidenceHotspot] = Field(default_factory=list)
    domain_hotspots: list[CorpusEvidenceHotspot] = Field(default_factory=list)
    followup_hints: list[CorpusEvidenceFollowupHint] = Field(default_factory=list)


class CorpusEvidenceTrendSummary(BaseModel):
    baseline_signature_count: int = 0
    current_signature_count: int = 0
    added_signature_count: int = 0
    resolved_signature_count: int = 0
    persisting_signature_count: int = 0
    added_error_signature_count: int = 0


class CorpusEvidenceTrendSignature(BaseModel):
    signature_id: str
    status: str
    severity: str
    category: str
    domain_adapter: str
    ssd_agent_domain: str
    ssd_agent_spec_type: str
    code: Optional[str] = None
    metric: Optional[str] = None
    baseline_document_count: int = 0
    current_document_count: int = 0


class CorpusEvidenceTrendReport(BaseModel):
    schema_version: str = "1.0"
    purpose: str = "corpus_evidence_trend_comparison"
    baseline_profile_fingerprint: str
    current_profile_fingerprint: str
    passed_trend_gate: bool = True
    summary: CorpusEvidenceTrendSummary = Field(default_factory=CorpusEvidenceTrendSummary)
    signatures: list[CorpusEvidenceTrendSignature] = Field(default_factory=list)
