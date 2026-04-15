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
    summary: dict[str, Any] = Field(default_factory=dict)
