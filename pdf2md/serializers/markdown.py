from __future__ import annotations

from pdf2md.utils.structure import is_structure_line


def _ensure_blank_line(lines: list[str]) -> None:
    if lines and lines[-1] != "":
        lines.append("")


def _append_line(lines: list[str], text: str) -> None:
    if is_structure_line(text):
        _ensure_blank_line(lines)
        lines.append(text)
        _ensure_blank_line(lines)
        return
    lines.append(text)


def _append_block(lines: list[str], block_markdown: str) -> None:
    _ensure_blank_line(lines)
    lines.append(block_markdown)
    _ensure_blank_line(lines)


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
                _append_block(lines, block_entries[block_idx][1])
                block_idx += 1
            _append_line(lines, text_line)

        while block_idx < len(block_entries):
            _append_block(lines, block_entries[block_idx][1])
            block_idx += 1

        _ensure_blank_line(lines)

    return "\n".join(lines).rstrip() + "\n"
