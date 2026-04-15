from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from pdf2md.models import ImageMode, TableMode
from pdf2md.utils.page_range import parse_page_range


class Config(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    input_pdf: Path
    output_dir: Path
    pages: Optional[str] = None
    password: Optional[str] = None
    image_mode: ImageMode = ImageMode.REFERENCED
    table_mode: TableMode = TableMode.AUTO
    force_ocr: bool = False
    keep_page_markers: bool = False
    debug: bool = False
    verbose: bool = False
    version: str = Field(default="0.1.0")
    markdown_filename: str = "document.md"
    manifest_filename: str = "manifest.json"
    report_filename: str = "report.json"
    assets_dirname: str = "assets"

    def selected_pages(self, total_pages: int) -> list[int]:
        return parse_page_range(self.pages, total_pages)
