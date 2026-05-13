from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from pdf2md.models import ImageMode, RagTableOutputMode, TableMode
from pdf2md.utils.page_range import parse_page_range


class Config(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    input_pdf: Path
    output_dir: Path
    pages: Optional[str] = None
    password: Optional[str] = None
    image_mode: ImageMode = ImageMode.REFERENCED
    table_mode: TableMode = TableMode.AUTO
    rag_table_output: RagTableOutputMode = RagTableOutputMode.NONE
    force_ocr: bool = False
    ocr_lang: str = "eng"
    keep_page_markers: bool = False
    remove_header_footer: bool = False
    dedupe_images: bool = False
    repair_hyphenation: bool = False
    figure_crop_fallback: bool = False
    debug: bool = False
    verbose: bool = False
    skip_existing: bool = False
    version: str = Field(default="0.1.0")
    markdown_filename: str = "document.md"
    manifest_filename: str = "manifest.json"
    report_filename: str = "report.json"
    rag_tables_markdown_filename: str = "rag_tables.md"
    rag_tables_jsonl_filename: str = "tables_rag.jsonl"
    rag_text_blocks_jsonl_filename: str = "text_blocks_rag.jsonl"
    semantic_units_jsonl_filename: str = "semantic_units_rag.jsonl"
    requirements_jsonl_filename: str = "requirements_rag.jsonl"
    cross_refs_jsonl_filename: str = "cross_refs_rag.jsonl"
    assets_dirname: str = "assets"

    def selected_pages(self, total_pages: int) -> list[int]:
        return parse_page_range(self.pages, total_pages)


def default_output_dir_for_input(input_pdf: Path) -> Path:
    """Return the default single-file output directory for an input PDF."""
    return input_pdf.parent / f"{input_pdf.stem}_output"
