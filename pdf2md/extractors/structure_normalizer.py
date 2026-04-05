from __future__ import annotations

import re
from dataclasses import dataclass, field

from pdf2md.extractors.text import TextLine
from pdf2md.models import DedupDecision, LineType, NormalizedLine, SuppressDecision
from pdf2md.utils.structure import classify_structure_line

SENTENCE_END_PATTERN = re.compile(r"[.:;?!]\s*$")
HYPHEN_JOIN_START_PATTERN = re.compile(r"^[A-Za-z0-9]")


@dataclass
class BlockRegion:
    block_type: str
    block_index: int
    bbox: tuple[float, float, float, float]


@dataclass
class NormalizationResult:
    lines: list[NormalizedLine] = field(default_factory=list)
    line_merge_count: int = 0
    structure_line_count: int = 0
    dedupe_count: int = 0
    suppressed_line_count: int = 0
    deduplicated_blocks: list[DedupDecision] = field(default_factory=list)
    suppressed_lines: list[SuppressDecision] = field(default_factory=list)


def _normalize_for_compare(text: str) -> str:
    return " ".join(text.lower().split())


def _intersection_area(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)
    return max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)


def _area(bbox: tuple[float, float, float, float]) -> float:
    x0, y0, x1, y1 = bbox
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _line_should_be_suppressed(
    line: TextLine,
    regions: list[BlockRegion],
) -> SuppressDecision | None:
    line_bbox = (line.x0, line.top, max(line.x1, line.x0 + 1.0), max(line.bottom, line.top + 1.0))
    line_area = _area(line_bbox)
    cx = (line_bbox[0] + line_bbox[2]) / 2.0
    cy = (line_bbox[1] + line_bbox[3]) / 2.0

    for region in regions:
        x0, y0, x1, y1 = region.bbox
        expanded = (x0 - 2.0, y0 - 2.0, x1 + 2.0, y1 + 2.0)
        center_inside = expanded[0] <= cx <= expanded[2] and expanded[1] <= cy <= expanded[3]
        inter = _intersection_area(line_bbox, region.bbox)
        union = line_area + _area(region.bbox) - inter
        iou = inter / union if union > 0 else 0.0
        if center_inside or iou >= 0.05:
            return SuppressDecision(
                page=0,
                line_index=0,
                block_type=region.block_type,
                block_index=region.block_index,
                reason="BLOCK_OVERLAP_SUPPRESSION",
            )
    return None


def _merge_text(left: str, right: str) -> str:
    left_stripped = left.rstrip()
    right_stripped = right.lstrip()
    if left_stripped.endswith("-") and HYPHEN_JOIN_START_PATTERN.match(right_stripped):
        return left_stripped[:-1] + right_stripped
    return f"{left_stripped} {right_stripped}".strip()


def normalize_page_lines(
    *,
    page: int,
    lines: list[TextLine],
    block_regions: list[BlockRegion] | None = None,
) -> NormalizationResult:
    regions = block_regions or []
    result = NormalizationResult()

    prepared: list[NormalizedLine] = []
    caption_seen: dict[str, float] = {}
    for idx, line in enumerate(lines):
        suppress = _line_should_be_suppressed(line, regions)
        if suppress is not None:
            suppress.page = page
            suppress.line_index = idx
            result.suppressed_line_count += 1
            result.suppressed_lines.append(suppress)
            continue

        line_type = classify_structure_line(line.text)
        normalized = NormalizedLine(
            page=page,
            index=idx,
            text=line.text.strip(),
            line_type=line_type,
            top=line.top,
            bottom=line.bottom,
            x0=line.x0,
            x1=line.x1,
        )
        if line_type in {LineType.FIGURE_CAPTION, LineType.TABLE_CAPTION}:
            key = _normalize_for_compare(normalized.text)
            previous_top = caption_seen.get(key)
            if previous_top is not None and abs(normalized.top - previous_top) <= 30:
                result.dedupe_count += 1
                result.deduplicated_blocks.append(
                    DedupDecision(
                        page=page,
                        line_index=idx,
                        line_type=line_type,
                        text=normalized.text,
                        reason="NEAR_DUPLICATE_CAPTION",
                    )
                )
                continue
            caption_seen[key] = normalized.top

        if line_type is not LineType.BODY_LINE:
            result.structure_line_count += 1
        prepared.append(normalized)

    merged: list[NormalizedLine] = []
    for i, current in enumerate(prepared):
        if not merged:
            merged.append(current)
            continue

        previous = merged[-1]
        next_line = prepared[i + 1] if i + 1 < len(prepared) else None
        can_merge = (
            previous.line_type is LineType.BODY_LINE
            and current.line_type is LineType.BODY_LINE
            and (next_line is None or next_line.line_type is LineType.BODY_LINE)
            and abs(previous.x0 - current.x0) <= 6.0
            and (current.top - previous.bottom) <= 18.0
            and not SENTENCE_END_PATTERN.search(previous.text)
        )
        if can_merge:
            previous.text = _merge_text(previous.text, current.text)
            previous.bottom = max(previous.bottom, current.bottom)
            previous.x1 = max(previous.x1, current.x1)
            result.line_merge_count += 1
        else:
            merged.append(current)

    result.lines = merged
    return result
