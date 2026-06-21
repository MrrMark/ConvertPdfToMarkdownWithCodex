from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import json
import re
from typing import Any

from pdf2md.models import LineType, NormalizedLine


FOOTNOTE_MARKER_PATTERN = re.compile(r"^\s*(?:\[\d+\]|\d+[.)])\s+\S")
NUMERIC_HEADING_PATTERN = re.compile(r"^(\d+(?:\.\d+)*)\s+\S")
CODE_TOKEN_PATTERN = re.compile(r"(?:[{};=]|\b(?:def|class|return|const|let|var)\b)")
SENTENCE_END_PATTERN = re.compile(r"[.!?。]\s*$")


@dataclass
class TextBlock:
    page: int
    block_index: int
    block_type: str
    text: str
    bbox: list[float]
    line_indices: list[int]
    heading_path: list[str]
    parent_heading_block_id: str | None
    classification_confidence: float
    classification_reasons: list[str] = field(default_factory=list)

    @property
    def block_id(self) -> str:
        return f"page-{self.page:04d}-block-{self.block_index:04d}"

    def to_record(self) -> dict[str, Any]:
        return {
            "block_id": self.block_id,
            "page": self.page,
            "block_index": self.block_index,
            "block_type": self.block_type,
            "text": self.text,
            "bbox": self.bbox,
            "line_indices": self.line_indices,
            "heading_path": self.heading_path,
            "parent_heading_block_id": self.parent_heading_block_id,
            "classification_confidence": self.classification_confidence,
            "classification_reasons": self.classification_reasons,
        }


@dataclass
class TextBlockBuildResult:
    blocks_by_page: dict[int, list[TextBlock]] = field(default_factory=dict)
    records: list[dict[str, Any]] = field(default_factory=list)
    font_heading_candidate_count: int = 0
    footnote_candidate_count: int = 0
    structure_low_confidence_count: int = 0


@dataclass(frozen=True)
class _LineClassification:
    block_type: str
    confidence: float
    reasons: list[str]
    low_confidence: bool = False
    font_heading_candidate: bool = False
    footnote_candidate: bool = False


def _body_font_size(lines: list[NormalizedLine]) -> float | None:
    sizes = [
        float(line.font_size)
        for line in lines
        if line.font_size is not None and line.line_type is LineType.BODY_LINE and line.y_band != "bottom"
    ]
    if not sizes:
        sizes = [float(line.font_size) for line in lines if line.font_size is not None]
    if not sizes:
        return None
    counts = Counter(round(size, 2) for size in sizes)
    return float(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0])


def _font_heading_level(text: str) -> int:
    match = NUMERIC_HEADING_PATTERN.match(text.strip())
    if match is None:
        return 1
    return min(match.group(1).count(".") + 1, 6)


def _line_gap_before(lines: list[NormalizedLine], idx: int) -> float | None:
    if idx <= 0:
        return None
    return max(0.0, lines[idx].top - lines[idx - 1].bottom)


def _line_gap_after(lines: list[NormalizedLine], idx: int) -> float | None:
    if idx + 1 >= len(lines):
        return None
    return max(0.0, lines[idx + 1].top - lines[idx].bottom)


def _is_font_heading_candidate(line: NormalizedLine, body_size: float | None, page_line_count: int) -> bool:
    if line.font_size is None:
        return False
    if line.line_type in {LineType.FIGURE_CAPTION, LineType.TABLE_CAPTION, LineType.TOC_LINE, LineType.LIST_ITEM}:
        return False
    text = line.text.strip()
    if not text or len(text) > 120 or SENTENCE_END_PATTERN.search(text):
        return False
    if page_line_count == 1:
        return float(line.font_size) >= 16.0
    if body_size is None:
        return False
    return float(line.font_size) >= max(body_size * 1.35, body_size + 3.0)


def _is_code_line(line: NormalizedLine) -> bool:
    style = (line.font_style_hint or "").lower()
    if "monospace" in style:
        return True
    return (line.left_indent or 0.0) >= 96.0 and CODE_TOKEN_PATTERN.search(line.text) is not None


