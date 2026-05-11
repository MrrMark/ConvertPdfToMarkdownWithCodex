from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from pdf2md.constants import TextSuppressionReason
from pdf2md.extractors.text import TextLine
from pdf2md.models import SuppressDecision

DIGIT_PATTERN = re.compile(r"\d+")
WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass
class HeaderFooterRemovalResult:
    lines_by_page: dict[int, list[TextLine]] = field(default_factory=dict)
    suppressed_lines: list[SuppressDecision] = field(default_factory=list)


def _normalize_repeated_text(text: str) -> str:
    normalized = WHITESPACE_PATTERN.sub(" ", text.strip().lower())
    return DIGIT_PATTERN.sub("#", normalized)


def _is_margin_line(line: TextLine, page_height: float) -> bool:
    if page_height <= 0:
        return line.top <= 85.0 or line.bottom >= 760.0
    return line.top <= max(85.0, page_height * 0.11) or line.bottom >= page_height - max(75.0, page_height * 0.09)


def _band_for_line(line: TextLine) -> int:
    return int(round(line.top / 12.0) * 12)


def remove_repeated_header_footer(
    lines_by_page: dict[int, list[TextLine]],
    page_heights: dict[int, float],
) -> HeaderFooterRemovalResult:
    """Remove only repeated margin lines across multiple pages."""
    result = HeaderFooterRemovalResult(lines_by_page={page: list(lines) for page, lines in lines_by_page.items()})
    page_count = len(lines_by_page)
    if page_count < 3:
        return result

    threshold = max(3, math.ceil(page_count * 0.6))
    occurrences: dict[tuple[int, str], set[int]] = {}
    line_keys: dict[tuple[int, int], tuple[int, str]] = {}

    for page, lines in lines_by_page.items():
        page_height = page_heights.get(page, 0.0)
        for idx, line in enumerate(lines):
            text_key = _normalize_repeated_text(line.text)
            if not text_key or len(text_key) < 2:
                continue
            if not _is_margin_line(line, page_height):
                continue
            key = (_band_for_line(line), text_key)
            occurrences.setdefault(key, set()).add(page)
            line_keys[(page, idx)] = key

    repeated_keys = {key for key, pages in occurrences.items() if len(pages) >= threshold}
    if not repeated_keys:
        return result

    filtered: dict[int, list[TextLine]] = {}
    for page, lines in lines_by_page.items():
        kept: list[TextLine] = []
        for idx, line in enumerate(lines):
            key = line_keys.get((page, idx))
            if key in repeated_keys:
                result.suppressed_lines.append(
                    SuppressDecision(
                        page=page,
                        line_index=idx,
                        block_type="header_footer",
                        block_index=0,
                        reason=TextSuppressionReason.REPEATED_HEADER_FOOTER,
                    )
                )
                continue
            kept.append(line)
        filtered[page] = kept
    result.lines_by_page = filtered
    return result
