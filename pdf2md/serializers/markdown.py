from __future__ import annotations

import re

HEADING_INDEX_PATTERN = re.compile(r"^\d+(?:\.\d+)+\s+\S")
FIGURE_CAPTION_PATTERN = re.compile(r"^Figure\s+\d+\s*:", re.IGNORECASE)
TABLE_CAPTION_PATTERN = re.compile(r"^Table\s+\d+\s*:", re.IGNORECASE)


def _is_structure_line(text: str) -> bool:
    stripped = text.strip()
    return bool(
        HEADING_INDEX_PATTERN.match(stripped)
        or FIGURE_CAPTION_PATTERN.match(stripped)
        or TABLE_CAPTION_PATTERN.match(stripped)
    )


def _append_line(lines: list[str], text: str) -> None:
    if _is_structure_line(text):
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(text)
        lines.append("")
        return
    lines.append(text)


def serialize_markdown(
    page_text_lines: dict[int, list[str]],
    keep_page_markers: bool,
    page_blocks_by_page: dict[int, list[tuple[int, str]]] | None = None,
) -> str:
    """Serialize extracted page text lines and anchored blocks into markdown."""
    lines: list[str] = []
    page_blocks_by_page = page_blocks_by_page or {}

    for page in sorted(page_text_lines):
        if keep_page_markers:
            lines.append(f"<!-- page: {page} -->")
            lines.append("")

        text_lines = page_text_lines[page]
        block_entries = sorted(page_blocks_by_page.get(page, []), key=lambda item: item[0])
        block_idx = 0
        for line_idx, text_line in enumerate(text_lines):
            while block_idx < len(block_entries) and block_entries[block_idx][0] <= line_idx:
                lines.append(block_entries[block_idx][1])
                lines.append("")
                block_idx += 1
            _append_line(lines, text_line)

        while block_idx < len(block_entries):
            lines.append(block_entries[block_idx][1])
            lines.append("")
            block_idx += 1

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