def _classify_line(
    lines: list[NormalizedLine],
    idx: int,
    body_size: float | None,
) -> _LineClassification:
    line = lines[idx]
    if line.line_type in {LineType.FIGURE_CAPTION, LineType.TABLE_CAPTION}:
        return _LineClassification("caption", 1.0, ["explicit_caption"])
    if line.line_type is LineType.HEADING_INDEX:
        return _LineClassification("heading", 1.0, ["numeric_heading"])
    if line.line_type is LineType.LIST_ITEM:
        return _LineClassification("list", 0.95, ["explicit_list_marker"])
    if _is_code_line(line):
        return _LineClassification("code", 0.9, ["monospace_or_indented_code"])

    footnote_candidate = bool(FOOTNOTE_MARKER_PATTERN.match(line.text))
    if footnote_candidate:
        small_font = body_size is not None and line.font_size is not None and float(line.font_size) <= body_size * 0.92
        if line.y_band == "bottom" and small_font:
            return _LineClassification("footnote", 0.9, ["bottom_band", "small_font", "footnote_marker"], footnote_candidate=True)
        return _LineClassification(
            "paragraph",
            0.55,
            ["ambiguous_footnote_marker"],
            low_confidence=True,
            footnote_candidate=True,
        )

    if _is_font_heading_candidate(line, body_size, len(lines)):
        gap_before = _line_gap_before(lines, idx)
        gap_after = _line_gap_after(lines, idx)
        has_whitespace = (gap_before is None or gap_before >= body_size * 1.2) and (
            gap_after is None or gap_after >= body_size * 1.2
        )
        if has_whitespace:
            return _LineClassification(
                "heading",
                0.88,
                ["large_font", "surrounding_whitespace"],
                font_heading_candidate=True,
            )
        return _LineClassification(
            "paragraph",
            0.55,
            ["large_font_without_heading_spacing"],
            low_confidence=True,
            font_heading_candidate=True,
        )

    return _LineClassification("paragraph", 0.75, ["default_paragraph"])


def _block_bbox(lines: list[NormalizedLine]) -> list[float]:
    return [
        round(min(line.x0 for line in lines), 2),
        round(min(line.top for line in lines), 2),
        round(max(line.x1 for line in lines), 2),
        round(max(line.bottom for line in lines), 2),
    ]


def _line_indices(lines: list[NormalizedLine]) -> list[int]:
    indices: list[int] = []
    for line in lines:
        if line.source_line_indices:
            indices.extend(line.source_line_indices)
        else:
            indices.append(line.index)
    return sorted(dict.fromkeys(indices))


def _make_block(
    *,
    page: int,
    block_index: int,
    block_type: str,
    lines: list[NormalizedLine],
    confidence: float,
    reasons: list[str],
    heading_path: list[str],
    parent_heading_block_id: str | None,
) -> TextBlock:
    return TextBlock(
        page=page,
        block_index=block_index,
        block_type=block_type,
        text="\n".join(line.text for line in lines),
        bbox=_block_bbox(lines),
        line_indices=_line_indices(lines),
        heading_path=list(heading_path),
        parent_heading_block_id=parent_heading_block_id,
        classification_confidence=round(confidence, 2),
        classification_reasons=sorted(dict.fromkeys(reasons)),
    )


def build_text_blocks(lines_by_page: dict[int, list[NormalizedLine]]) -> TextBlockBuildResult:
    """Build conservative text structure blocks for RAG ingestion."""
    result = TextBlockBuildResult()
    heading_path: list[str] = []
    heading_ids_by_level: dict[int, str] = {}

    for page in sorted(lines_by_page):
        lines = lines_by_page[page]
        body_size = _body_font_size(lines)
        page_blocks: list[TextBlock] = []
        idx = 0
        while idx < len(lines):
            classification = _classify_line(lines, idx, body_size)
            result.font_heading_candidate_count += int(classification.font_heading_candidate)
            result.footnote_candidate_count += int(classification.footnote_candidate)
            result.structure_low_confidence_count += int(classification.low_confidence)

            grouped = [lines[idx]]
            idx += 1
            if classification.block_type in {"list", "code", "footnote"}:
                while idx < len(lines):
                    next_classification = _classify_line(lines, idx, body_size)
                    if next_classification.block_type != classification.block_type:
                        break
                    result.font_heading_candidate_count += int(next_classification.font_heading_candidate)
                    result.footnote_candidate_count += int(next_classification.footnote_candidate)
                    result.structure_low_confidence_count += int(next_classification.low_confidence)
                    grouped.append(lines[idx])
                    idx += 1

            block_index = len(page_blocks) + 1
            block_heading_path = heading_path
            if classification.block_type == "heading":
                level = _font_heading_level(grouped[0].text)
                parent_levels = [key for key in heading_ids_by_level if key < level]
                parent_id = heading_ids_by_level[max(parent_levels)] if parent_levels else None
                heading_path = heading_path[: max(level - 1, 0)] + [grouped[0].text]
                for stale_level in [key for key in heading_ids_by_level if key >= level]:
                    del heading_ids_by_level[stale_level]
                block_heading_path = heading_path
            else:
                parent_id = heading_ids_by_level[max(heading_ids_by_level)] if heading_ids_by_level else None

            block = _make_block(
                page=page,
                block_index=block_index,
                block_type=classification.block_type,
                lines=grouped,
                confidence=classification.confidence,
                reasons=classification.reasons,
                heading_path=block_heading_path,
                parent_heading_block_id=parent_id,
            )
            page_blocks.append(block)
            if classification.block_type == "heading":
                heading_ids_by_level[_font_heading_level(grouped[0].text)] = block.block_id

        result.blocks_by_page[page] = page_blocks
        result.records.extend(block.to_record() for block in page_blocks)

    return result


def serialize_text_blocks_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
