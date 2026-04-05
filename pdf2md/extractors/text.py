from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pdfplumber


class TextExtractionError(RuntimeError):
    pass


@dataclass
class TextLine:
    text: str
    top: float


def normalize_text(raw_text: str) -> str:
    normalized = unicodedata.normalize("NFC", raw_text)
    lines = [line.rstrip() for line in normalized.splitlines()]
    return "\n".join(lines).strip()


def extract_page_text_layout(
    pdf_path: Path,
    selected_pages: list[int],
    password: Optional[str] = None,
) -> dict[int, list[TextLine]]:
    """Extract text lines with vertical position for anchor mapping."""
    layout: dict[int, list[TextLine]] = {}
    try:
        with pdfplumber.open(str(pdf_path), password=password) as pdf:
            for page_number in selected_pages:
                page = pdf.pages[page_number - 1]
                raw_lines = page.extract_text_lines() or []
                normalized_lines: list[TextLine] = []
                for line in raw_lines:
                    text = normalize_text(line.get("text", ""))
                    if not text:
                        continue
                    normalized_lines.append(TextLine(text=text, top=float(line.get("top", 0.0))))
                normalized_lines.sort(key=lambda item: item.top)
                layout[page_number] = normalized_lines
    except Exception as exc:  # noqa: BLE001
        raise TextExtractionError(f"Failed to extract text layout: {exc}") from exc
    return layout


def extract_page_texts(
    pdf_path: Path,
    selected_pages: list[int],
    password: Optional[str] = None,
) -> dict[int, str]:
    """Extract page text with deterministic page-index mapping."""
    page_texts: dict[int, str] = {}
    try:
        layout = extract_page_text_layout(pdf_path, selected_pages, password=password)
        for page_number in selected_pages:
            lines = layout.get(page_number, [])
            if lines:
                page_texts[page_number] = normalize_text("\n".join(item.text for item in lines))
            else:
                page_texts[page_number] = ""
    except Exception as exc:  # noqa: BLE001
        raise TextExtractionError(f"Failed to extract text: {exc}") from exc

    return page_texts
