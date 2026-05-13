from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from pdf2md.utils.structure import is_structure_line

NUMERIC_HEADING_PATTERN = re.compile(r"^(\d+(?:\.\d+)+)\s+(.+)$")
LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-*]\s+\S|\d+[.)]\s+\S)")
FOOTNOTE_PATTERN = re.compile(r"^\s*(?:\[\d+\]|\d+\))\s+\S")
HYPHENATED_LINE_PATTERN = re.compile(r"^(.*[A-Za-z])-\s*$")


@dataclass(frozen=True)
class MarkdownSerializationResult:
    markdown: str
    heading_count: int = 0
    list_item_count: int = 0
    code_block_count: int = 0


@dataclass(frozen=True)
class HyphenationRepairResult:
    lines: list[str]
    repair_count: int = 0


def _ensure_blank_line(lines: list[str]) -> None:
    if lines and lines[-1] != "":
        lines.append("")


def _is_numeric_heading(text: str) -> bool:
    return bool(NUMERIC_HEADING_PATTERN.match(text.strip()))


def _heading_level(text: str) -> int:
    match = NUMERIC_HEADING_PATTERN.match(text.strip())
    if match is None:
        return 0
    return min(match.group(1).count(".") + 1, 6)


def _is_list_item(text: str) -> bool:
    return bool(LIST_ITEM_PATTERN.match(text))


def _is_code_like(text: str) -> bool:
    if text.startswith("    ") or text.startswith("\t"):
        return True
    stripped = text.rstrip()
    return bool(stripped and len(re.findall(r"\S\s{2,}\S", stripped)) >= 2)


def _render_heading(text: str) -> str:
    level = _heading_level(text)
    if level == 0:
        level = 2
    return f"{'#' * level} {text.strip()}"


def repair_hyphenated_lines(text_lines: list[str]) -> HyphenationRepairResult:
    """Repair clear line-break hyphenation without changing ambiguous lines."""
    repaired: list[str] = []
    repair_count = 0
    idx = 0
    while idx < len(text_lines):
        current = text_lines[idx]
        if idx + 1 < len(text_lines):
            match = HYPHENATED_LINE_PATTERN.match(current.rstrip())
            next_line = text_lines[idx + 1]
            next_stripped = next_line.lstrip()
            if match and next_stripped and next_stripped[0].islower():
                repaired.append(f"{match.group(1)}{next_stripped}")
                repair_count += 1
                idx += 2
                continue
        repaired.append(current)
        idx += 1
    return HyphenationRepairResult(lines=repaired, repair_count=repair_count)


def _append_line(lines: list[str], text: str, result_counts: dict[str, int]) -> None:
    if _is_numeric_heading(text):
        _ensure_blank_line(lines)
        lines.append(_render_heading(text))
        _ensure_blank_line(lines)
        result_counts["heading_count"] += 1
        return
    if _is_list_item(text):
        lines.append(text)
        result_counts["list_item_count"] += 1
        return
    if FOOTNOTE_PATTERN.match(text):
        _ensure_blank_line(lines)
        lines.append(text)
        _ensure_blank_line(lines)
        return
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


