from __future__ import annotations

import html
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pdfplumber

from pdf2md.constants import TableModeEmission, TableReason, WarningCode
from pdf2md.models import TableAsset, TableMode, WarningEntry

TABLE_STRATEGIES: list[tuple[str, dict[str, Any] | None]] = [
    ("default", None),
    (
        "lines_strict",
        {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 3,
            "join_tolerance": 3,
        },
    ),
    (
        "mixed_lines_text",
        {
            "vertical_strategy": "lines",
            "horizontal_strategy": "text",
            "min_words_horizontal": 1,
            "text_tolerance": 2,
        },
    ),
]
logger = logging.getLogger(__name__)


@dataclass
class TableQualityMetrics:
    selected_strategy: str
    empty_cell_ratio: float
    all_empty_rows_removed: int
    columns_compacted: int
    columns_merged: int
    quality_score: float
    data_density: float
    header_fill_ratio: float


@dataclass
class TableRecoveryDecision:
    unresolved: bool
    reasons: list[str]


@dataclass
class TableExtractionCandidate:
    strategy: str
    bbox: tuple[float, float, float, float]
    rows: list[list[str]]
    notes: list[str]
    quality_score: float
    metrics: TableQualityMetrics
    decision: TableRecoveryDecision


@dataclass
class TableBlock:
    page: int
    index: int
    mode: str
    markdown: str
    top: float
    bbox: tuple[float, float, float, float]


@dataclass
class TableExtractionResult:
    warnings: list[WarningEntry] = field(default_factory=list)
    assets: list[TableAsset] = field(default_factory=list)
    blocks_by_page: dict[int, list[TableBlock]] = field(default_factory=dict)
    table_quality: list[dict[str, Any]] = field(default_factory=list)
    fallbacks: list[dict[str, Any]] = field(default_factory=list)
    table_counts: dict[str, int] = field(
        default_factory=lambda: {
            "table_total": 0,
            "table_html_count": 0,
            "table_gfm_count": 0,
            "table_recovered_count": 0,
            "table_unresolved_count": 0,
            "table_markdown_forced_count": 0,
            "table_html_forced_count": 0,
        }
    )


