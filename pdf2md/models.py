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
    line_merge_count: int = 0
    structure_line_count: int = 0
    dedupe_count: int = 0
    suppressed_line_count: int = 0


class ReportSummary(BaseModel):
    processed_pages: int = 0
    warning_count: int = 0
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
    anchor_line_index: Optional[int] = None
    anchor_top: Optional[float] = None


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


class NormalizedLine(BaseModel):
    page: int
    index: int
    text: str
    line_type: LineType
    top: float
    bottom: float
    x0: float
    x1: float


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
