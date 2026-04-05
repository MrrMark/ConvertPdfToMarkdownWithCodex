from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Optional

import pdfplumber


class TextExtractionError(RuntimeError):
    pass


def normalize_text(raw_text: str) -> str:
    normalized = unicodedata.normalize("NFC", raw_text)
    lines = [line.rstrip() for line in normalized.splitlines()]
    return "\n".join(lines).strip()


def extract_page_texts(
    pdf_path: Path,
    selected_pages: list[int],
    password: Optional[str] = None,
) -> dict[int, str]:
    """Extract page text with deterministic page-index mapping."""
    page_texts: dict[int, str] = {}
    try:
        with pdfplumber.open(str(pdf_path), password=password) as pdf:
            for page_number in selected_pages:
                page = pdf.pages[page_number - 1]
                raw_text = page.extract_text() or ""
                page_texts[page_number] = normalize_text(raw_text)
    except Exception as exc:  # noqa: BLE001
        raise TextExtractionError(f"Failed to extract text: {exc}") from exc

    return page_texts