def _sanitize_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\t", " ")
    return " ".join(text.split()).strip()


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    x0, y0, x1, y1 = bbox
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _bbox_intersection(
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


def _is_contained(inner: tuple[float, float, float, float], outer: tuple[float, float, float, float]) -> bool:
    ix = _bbox_intersection(inner, outer)
    ia = _bbox_area(inner)
    return ia > 0 and (ix / ia) >= 0.9


def _normalize_rows(raw_rows: list[list[str]]) -> list[list[str]]:
    cleaned = [[_sanitize_cell(cell) for cell in row] for row in raw_rows if row is not None]
    if not cleaned:
        return []
    width = max(len(row) for row in cleaned)
    if width == 0:
        return []
    return [row + [""] * (width - len(row)) for row in cleaned]


def _is_all_empty_row(row: list[str]) -> bool:
    return all(not cell.strip() for cell in row)


def _empty_ratio(rows: list[list[str]]) -> float:
    if not rows or not rows[0]:
        return 1.0
    width = len(rows[0])
    total = len(rows) * width
    empty = sum(1 for row in rows for cell in row if not cell.strip())
    return empty / total if total else 1.0


def _column_non_empty_counts(rows: list[list[str]]) -> list[int]:
    if not rows or not rows[0]:
        return []
    width = len(rows[0])
    counts = [0] * width
    for row in rows:
        for idx, cell in enumerate(row):
            if cell.strip():
                counts[idx] += 1
    return counts


def _compact_columns(rows: list[list[str]]) -> tuple[list[list[str]], int]:
    if not rows or not rows[0]:
        return rows, 0
    counts = _column_non_empty_counts(rows)
    keep = [idx for idx, value in enumerate(counts) if value > 0]
    if not keep:
        return rows, 0
    if len(keep) == len(rows[0]):
        return rows, 0
    compacted = [[row[idx] for idx in keep] for row in rows]
    return compacted, len(rows[0]) - len(keep)


def _merge_columns(rows: list[list[str]]) -> tuple[list[list[str]], int]:
    if not rows or len(rows[0]) < 3:
        return rows, 0
    merged_count = 0
    current = rows
    while True:
        width = len(current[0])
        counts = _column_non_empty_counts(current)
        merge_idx: int | None = None
        for idx in range(width - 1):
            left_count = counts[idx]
            right_count = counts[idx + 1]
            high = max(left_count, right_count)
            low = min(left_count, right_count)
            if high == 0:
                continue
            # conservative merge: one sparse neighbor and one informative neighbor
            if low > math.ceil(len(current) * 0.3):
                continue
            if high < max(2, math.ceil(len(current) * 0.5)):
                continue
            complement_ok = True
            for row in current:
                left = bool(row[idx].strip())
                right = bool(row[idx + 1].strip())
                if left and right:
                    complement_ok = False
                    break
            if complement_ok:
                merge_idx = idx
                break
        if merge_idx is None:
            break
        next_rows: list[list[str]] = []
        for row in current:
            left = row[merge_idx].strip()
            right = row[merge_idx + 1].strip()
            combined = left if left and not right else right if right and not left else left
            next_row = row[:merge_idx] + [combined] + row[merge_idx + 2 :]
            next_rows.append(next_row)
        current = next_rows
        merged_count += 1
        if len(current[0]) <= 2:
            break
    return current, merged_count


def _realign_header_columns(rows: list[list[str]]) -> tuple[list[list[str]], int]:
    if len(rows) < 2 or not rows[0]:
        return rows, 0
    header = rows[0][:]
    body = [row[:] for row in rows[1:]]
    width = len(header)
    shifts = 0

    for idx in range(width):
        head = header[idx].strip()
        if not head:
            continue
        body_non_empty_curr = sum(1 for row in body if row[idx].strip())
        if body_non_empty_curr > 0:
            continue

        left_count = sum(1 for row in body if idx > 0 and row[idx - 1].strip()) if idx > 0 else 0
        right_count = sum(1 for row in body if idx + 1 < width and row[idx + 1].strip()) if idx + 1 < width else 0
        target: int | None = None

        if idx > 0 and left_count > 0 and not header[idx - 1].strip() and left_count >= right_count:
            target = idx - 1
        elif idx + 1 < width and right_count > 0 and not header[idx + 1].strip():
            target = idx + 1
        elif idx > 0 and left_count > 0 and not header[idx - 1].strip():
            target = idx - 1

        if target is None:
            continue
        header[target] = head
        header[idx] = ""
        shifts += 1

    realigned = [header] + body
    return realigned, shifts


def _split_notes(rows: list[list[str]]) -> tuple[list[list[str]], list[str], int]:
    if len(rows) < 2:
        return rows, [], 0
    header = rows[0]
    body = rows[1:]
    clean_body: list[list[str]] = []
    notes: list[str] = []
    removed = 0
    for row in body:
        non_empty = [cell for cell in row if cell.strip()]
        if not non_empty:
            removed += 1
            continue
        joined = " ".join(non_empty)
        if joined.lower().startswith("notes:") or joined.lower().startswith("note:"):
            notes.append(joined)
            continue
        clean_body.append(row)
    return [header] + clean_body, notes, removed


def _header_fill_ratio(rows: list[list[str]]) -> float:
    if not rows or not rows[0]:
        return 0.0
    header = rows[0]
    return sum(1 for cell in header if cell.strip()) / len(header)


def _data_density(rows: list[list[str]]) -> float:
    if len(rows) <= 1 or not rows[0]:
        return 0.0
    body = rows[1:]
    width = len(rows[0])
    non_empty = sum(1 for row in body for cell in row if cell.strip())
    total = len(body) * width
    return non_empty / total if total else 0.0


def _column_consistency(rows: list[list[str]]) -> float:
    if not rows:
        return 0.0
    width = len(rows[0]) if rows[0] else 0
    if width == 0:
        return 0.0
    good = sum(1 for row in rows if len(row) == width)
    return good / len(rows)


def _quality_score(rows: list[list[str]], removed_rows: int, compacted: int, merged: int) -> float:
    empty_cell_ratio = _empty_ratio(rows)
    all_empty_row_ratio = removed_rows / max(len(rows), 1)
    header_fill = _header_fill_ratio(rows)
    consistency = _column_consistency(rows)
    data_density = _data_density(rows)
    score = (
        0.35 * (1.0 - empty_cell_ratio)
        + 0.2 * (1.0 - all_empty_row_ratio)
        + 0.15 * header_fill
        + 0.15 * consistency
        + 0.15 * data_density
    )
    if compacted > 0:
        score += min(compacted * 0.02, 0.06)
    if merged > 0:
        score += min(merged * 0.015, 0.045)
    return max(0.0, min(score, 1.0))


def analyze_table_complexity(rows: list[list[str]]) -> tuple[bool, list[str]]:
    reasons: set[str] = set()
    if not rows:
        return False, [TableReason.AMBIGUOUS_GRID]
    if len(rows) < 2:
        reasons.add(TableReason.AMBIGUOUS_GRID)

    width = len(rows[0]) if rows and rows[0] else 0
    if width < 2:
        reasons.add(TableReason.AMBIGUOUS_GRID)
    if width > 12:
        reasons.add(TableReason.SPARSE_LAYOUT)

    if _header_fill_ratio(rows) < 0.4 and width >= 3:
        reasons.add(TableReason.HEADER_FRAGMENTED)

    density = _data_density(rows)
    if density < 0.3:
        reasons.add(TableReason.LOW_DATA_DENSITY)

    empty_ratio = _empty_ratio(rows)
    if empty_ratio > 0.55:
        reasons.add(TableReason.SPARSE_LAYOUT)
    if empty_ratio > 0.75:
        reasons.add(TableReason.AMBIGUOUS_GRID)

    for row in rows:
        if len(row) != width:
            reasons.add(TableReason.AMBIGUOUS_GRID)
            break
        if any("\n" in cell for cell in row):
            reasons.add(TableReason.MULTILINE_CELL)
        if any(len(cell.strip()) > 120 for cell in row):
            reasons.add(TableReason.AMBIGUOUS_GRID)

    return len(reasons) == 0, sorted(reasons)


def is_simple_table(rows: list[list[str]]) -> bool:
    return analyze_table_complexity(rows)[0]


def _serialize_gfm(rows: list[list[str]]) -> str:
    def render_cell(cell: str) -> str:
        return cell.replace("\n", "<br>").replace("|", "\\|")

    header = rows[0]
    body = rows[1:]
    lines: list[str] = []
    lines.append("| " + " | ".join(render_cell(cell) for cell in header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for row in body:
        lines.append("| " + " | ".join(render_cell(cell) for cell in row) + " |")
    return "\n".join(lines)


def _serialize_html(rows: list[list[str]], notes: list[str]) -> str:
    if not rows:
        return "<table></table>"
    lines: list[str] = ["<table>", "  <thead>", "    <tr>"]
    for cell in rows[0]:
        lines.append(f"      <th>{html.escape(cell, quote=True)}</th>")
    lines.extend(["    </tr>", "  </thead>", "  <tbody>"])
    for row in rows[1:]:
        lines.append("    <tr>")
        for cell in row:
            lines.append(f"      <td>{html.escape(cell, quote=True)}</td>")
        lines.append("    </tr>")
    lines.append("  </tbody>")
    if notes:
        lines.append("  <tfoot>")
        col_span = len(rows[0])
        for note in notes:
            lines.append("    <tr>")
            lines.append(f'      <td colspan="{col_span}">{html.escape(note, quote=True)}</td>')
            lines.append("    </tr>")
        lines.append("  </tfoot>")
    lines.append("</table>")
    return "\n".join(lines)


def _pick_mode(table_mode: TableMode, rows: list[list[str]]) -> tuple[str, Optional[str], list[str]]:
    simple, reasons = analyze_table_complexity(rows)
    if table_mode in {TableMode.HTML, TableMode.HTML_ONLY}:
        return TableModeEmission.HTML, None, reasons
    if table_mode == TableMode.MARKDOWN:
        return TableModeEmission.MARKDOWN, None, reasons
    if table_mode == TableMode.GFM_ONLY:
        if simple:
            return TableModeEmission.GFM, None, reasons
        reason_text = ",".join(reasons) if reasons else TableReason.AMBIGUOUS_GRID
        return TableModeEmission.HTML, f"Requested gfm-only but table was unsafe for GFM ({reason_text}); used HTML fallback.", reasons
    if simple:
        return TableModeEmission.GFM, None, reasons
    return TableModeEmission.HTML, None, reasons


def _fill_blank_headers(rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        return rows
    header = [cell if cell.strip() else f"Column {idx + 1}" for idx, cell in enumerate(rows[0])]
    return [header] + [row[:] for row in rows[1:]]


def _drop_empty_body_rows(rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        return rows
    header = rows[0][:]
    body = [row[:] for row in rows[1:] if any(cell.strip() for cell in row)]
    return [header] + body


def _ensure_rectangular(rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        return [["Column 1"], [""]]
    width = max(len(row) for row in rows)
    if width == 0:
        return [["Column 1"], [""]]
    rectangular = [row + [""] * (width - len(row)) for row in rows]
    if len(rectangular) == 1:
        rectangular.append([""] * width)
    return rectangular


def _prepare_forced_markdown_rows(rows: list[list[str]]) -> list[list[str]]:
    prepared = [row[:] for row in rows]
    prepared = _ensure_rectangular(prepared)
    prepared = _drop_empty_body_rows(prepared)
    prepared, _ = _compact_columns(prepared)
    prepared = _ensure_rectangular(prepared)
    prepared = _fill_blank_headers(prepared)
    return prepared


def _serialize_markdown_forced(rows: list[list[str]], notes: list[str]) -> str:
    prepared = _prepare_forced_markdown_rows(rows)
    rendered = _serialize_gfm(prepared)
    if not notes:
        return rendered
    note_lines = [note for note in notes if note.strip()]
    if not note_lines:
        return rendered
    return rendered + "\n\n" + "\n".join(note_lines)


def _candidate_rank(
    page: pdfplumber.page.Page,
    bbox: tuple[float, float, float, float],
    quality_score: float,
) -> float:
    area = _bbox_area(bbox)
    page_area = float(page.width * page.height)
    area_ratio = (area / page_area) if page_area > 0 else 0.0
    return quality_score + min(area_ratio * 0.2, 0.1)


def _is_fragment_candidate(
    candidate: TableExtractionCandidate,
    accepted: TableExtractionCandidate,
) -> bool:
    cand_w = len(candidate.rows[0]) if candidate.rows and candidate.rows[0] else 0
    cand_h = len(candidate.rows)
    acc_w = len(accepted.rows[0]) if accepted.rows and accepted.rows[0] else 0
    acc_h = len(accepted.rows)
    if cand_w >= acc_w or cand_h > acc_h:
        return False
    inter = _bbox_intersection(candidate.bbox, accepted.bbox)
    min_area = min(_bbox_area(candidate.bbox), _bbox_area(accepted.bbox))
    overlap = (inter / min_area) if min_area > 0 else 0.0
    if overlap < 0.35:
        return False
    if candidate.quality_score > accepted.quality_score:
        return False
    # conservative suppression for narrow fragments
    return cand_w <= 1 or (cand_w <= 2 and cand_h <= 3 and acc_w >= 3)


def _process_rows(raw_rows: list[list[str]], strategy: str) -> tuple[list[list[str]], list[str], TableQualityMetrics]:
    rows = _normalize_rows(raw_rows)
    if not rows:
        metrics = TableQualityMetrics(
            selected_strategy=strategy,
            empty_cell_ratio=1.0,
            all_empty_rows_removed=0,
            columns_compacted=0,
            columns_merged=0,
            quality_score=0.0,
            data_density=0.0,
            header_fill_ratio=0.0,
        )
        return [], [], metrics

    rows, compacted = _compact_columns(rows)
    rows, header_shifts = _realign_header_columns(rows)
    rows, merged = _merge_columns(rows)
    rows, notes, removed_rows = _split_notes(rows)
    rows, extra_compacted = _compact_columns(rows)
    compacted += extra_compacted

    metrics = TableQualityMetrics(
        selected_strategy=strategy,
        empty_cell_ratio=round(_empty_ratio(rows), 4),
        all_empty_rows_removed=removed_rows,
        columns_compacted=compacted,
        columns_merged=merged + header_shifts,
        quality_score=round(_quality_score(rows, removed_rows, compacted, merged), 4),
        data_density=round(_data_density(rows), 4),
        header_fill_ratio=round(_header_fill_ratio(rows), 4),
    )
    return rows, notes, metrics


def _collect_candidates_for_page(page: pdfplumber.page.Page) -> list[TableExtractionCandidate]:
    candidates_by_bbox: dict[tuple[float, float, float, float], TableExtractionCandidate] = {}
    for strategy, table_settings in TABLE_STRATEGIES:
        raw_candidates = page.find_tables() if table_settings is None else page.find_tables(table_settings=table_settings)
        for table_obj in raw_candidates or []:
            raw_rows = table_obj.extract() or []
            rows, notes, metrics = _process_rows(raw_rows, strategy)
            if not rows or not rows[0]:
                continue
            simple, reasons = analyze_table_complexity(rows)
            candidate = TableExtractionCandidate(
                strategy=strategy,
                bbox=tuple(float(v) for v in table_obj.bbox),
                rows=rows,
                notes=notes,
                quality_score=metrics.quality_score,
                metrics=metrics,
                decision=TableRecoveryDecision(unresolved=not simple, reasons=reasons),
            )
            bbox_key = tuple(round(v, 1) for v in candidate.bbox)
            previous = candidates_by_bbox.get(bbox_key)
            if previous is None or candidate.quality_score > previous.quality_score:
                candidates_by_bbox[bbox_key] = candidate
            elif previous is not None and candidate.quality_score == previous.quality_score:
                prev_rank = next(i for i, (name, _) in enumerate(TABLE_STRATEGIES) if name == previous.strategy)
                curr_rank = next(i for i, (name, _) in enumerate(TABLE_STRATEGIES) if name == candidate.strategy)
                if curr_rank < prev_rank:
                    candidates_by_bbox[bbox_key] = candidate
    return list(candidates_by_bbox.values())


def _prune_candidates(
    page: pdfplumber.page.Page,
    candidates: list[TableExtractionCandidate],
) -> list[TableExtractionCandidate]:
    ranked = list(candidates)
    ranked.sort(
        key=lambda item: (_candidate_rank(page, item.bbox, item.quality_score), _bbox_area(item.bbox)),
        reverse=True,
    )
    deduped: list[TableExtractionCandidate] = []
    for item in ranked:
        if any(_is_contained(item.bbox, prev.bbox) for prev in deduped):
            continue
        deduped.append(item)
        if len(deduped) >= 20:
            break
    deduped.sort(key=lambda item: item.bbox[1])
    pruned: list[TableExtractionCandidate] = []
    for item in deduped:
        if any(_is_fragment_candidate(item, accepted) for accepted in pruned):
            continue
        pruned.append(item)
    refined: list[TableExtractionCandidate] = []
    for item in pruned:
        width = len(item.rows[0]) if item.rows and item.rows[0] else 0
        height = len(item.rows)
        if width == 1 and height <= 2:
            fragment_text = " ".join(cell.strip() for row in item.rows for cell in row if cell.strip()).lower()
            has_better_neighbor = False
            for other in pruned:
                if other is item:
                    continue
                other_width = len(other.rows[0]) if other.rows and other.rows[0] else 0
                if other_width <= 1:
                    continue
                same_page_band = abs(item.bbox[1] - other.bbox[1]) <= 90 or abs(item.bbox[3] - other.bbox[1]) <= 60
                x_overlap = _bbox_intersection(item.bbox, other.bbox) > 0 or (
                    min(item.bbox[2], other.bbox[2]) - max(item.bbox[0], other.bbox[0]) > 20
                )
                if not (same_page_band and x_overlap):
                    continue
                other_text = " ".join(cell.strip() for row in other.rows for cell in row if cell.strip()).lower()
                if fragment_text and fragment_text in other_text:
                    has_better_neighbor = True
                    break
            if has_better_neighbor:
                continue
        refined.append(item)
    return refined


def extract_tables(
    pdf_path: Path,
    selected_pages: list[int],
    password: Optional[str],
    table_mode: TableMode,
) -> TableExtractionResult:
    result = TableExtractionResult()

    try:
        with pdfplumber.open(str(pdf_path), password=password) as pdf:
            for page_number in selected_pages:
                page = pdf.pages[page_number - 1]
                logger.debug("Extracting tables for page=%s", page_number)
                candidates = _collect_candidates_for_page(page)
                deduped = _prune_candidates(page, candidates)

                page_blocks: list[TableBlock] = []
                for index, candidate in enumerate(deduped, start=1):
                    mode, fallback_reason, reasons = _pick_mode(table_mode, candidate.rows)
                    if fallback_reason:
                        result.warnings.append(
                            WarningEntry(
                                code=WarningCode.TABLE_GFM_UNSAFE_FALLBACK_HTML,
                                message=fallback_reason,
                                page=page_number,
                                details={"table_index": index, "reasons": reasons},
                            )
                        )
                    elif mode == TableModeEmission.HTML and table_mode == TableMode.AUTO:
                        result.warnings.append(
                            WarningEntry(
                                code=WarningCode.TABLE_COMPLEXITY_HTML_FALLBACK,
                                message="Table was treated as complex and serialized as HTML fallback.",
                                page=page_number,
                                details={"table_index": index, "reasons": reasons},
                            )
                        )
                    elif mode == TableModeEmission.MARKDOWN and reasons:
                        result.warnings.append(
                            WarningEntry(
                                code=WarningCode.TABLE_COMPLEXITY_MARKDOWN_COERCED,
                                message="Table was treated as complex and coerced into Markdown output.",
                                page=page_number,
                                details={"table_index": index, "reasons": reasons},
                            )
                        )
                    if mode == TableModeEmission.HTML:
                        result.fallbacks.append(
                            {
                                "page": page_number,
                                "table_index": index,
                                "mode": mode,
                                "reasons": reasons,
                                "selected_strategy": candidate.metrics.selected_strategy,
                                "quality_score": candidate.metrics.quality_score,
                            }
                        )

                    if mode == TableModeEmission.HTML:
                        rendered = _serialize_html(candidate.rows, candidate.notes)
                    elif mode == TableModeEmission.MARKDOWN:
                        rendered = _serialize_markdown_forced(candidate.rows, candidate.notes)
                    else:
                        rendered = _serialize_gfm(candidate.rows)
                    comment_mode = TableModeEmission.MARKDOWN if mode == TableModeEmission.MARKDOWN else mode
                    comment = f"<!-- table: page={page_number} index={index} mode={comment_mode} -->"
                    x0, top, x1, bottom = candidate.bbox
                    asset_mode = TableModeEmission.GFM if mode == TableModeEmission.MARKDOWN else mode
                    page_blocks.append(
                        TableBlock(
                            page=page_number,
                            index=index,
                            mode=asset_mode,
                            markdown=f"{comment}\n{rendered}",
                            top=top,
                            bbox=(x0, top, x1, bottom),
                        )
                    )
                    result.assets.append(
                        TableAsset(
                            page=page_number,
                            index=index,
                            mode=asset_mode,
                            bbox=[x0, top, x1, bottom],
                        )
                    )
                    result.table_quality.append(
                        {
                            "page": page_number,
                            "table_index": index,
                            "selected_strategy": candidate.metrics.selected_strategy,
                            "empty_cell_ratio": candidate.metrics.empty_cell_ratio,
                            "all_empty_rows_removed": candidate.metrics.all_empty_rows_removed,
                            "columns_compacted": candidate.metrics.columns_compacted,
                            "columns_merged": candidate.metrics.columns_merged,
                            "quality_score": candidate.metrics.quality_score,
                            "data_density": candidate.metrics.data_density,
                            "header_fill_ratio": candidate.metrics.header_fill_ratio,
                            "reasons": candidate.decision.reasons,
                            "unresolved": candidate.decision.unresolved,
                            "mode": asset_mode,
                        }
                    )

                    result.table_counts["table_total"] += 1
                    if asset_mode == TableModeEmission.GFM:
                        result.table_counts["table_gfm_count"] += 1
                    else:
                        result.table_counts["table_html_count"] += 1
                    if table_mode in {TableMode.HTML, TableMode.HTML_ONLY}:
                        result.table_counts["table_html_forced_count"] += 1
                    if table_mode == TableMode.MARKDOWN:
                        result.table_counts["table_markdown_forced_count"] += 1
                    if candidate.metrics.columns_compacted > 0 or candidate.metrics.columns_merged > 0:
                        result.table_counts["table_recovered_count"] += 1
                    if candidate.decision.unresolved:
                        result.table_counts["table_unresolved_count"] += 1

                if page_blocks:
                    result.blocks_by_page[page_number] = page_blocks
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(
            WarningEntry(
                code=WarningCode.TABLE_EXTRACTION_FAILED,
                message=f"Failed to extract tables: {exc}",
            )
        )

    return result