def serialize_markdown_result(
    page_text_lines: dict[int, list[str]],
    keep_page_markers: bool,
    page_blocks_by_page: dict[int, list[tuple[int, str]]] | None = None,
) -> MarkdownSerializationResult:
    """Serialize extracted page text lines and anchored blocks into markdown with diagnostics."""
    lines: list[str] = []
    page_blocks_by_page = page_blocks_by_page or {}
    counts = {
        "heading_count": 0,
        "list_item_count": 0,
        "code_block_count": 0,
    }

    for page in sorted(page_text_lines):
        if keep_page_markers:
            lines.append(f"<!-- page: {page} -->")
            lines.append("")

        text_lines = page_text_lines[page]
        block_entries = sorted(page_blocks_by_page.get(page, []), key=lambda item: item[0])
        block_idx = 0
        line_idx = 0
        while line_idx < len(text_lines):
            while block_idx < len(block_entries) and block_entries[block_idx][0] <= line_idx:
                _append_block(lines, block_entries[block_idx][1])
                block_idx += 1
            text_line = text_lines[line_idx]
            if _is_code_like(text_line):
                _ensure_blank_line(lines)
                lines.append("```text")
                while line_idx < len(text_lines) and _is_code_like(text_lines[line_idx]):
                    if block_idx < len(block_entries) and block_entries[block_idx][0] <= line_idx:
                        break
                    lines.append(text_lines[line_idx].rstrip())
                    line_idx += 1
                lines.append("```")
                _ensure_blank_line(lines)
                counts["code_block_count"] += 1
            else:
                _append_line(lines, text_line, counts)
                line_idx += 1

        while block_idx < len(block_entries):
            _append_block(lines, block_entries[block_idx][1])
            block_idx += 1

        _ensure_blank_line(lines)

    return MarkdownSerializationResult(
        markdown="\n".join(lines).rstrip() + "\n",
        heading_count=counts["heading_count"],
        list_item_count=counts["list_item_count"],
        code_block_count=counts["code_block_count"],
    )


def serialize_markdown(
    page_text_lines: dict[int, list[str]],
    keep_page_markers: bool,
    page_blocks_by_page: dict[int, list[tuple[int, str]]] | None = None,
) -> str:
    """Serialize extracted page text lines and anchored blocks into markdown."""
    return serialize_markdown_result(
        page_text_lines=page_text_lines,
        keep_page_markers=keep_page_markers,
        page_blocks_by_page=page_blocks_by_page,
    ).markdown


def _append_text_block(lines: list[str], block: dict[str, Any], result_counts: dict[str, int]) -> None:
    block_type = str(block.get("block_type", "paragraph"))
    text = str(block.get("text", ""))
    if not text:
        return
    if block_type == "heading":
        _ensure_blank_line(lines)
        lines.append(_render_heading(text))
        _ensure_blank_line(lines)
        result_counts["heading_count"] += 1
        return
    if block_type == "list":
        for item in text.splitlines():
            if item.strip():
                lines.append(item)
                result_counts["list_item_count"] += 1
        return
    if block_type == "code":
        _ensure_blank_line(lines)
        lines.append("```text")
        lines.extend(item.rstrip() for item in text.splitlines())
        lines.append("```")
        _ensure_blank_line(lines)
        result_counts["code_block_count"] += 1
        return
    if block_type in {"footnote", "caption"}:
        _ensure_blank_line(lines)
        lines.extend(item for item in text.splitlines() if item.strip())
        _ensure_blank_line(lines)
        return
    lines.extend(item for item in text.splitlines() if item.strip())


def serialize_markdown_blocks_result(
    page_text_blocks: dict[int, list[dict[str, Any]]],
    keep_page_markers: bool,
    page_blocks_by_page: dict[int, list[tuple[int, str]]] | None = None,
) -> MarkdownSerializationResult:
    """Serialize RAG text blocks and anchored table/image blocks into Markdown."""
    lines: list[str] = []
    page_blocks_by_page = page_blocks_by_page or {}
    counts = {
        "heading_count": 0,
        "list_item_count": 0,
        "code_block_count": 0,
    }

    for page in sorted(page_text_blocks):
        if keep_page_markers:
            lines.append(f"<!-- page: {page} -->")
            lines.append("")

        block_entries = sorted(page_blocks_by_page.get(page, []), key=lambda item: item[0])
        block_idx = 0
        for text_block in page_text_blocks[page]:
            line_indices = text_block.get("line_indices") or [0]
            anchor_line = int(min(line_indices))
            while block_idx < len(block_entries) and block_entries[block_idx][0] <= anchor_line:
                _append_block(lines, block_entries[block_idx][1])
                block_idx += 1
            _append_text_block(lines, text_block, counts)

        while block_idx < len(block_entries):
            _append_block(lines, block_entries[block_idx][1])
            block_idx += 1

        _ensure_blank_line(lines)

    return MarkdownSerializationResult(
        markdown="\n".join(lines).rstrip() + "\n",
        heading_count=counts["heading_count"],
        list_item_count=counts["list_item_count"],
        code_block_count=counts["code_block_count"],
    )
