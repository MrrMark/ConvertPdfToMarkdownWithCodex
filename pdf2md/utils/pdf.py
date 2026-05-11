from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pdfplumber
from pypdf import PdfReader


class PdfOpenError(RuntimeError):
    pass


def open_pdf_reader(pdf_path: Path, password: Optional[str]) -> PdfReader:
    """Open PDF with optional password and return a ready-to-read reader."""
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:  # noqa: BLE001
        raise PdfOpenError(f"Unable to open PDF: {exc}") from exc

    if reader.is_encrypted:
        if not password:
            raise PdfOpenError("PDF is encrypted but no password was provided")
        result = reader.decrypt(password)
        if result == 0:
            raise PdfOpenError("Failed to decrypt PDF with the given password")

    return reader


@dataclass
class PdfDocumentContext:
    """Share expensive PDF handles across extraction stages for one conversion."""

    pdf_path: Path
    password: Optional[str]
    reader: PdfReader
    pdf_open_count: int = 1
    page_cache_hits: int = 0
    page_cache_misses: int = 0
    text_line_extract_count: int = 0
    _pdfplumber_pdf: Any = None
    _page_cache: dict[int, Any] | None = None
    _text_lines_cache: dict[int, list[dict]] | None = None
    _image_boxes_cache: dict[int, list[dict]] | None = None

    @classmethod
    def open(cls, pdf_path: Path, password: Optional[str]) -> "PdfDocumentContext":
        return cls(
            pdf_path=pdf_path,
            password=password,
            reader=open_pdf_reader(pdf_path, password),
        )

    def __enter__(self) -> "PdfDocumentContext":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    @property
    def total_pages(self) -> int:
        return len(self.reader.pages)

    def get_pdfplumber_pdf(self) -> Any:
        if self._pdfplumber_pdf is None:
            self._pdfplumber_pdf = pdfplumber.open(str(self.pdf_path), password=self.password)
            self.pdf_open_count += 1
        return self._pdfplumber_pdf

    def get_pdfplumber_page(self, page_number: int) -> Any:
        if self._page_cache is None:
            self._page_cache = {}
        cached = self._page_cache.get(page_number)
        if cached is not None:
            self.page_cache_hits += 1
            return cached
        pdf = self.get_pdfplumber_pdf()
        page = pdf.pages[page_number - 1]
        self._page_cache[page_number] = page
        self.page_cache_misses += 1
        return page

    def get_text_lines(self, page_number: int) -> list[dict]:
        if self._text_lines_cache is None:
            self._text_lines_cache = {}
        cached = self._text_lines_cache.get(page_number)
        if cached is not None:
            self.page_cache_hits += 1
            return cached
        page = self.get_pdfplumber_page(page_number)
        lines = page.extract_text_lines() or []
        self._text_lines_cache[page_number] = lines
        self.text_line_extract_count += 1
        return lines

    def get_image_boxes(self, page_number: int) -> list[dict]:
        if self._image_boxes_cache is None:
            self._image_boxes_cache = {}
        cached = self._image_boxes_cache.get(page_number)
        if cached is not None:
            self.page_cache_hits += 1
            return cached
        page = self.get_pdfplumber_page(page_number)
        boxes = sorted(
            (page.images or []),
            key=lambda item: (float(item.get("top", 0.0)), float(item.get("x0", 0.0))),
        )
        self._image_boxes_cache[page_number] = boxes
        return boxes

    def close(self) -> None:
        if self._pdfplumber_pdf is not None:
            self._pdfplumber_pdf.close()
            self._pdfplumber_pdf = None
        self._page_cache = None
        self._text_lines_cache = None
        self._image_boxes_cache = None
