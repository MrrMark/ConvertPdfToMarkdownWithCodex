from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pdfplumber


class TextExtractionError(RuntimeError):
    pass


@dataclass
class TextLine:
    text: str
    top: float
    bottom: float
    x0: float
    x1: float


@dataclass
class PageLayoutMetadata:
    page: int
    reading_order_strategy: str = "top"
    column_count_estimate: int = 1
    page_width: float = 0.0
    page_height: float = 0.0
    raw_line_count: int = 0


@dataclass
class TextLayoutResult:
    lines_by_page: dict[int, list[TextLine]] = field(default_factory=dict)
    metadata_by_page: dict[int, PageLayoutMetadata] = field(default_factory=dict)
    raw_lines_by_page: dict[int, list[dict]] = field(default_factory=dict)


def normalize_text(raw_text: str) -> str:
    normalized = unicodedata.normalize("NFC", raw_text)
    lines = [line.rstrip() for line in normalized.splitlines()]
    return "\n".join(lines).strip()


def _line_width(line: TextLine) -> float:
    return max(0.0, line.x1 - line.x0)


def _is_two_column_candidate(line: TextLine, page_width: float, midpoint: float) -> bool:
    width = _line_width(line)
    if width <= 8.0:
        return False
    if width >= page_width * 0.48:
        return False
    if line.x0 < midpoint - 12.0 and line.x1 <= midpoint + 18.0:
        return True
    return line.x0 >= midpoint - 12.0


def _detect_two_column_layout(lines: list[TextLine], page_width: float) -> tuple[bool, float, float, float]:
    if page_width <= 0 or len(lines) < 8:
        return False, 0.0, 0.0, 0.0

    midpoint = page_width / 2.0
    candidates = [line for line in lines if _is_two_column_candidate(line, page_width, midpoint)]
    if len(candidates) < 8 or len(candidates) < int(len(lines) * 0.65):
        return False, 0.0, 0.0, 0.0

    left = [line for line in candidates if line.x0 < midpoint - 12.0 and line.x1 <= midpoint + 18.0]
    right = [line for line in candidates if line.x0 >= midpoint - 12.0]
    if len(left) < 4 or len(right) < 4:
        return False, 0.0, 0.0, 0.0

    max_left_x1 = max(line.x1 for line in left)
    min_right_x0 = min(line.x0 for line in right)
    column_gap = min_right_x0 - max_left_x1
    if column_gap < max(24.0, page_width * 0.04):
        return False, 0.0, 0.0, 0.0

    column_top = min(line.top for line in candidates)
    column_bottom = max(line.bottom for line in candidates)
    in_region = [line for line in lines if column_top <= line.top <= column_bottom]
    spanning_in_region = [line for line in in_region if line not in candidates and _line_width(line) >= page_width * 0.55]
    if len(spanning_in_region) > max(2, int(len(in_region) * 0.15)):
        return False, 0.0, 0.0, 0.0

    return True, midpoint, column_top, column_bottom


def order_text_lines(lines: list[TextLine], page_width: float, page_height: float) -> tuple[list[TextLine], PageLayoutMetadata]:
    """Order page lines conservatively, using column order only for clear two-column pages."""
    ordered_top = sorted(lines, key=lambda item: (item.top, item.x0))
    detected, midpoint, column_top, column_bottom = _detect_two_column_layout(ordered_top, page_width)
    if not detected:
        return ordered_top, PageLayoutMetadata(
            page=0,
            reading_order_strategy="top",
            column_count_estimate=1,
            page_width=page_width,
            page_height=page_height,
            raw_line_count=len(lines),
        )

    def key(line: TextLine) -> tuple[int, int, float, float]:
        if line.top < column_top:
            return (0, 0, line.top, line.x0)
        if line.top > column_bottom:
            return (2, 0, line.top, line.x0)
        is_left = line.x0 < midpoint - 12.0 and line.x1 <= midpoint + 18.0
        is_right = line.x0 >= midpoint - 12.0
        if is_left:
            return (1, 0, line.top, line.x0)
        if is_right:
            return (1, 1, line.top, line.x0)
        return (1, 0, line.top, line.x0)

    return sorted(ordered_top, key=key), PageLayoutMetadata(
        page=0,
        reading_order_strategy="two_column_left_to_right",
        column_count_estimate=2,
        page_width=page_width,
        page_height=page_height,
        raw_line_count=len(lines),
    )


def _raw_line_payload(line: dict) -> dict:
    return {
        "text": normalize_text(line.get("text", "")),
        "top": float(line.get("top", 0.0)),
        "bottom": float(line.get("bottom", line.get("top", 0.0))),
        "x0": float(line.get("x0", 0.0)),
        "x1": float(line.get("x1", line.get("x0", 0.0))),
    }


def _extract_page_text_layout_from_pdf(
    pdf: Any,
    selected_pages: list[int],
    text_lines_by_page: dict[int, list[dict]] | None = None,
) -> TextLayoutResult:
    result = TextLayoutResult()
    for page_number in selected_pages:
        page = pdf.pages[page_number - 1]
        raw_lines = (text_lines_by_page or {}).get(page_number)
        if raw_lines is None:
            raw_lines = page.extract_text_lines() or []
        result.raw_lines_by_page[page_number] = [_raw_line_payload(line) for line in raw_lines]
        normalized_lines: list[TextLine] = []
        for line in raw_lines:
            text = normalize_text(line.get("text", ""))
            if not text:
                continue
            top = float(line.get("top", 0.0))
            bottom = float(line.get("bottom", top))
            x0 = float(line.get("x0", 0.0))
            x1 = float(line.get("x1", x0))
            normalized_lines.append(
                TextLine(
                    text=text,
                    top=top,
                    bottom=bottom,
                    x0=x0,
                    x1=x1,
                )
            )
        ordered_lines, metadata = order_text_lines(
            normalized_lines,
            page_width=float(page.width),
            page_height=float(page.height),
        )
        metadata.page = page_number
        result.lines_by_page[page_number] = ordered_lines
        result.metadata_by_page[page_number] = metadata
    return result


def extract_page_text_layout_result(
    pdf_path: Path,
    selected_pages: list[int],
    password: Optional[str] = None,
    pdf: Any = None,
    text_lines_by_page: dict[int, list[dict]] | None = None,
) -> TextLayoutResult:
    """Extract text lines, reading order metadata, and raw line debug payloads."""
    try:
        if pdf is not None:
            return _extract_page_text_layout_from_pdf(pdf, selected_pages, text_lines_by_page=text_lines_by_page)
        with pdfplumber.open(str(pdf_path), password=password) as opened_pdf:
            return _extract_page_text_layout_from_pdf(
                opened_pdf,
                selected_pages,
                text_lines_by_page=text_lines_by_page,
            )
    except Exception as exc:  # noqa: BLE001
        raise TextExtractionError(f"Failed to extract text layout: {exc}") from exc


def extract_page_text_layout(
    pdf_path: Path,
    selected_pages: list[int],
    password: Optional[str] = None,
) -> dict[int, list[TextLine]]:
    """Extract text lines with vertical position for anchor mapping."""
    return extract_page_text_layout_result(pdf_path, selected_pages, password=password).lines_by_page


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
