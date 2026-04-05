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
    GFM_ONLY = "gfm-only"
    HTML_ONLY = "html-only"


class WarningEntry(BaseModel):
    code: str
    message: str
    page: Optional[int] = None
    details: dict[str, Any] = Field(default_factory=dict)


class PageResult(BaseModel):
    page: int
    status: str = "success"
    char_count: int = 0
    warning_count: int = 0
    used_ocr: bool = False
    ocr_confidence: Optional[float] = None


class ImageAsset(BaseModel):
    page: int
    index: int
    path: str
    bbox: Optional[list[float]] = None
    width: Optional[int] = None
    height: Optional[int] = None
    sha256: Optional[str] = None


class TableAsset(BaseModel):
    page: int
    index: int
    mode: str
    bbox: Optional[list[float]] = None


class Manifest(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    input_file: str
    total_pages: int
    selected_pages: list[int]
    options: dict[str, Any]
    images: list[ImageAsset] = Field(default_factory=list)
    tables: list[TableAsset] = Field(default_factory=list)
    ocr_pages: list[int] = Field(default_factory=list)
    warnings: list[WarningEntry] = Field(default_factory=list)


class Report(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    started_at: datetime
    finished_at: datetime
    duration_ms: int
    status: str
    engine_usage: dict[str, bool]
    failed_pages: list[int] = Field(default_factory=list)
    warnings: list[WarningEntry] = Field(default_factory=list)
    page_results: list[PageResult] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
