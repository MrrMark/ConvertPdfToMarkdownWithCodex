from __future__ import annotations

import re

from pdf2md.models import LineType

HEADING_INDEX_PATTERN = re.compile(r"^\d+(?:\.\d+)+\s+\S")
FIGURE_CAPTION_PATTERN = re.compile(r"^(?:Figure|Fig\.?|그림|도표)\s+\d+\s*[:.]?", re.IGNORECASE)
TABLE_CAPTION_PATTERN = re.compile(r"^(?:Table|표)\s+\d+\s*[:.]?", re.IGNORECASE)
TOC_LEADER_PATTERN = re.compile(r"\.{5,}\s*\d+\s*$")
CAPTION_NEARBY_PATTERN = re.compile(r"\b(figure|fig\.?|chart|table|그림|도표|표)\b", re.IGNORECASE)


def classify_structure_line(text: str) -> LineType:
    """Classify a normalized line conservatively for markdown spacing and dedupe."""
    normalized = text.strip()
    if TOC_LEADER_PATTERN.search(normalized):
        return LineType.TOC_LINE
    if HEADING_INDEX_PATTERN.match(normalized):
        return LineType.HEADING_INDEX
    if FIGURE_CAPTION_PATTERN.match(normalized):
        return LineType.FIGURE_CAPTION
    if TABLE_CAPTION_PATTERN.match(normalized):
        return LineType.TABLE_CAPTION
    return LineType.BODY_LINE


def is_structure_line(text: str) -> bool:
    """Return True when a line should be isolated as a structure-preserving block."""
    return classify_structure_line(text) is not LineType.BODY_LINE


def is_caption_candidate(text: str) -> bool:
    """Return True when nearby text strongly suggests a figure/table caption label."""
    return bool(CAPTION_NEARBY_PATTERN.search(text.strip()))
