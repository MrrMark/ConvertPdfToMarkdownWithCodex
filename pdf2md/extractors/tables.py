from __future__ import annotations

import html
import logging
import math
from difflib import SequenceMatcher
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pdfplumber

from pdf2md.constants import TableDecisionReason, TableModeEmission, TableReason, WarningCode
from pdf2md.models import LineType, TableAsset, TableMode, WarningEntry
from pdf2md.utils.structure import classify_structure_line

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
    diagnostics: "TableDiagnostics"


@dataclass
class TableRow:
    index: int
    cells: list[str]
    role: str


@dataclass
class TableDiagnostics:
    header_depth: int
    header_confidence: float
    stub_column_count: int
    footnote_row_count: int
    merged_cell_suspected: bool
    rag_header_strategy: str
    headers: list[str]
    data_row_start_index: int
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TableCaptionMatch:
    text: str
    distance: float
    position: str


@dataclass(frozen=True)
class ContinuationDecision:
    accepted: bool
    confidence: float
    reasons: list[str]
    rejected_reasons: list[str]
    features: dict[str, Any]


@dataclass
class TableGrid:
    rows: list[TableRow]
    diagnostics: TableDiagnostics


@dataclass
class RagTablePayload:
    page: int
    table_index: int
    source_mode: str
    caption_text: str
    headers: list[str]
    bbox: list[float]
    quality_score: float
    fallback_reasons: list[str]
    records: list[dict[str, Any]]
    header_depth: int
    header_confidence: float
    stub_column_count: int
    rag_header_strategy: str
    caption_distance: float | None = None
    caption_position: str | None = None
    continuation_group: str | None = None
    continued_from_page: int | None = None
    continued_to_page: int | None = None
    continuation_confidence: float | None = None
    continuation_reasons: list[str] = field(default_factory=list)
    continuation_rejected_reasons: list[str] = field(default_factory=list)
    continuation_features: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "page": self.page,
            "table_index": self.table_index,
            "source_mode": self.source_mode,
            "caption_text": self.caption_text,
            "headers": self.headers,
            "bbox": self.bbox,
            "quality_score": self.quality_score,
            "fallback_reasons": self.fallback_reasons,
            "records": self.records,
            "header_depth": self.header_depth,
            "header_confidence": self.header_confidence,
            "stub_column_count": self.stub_column_count,
            "rag_header_strategy": self.rag_header_strategy,
        }
        if self.continuation_group is not None:
            payload["continuation_group"] = self.continuation_group
        if self.continued_from_page is not None:
            payload["continued_from_page"] = self.continued_from_page
        if self.continued_to_page is not None:
            payload["continued_to_page"] = self.continued_to_page
        if self.continuation_confidence is not None:
            payload["continuation_confidence"] = self.continuation_confidence
        if self.caption_distance is not None:
            payload["caption_distance"] = self.caption_distance
        if self.caption_position is not None:
            payload["caption_position"] = self.caption_position
        if self.continuation_reasons:
            payload["continuation_reasons"] = self.continuation_reasons
        if self.continuation_rejected_reasons:
            payload["continuation_rejected_reasons"] = self.continuation_rejected_reasons
        if self.continuation_features:
            payload["continuation_features"] = self.continuation_features
        return payload


@dataclass
class TableBlock:
    page: int
    index: int
    mode: str
    markdown: str
    top: float
    bbox: tuple[float, float, float, float]
    rows: list[list[str]] = field(default_factory=list)
    caption_text: str | None = None
    quality_score: float = 0.0
    fallback_reasons: list[str] = field(default_factory=list)


@dataclass
class TableExtractionResult:
    warnings: list[WarningEntry] = field(default_factory=list)
    assets: list[TableAsset] = field(default_factory=list)
    blocks_by_page: dict[int, list[TableBlock]] = field(default_factory=dict)
    table_quality: list[dict[str, Any]] = field(default_factory=list)
    fallbacks: list[dict[str, Any]] = field(default_factory=list)
    rag_tables: list[dict[str, Any]] = field(default_factory=list)
    debug_candidates_by_page: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
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
        reasons.add(TableReason.TOO_FEW_ROWS)

    width = len(rows[0]) if rows and rows[0] else 0
    if width < 2:
        reasons.add(TableReason.AMBIGUOUS_GRID)
        reasons.add(TableReason.TOO_FEW_COLUMNS)
    if width > 12:
        reasons.add(TableReason.SPARSE_LAYOUT)
        reasons.add(TableReason.OVERWIDE_TABLE)

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
            reasons.add(TableReason.LONG_CELL)

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


def _pick_mode(
    table_mode: TableMode,
    rows: list[list[str]],
    complexity_reasons: list[str] | None = None,
) -> tuple[str, Optional[str], list[str]]:
    if complexity_reasons is None:
        simple, reasons = analyze_table_complexity(rows)
    else:
        reasons = sorted(set(complexity_reasons))
        simple = not reasons
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


def _candidate_text_signature(candidate: TableExtractionCandidate) -> str:
    return " ".join(cell.strip().lower() for row in candidate.rows for cell in row if cell.strip())


def _is_redundant_text_fragment(
    candidate: TableExtractionCandidate,
    accepted: TableExtractionCandidate,
) -> bool:
    candidate_text = _candidate_text_signature(candidate)
    accepted_text = _candidate_text_signature(accepted)
    if len(candidate_text) < 5 or candidate_text not in accepted_text:
        return False
    candidate_area = _bbox_area(candidate.bbox)
    accepted_area = _bbox_area(accepted.bbox)
    if accepted_area <= 0 or candidate_area / accepted_area > 0.35:
        return False
    vertical_overlap = max(0.0, min(candidate.bbox[3], accepted.bbox[3]) - max(candidate.bbox[1], accepted.bbox[1]))
    candidate_height = max(1.0, candidate.bbox[3] - candidate.bbox[1])
    same_band = vertical_overlap / candidate_height >= 0.35
    horizontal_gap = max(accepted.bbox[0] - candidate.bbox[2], candidate.bbox[0] - accepted.bbox[2], 0.0)
    return same_band and horizontal_gap <= 36.0 and candidate.quality_score <= accepted.quality_score


def _candidate_debug_payload(candidate: TableExtractionCandidate, *, accepted: bool, reason: str | None = None) -> dict[str, Any]:
    width = len(candidate.rows[0]) if candidate.rows and candidate.rows[0] else 0
    return {
        "bbox": list(candidate.bbox),
        "selected_strategy": candidate.metrics.selected_strategy,
        "quality_score": candidate.metrics.quality_score,
        "row_count": len(candidate.rows),
        "column_count": width,
        "accepted": accepted,
        "suppression_reason": reason,
        "reasons": candidate.decision.reasons,
        "unresolved": candidate.decision.unresolved,
        "header_depth": candidate.diagnostics.header_depth,
        "header_confidence": candidate.diagnostics.header_confidence,
        "stub_column_count": candidate.diagnostics.stub_column_count,
        "rag_header_strategy": candidate.diagnostics.rag_header_strategy,
    }


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
            table_grid = _build_table_grid(rows, notes, metrics)
            simple, reasons = analyze_table_complexity(rows)
            reasons = sorted(set(reasons).union(table_grid.diagnostics.reasons))
            candidate = TableExtractionCandidate(
                strategy=strategy,
                bbox=tuple(float(v) for v in table_obj.bbox),
                rows=rows,
                notes=notes,
                quality_score=metrics.quality_score,
                metrics=metrics,
                decision=TableRecoveryDecision(unresolved=bool(reasons) or not simple, reasons=reasons),
                diagnostics=table_grid.diagnostics,
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


def _prune_candidates_with_debug(
    page: pdfplumber.page.Page,
    candidates: list[TableExtractionCandidate],
) -> tuple[list[TableExtractionCandidate], list[dict[str, Any]]]:
    debug_by_id: dict[int, dict[str, Any]] = {
        id(candidate): _candidate_debug_payload(candidate, accepted=False) for candidate in candidates
    }
    ranked = list(candidates)
    ranked.sort(
        key=lambda item: (_candidate_rank(page, item.bbox, item.quality_score), _bbox_area(item.bbox)),
        reverse=True,
    )
    deduped: list[TableExtractionCandidate] = []
    for item in ranked:
        if any(_is_contained(item.bbox, prev.bbox) for prev in deduped):
            debug_by_id[id(item)]["suppression_reason"] = "contained_bbox"
            continue
        deduped.append(item)
        if len(deduped) >= 20:
            break
    deduped.sort(key=lambda item: item.bbox[1])
    pruned: list[TableExtractionCandidate] = []
    for item in deduped:
        if any(_is_fragment_candidate(item, accepted) for accepted in pruned):
            debug_by_id[id(item)]["suppression_reason"] = "narrow_fragment"
            continue
        if any(_is_redundant_text_fragment(item, accepted) for accepted in pruned):
            debug_by_id[id(item)]["suppression_reason"] = TableDecisionReason.TEXT_FRAGMENT_SUPPRESSION
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
                debug_by_id[id(item)]["suppression_reason"] = "neighbor_text_fragment"
                continue
        refined.append(item)
    for item in refined:
        debug_by_id[id(item)]["accepted"] = True
    debug = [debug_by_id[id(candidate)] for candidate in candidates]
    return refined, debug


def _prune_candidates(
    page: pdfplumber.page.Page,
    candidates: list[TableExtractionCandidate],
) -> list[TableExtractionCandidate]:
    pruned, _ = _prune_candidates_with_debug(page, candidates)
    return pruned


def _line_text(line: dict[str, Any]) -> str:
    return _sanitize_cell(line.get("text", ""))


def _line_bbox(line: dict[str, Any]) -> tuple[float, float, float, float]:
    x0 = float(line.get("x0", 0.0))
    top = float(line.get("top", 0.0))
    x1 = float(line.get("x1", x0))
    bottom = float(line.get("bottom", top))
    return x0, top, x1, bottom


def _horizontal_overlap_ratio(
    line_bbox: tuple[float, float, float, float],
    table_bbox: tuple[float, float, float, float],
) -> float:
    lx0, _, lx1, _ = line_bbox
    tx0, _, tx1, _ = table_bbox
    line_width = max(lx1 - lx0, 1.0)
    overlap = max(0.0, min(lx1, tx1) - max(lx0, tx0))
    return overlap / line_width


def _find_table_caption_match(
    page: pdfplumber.page.Page,
    bbox: tuple[float, float, float, float],
    text_lines: list[dict] | None = None,
) -> TableCaptionMatch | None:
    """Return a nearby explicit table caption only when the geometry is clear."""
    if text_lines is None:
        extract_text_lines = getattr(page, "extract_text_lines", None)
        if extract_text_lines is None:
            return None
        try:
            text_lines = extract_text_lines() or []
        except Exception:  # noqa: BLE001
            return None

    _, table_top, _, table_bottom = bbox
    candidates: list[tuple[float, str, str]] = []
    for raw_line in text_lines:
        text = _line_text(raw_line)
        if not text or classify_structure_line(text) is not LineType.TABLE_CAPTION:
            continue
        line_bbox = _line_bbox(raw_line)
        if _horizontal_overlap_ratio(line_bbox, bbox) < 0.25:
            continue
        _, line_top, _, line_bottom = line_bbox
        above_distance = table_top - line_bottom
        below_distance = line_top - table_bottom
        if 0 <= above_distance <= 48:
            candidates.append((above_distance, text, "above"))
        elif 0 <= below_distance <= 24:
            candidates.append((below_distance + 12, text, "below"))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    distance, text, position = candidates[0]
    return TableCaptionMatch(text=text, distance=round(distance, 4), position=position)


def _find_table_caption(
    page: pdfplumber.page.Page,
    bbox: tuple[float, float, float, float],
    text_lines: list[dict] | None = None,
) -> str | None:
    match = _find_table_caption_match(page, bbox, text_lines=text_lines)
    return match.text if match is not None else None


def _unique_headers(header_row: list[str]) -> list[str]:
    headers: list[str] = []
    seen: dict[str, int] = {}
    for idx, raw_header in enumerate(header_row, start=1):
        base = raw_header.strip() or f"Column {idx}"
        count = seen.get(base, 0) + 1
        seen[base] = count
        headers.append(base if count == 1 else f"{base} {count}")
    return headers


def _looks_like_multi_row_header(rows: list[list[str]]) -> bool:
    if len(rows) < 3 or not rows[0] or not rows[1]:
        return False
    first = rows[0]
    second = rows[1]
    first_non_empty = sum(1 for cell in first if cell.strip())
    second_non_empty = sum(1 for cell in second if cell.strip())
    if second_non_empty < max(2, len(second) // 2):
        return False
    repeated_parent = any(first[idx].strip() and first[idx].strip() == first[idx + 1].strip() for idx in range(len(first) - 1))
    blank_parent_with_child_count = sum(
        1 for idx in range(min(len(first), len(second))) if not first[idx].strip() and second[idx].strip()
    )
    body_density = _data_density([second] + rows[2:])
    return body_density >= 0.35 and (repeated_parent or blank_parent_with_child_count >= 2) and first_non_empty > 0


def _flatten_multi_row_headers(rows: list[list[str]]) -> list[str]:
    parent_row = rows[0]
    child_row = rows[1]
    headers: list[str] = []
    last_parent = ""
    width = max(len(parent_row), len(child_row))
    for idx in range(width):
        parent = parent_row[idx].strip() if idx < len(parent_row) else ""
        child = child_row[idx].strip() if idx < len(child_row) else ""
        if parent:
            last_parent = parent
        elif last_parent and child:
            parent = last_parent
        if parent and child and parent != child:
            headers.append(f"{parent} / {child}")
        else:
            headers.append(child or parent or f"Column {idx + 1}")
    return _unique_headers(headers)


def _detect_stub_column_count(rows: list[list[str]], header_depth: int) -> int:
    if len(rows) <= header_depth or not rows[0]:
        return 0
    data_rows = rows[header_depth:]
    if not data_rows:
        return 0
    first_column_values = [row[0].strip() for row in data_rows if row and row[0].strip()]
    if len(first_column_values) < max(1, int(len(data_rows) * 0.6)):
        return 0
    other_values = [
        cell.strip()
        for row in data_rows
        for cell in row[1:]
        if cell.strip()
    ]
    alpha_first = sum(1 for value in first_column_values if any(char.isalpha() for char in value))
    numeric_other = sum(1 for value in other_values if any(char.isdigit() for char in value))
    if alpha_first >= max(1, int(len(first_column_values) * 0.6)) and numeric_other >= max(1, int(len(other_values) * 0.4)):
        return 1
    header = rows[header_depth - 1][0].strip().lower() if header_depth > 0 and rows[header_depth - 1] else ""
    if not header and numeric_other >= 1:
        return 1
    return 0


def _header_confidence(rows: list[list[str]], header_depth: int) -> float:
    if not rows:
        return 0.0
    if header_depth == 2:
        return 0.85
    fill_ratio = _header_fill_ratio(rows)
    if fill_ratio >= 0.75:
        return 0.85
    if fill_ratio >= 0.5:
        return 0.65
    return 0.4


def _merged_cell_suspected(rows: list[list[str]], header_depth: int) -> bool:
    if not rows:
        return False
    width = len(rows[0])
    if width < 3:
        return False
    header_blank = any(not cell.strip() for row in rows[: max(header_depth, 1)] for cell in row)
    sparse_body_rows = 0
    for row in rows[header_depth:]:
        non_empty = sum(1 for cell in row if cell.strip())
        if 0 < non_empty < max(2, width // 2):
            sparse_body_rows += 1
    return header_blank or sparse_body_rows >= 2


def _build_table_grid(rows: list[list[str]], notes: list[str], metrics: TableQualityMetrics) -> TableGrid:
    header_depth = 2 if _looks_like_multi_row_header(rows) else 1
    confidence = _header_confidence(rows, header_depth)
    headers = _flatten_multi_row_headers(rows) if header_depth == 2 else _unique_headers(rows[0] if rows else [])
    rag_header_strategy = "multi_row_flattened" if header_depth == 2 else "single_row"
    reasons: set[str] = set()
    if header_depth == 2:
        reasons.add(TableReason.MULTI_ROW_HEADER)
    if notes:
        reasons.add(TableReason.FOOTNOTE_ROW)
    stub_count = _detect_stub_column_count(rows, header_depth)
    if stub_count:
        reasons.add(TableReason.STUB_COLUMN)
    merged = _merged_cell_suspected(rows, header_depth)
    if merged:
        reasons.add(TableReason.MERGED_CELL_SUSPECTED)
    if confidence < 0.5:
        reasons.add(TableReason.LOW_HEADER_CONFIDENCE)
        rag_header_strategy = "fallback_low_confidence"

    diagnostics = TableDiagnostics(
        header_depth=header_depth,
        header_confidence=round(confidence, 4),
        stub_column_count=stub_count,
        footnote_row_count=len(notes),
        merged_cell_suspected=merged,
        rag_header_strategy=rag_header_strategy,
        headers=headers,
        data_row_start_index=header_depth,
        reasons=sorted(reasons),
    )
    table_rows = [
        TableRow(
            index=idx,
            cells=row,
            role="header" if idx < header_depth else "body",
        )
        for idx, row in enumerate(rows)
    ]
    return TableGrid(rows=table_rows, diagnostics=diagnostics)


def _build_rag_table_payload(
    *,
    page_number: int,
    table_index: int,
    source_mode: str,
    candidate: TableExtractionCandidate,
    caption_text: str | None,
    fallback_reasons: list[str],
    caption_distance: float | None = None,
    caption_position: str | None = None,
) -> dict[str, Any]:
    diagnostics = candidate.diagnostics
    headers = diagnostics.headers
    row_records: list[dict[str, Any]] = []
    data_rows = candidate.rows[diagnostics.data_row_start_index :]
    for row_index, row in enumerate(data_rows, start=1):
        padded = row + [""] * max(0, len(headers) - len(row))
        cells = {header: padded[idx] if idx < len(padded) else "" for idx, header in enumerate(headers)}
        row_text = " | ".join(f"{header} = {cells[header]}" for header in headers)
        stub_cells = padded[: diagnostics.stub_column_count] if diagnostics.stub_column_count else []
        record = {
            "page": page_number,
            "table_index": table_index,
            "source_mode": source_mode,
            "caption_text": caption_text or "",
            "headers": headers,
            "row_index": row_index,
            "cells": cells,
            "row_text": row_text,
            "bbox": [float(value) for value in candidate.bbox],
            "quality_score": candidate.metrics.quality_score,
            "fallback_reasons": fallback_reasons,
            "header_depth": diagnostics.header_depth,
            "header_confidence": diagnostics.header_confidence,
            "rag_header_strategy": diagnostics.rag_header_strategy,
        }
        if caption_distance is not None:
            record["caption_distance"] = caption_distance
        if caption_position is not None:
            record["caption_position"] = caption_position
        if stub_cells:
            record["stub_cells"] = stub_cells
        row_records.append(
            record
        )
    return RagTablePayload(
        page=page_number,
        table_index=table_index,
        source_mode=source_mode,
        caption_text=caption_text or "",
        headers=headers,
        bbox=[float(value) for value in candidate.bbox],
        quality_score=candidate.metrics.quality_score,
        fallback_reasons=fallback_reasons,
        records=row_records,
        header_depth=diagnostics.header_depth,
        header_confidence=diagnostics.header_confidence,
        stub_column_count=diagnostics.stub_column_count,
        rag_header_strategy=diagnostics.rag_header_strategy,
        caption_distance=caption_distance,
        caption_position=caption_position,
    ).as_dict()


def _normalize_header_signature(headers: list[str]) -> tuple[str, ...]:
    return tuple(_sanitize_cell(header).casefold() for header in headers if _sanitize_cell(header))


def _signature_similarity(previous: tuple[str, ...], current: tuple[str, ...]) -> float:
    if not previous or not current:
        return 0.0
    if previous == current:
        return 1.0
    width = max(len(previous), len(current))
    positional_matches = sum(1 for left, right in zip(previous, current) if left == right) / width
    previous_set = set(previous)
    current_set = set(current)
    overlap = len(previous_set & current_set) / max(len(previous_set | current_set), 1)
    sequence = SequenceMatcher(None, " | ".join(previous), " | ".join(current)).ratio()
    return round(max(positional_matches, overlap, sequence), 4)


def _bbox_alignment_similarity(previous_bbox: list[float] | None, current_bbox: list[float] | None) -> float:
    if not previous_bbox or not current_bbox or len(previous_bbox) < 4 or len(current_bbox) < 4:
        return 0.0
    prev_x0, _, prev_x1, _ = (float(value) for value in previous_bbox[:4])
    curr_x0, _, curr_x1, _ = (float(value) for value in current_bbox[:4])
    prev_width = max(prev_x1 - prev_x0, 1.0)
    curr_width = max(curr_x1 - curr_x0, 1.0)
    scale = max(prev_width, curr_width, 1.0)
    left_delta = abs(prev_x0 - curr_x0) / scale
    right_delta = abs(prev_x1 - curr_x1) / scale
    width_delta = abs(prev_width - curr_width) / scale
    return round(max(0.0, 1.0 - ((left_delta + right_delta + width_delta) / 3.0)), 4)


def _body_text_signature(rag_table: dict[str, Any]) -> str:
    row_texts = [
        _sanitize_cell(str(record.get("row_text", ""))).casefold()
        for record in rag_table.get("records", [])
        if _sanitize_cell(str(record.get("row_text", "")))
    ]
    return "\n".join(row_texts)


def _repeated_template_penalty(previous_rag: dict[str, Any], current_rag: dict[str, Any]) -> float:
    previous_text = _body_text_signature(previous_rag)
    current_text = _body_text_signature(current_rag)
    if not previous_text or not current_text:
        return 0.0
    previous_rows = set(previous_text.splitlines())
    current_rows = set(current_text.splitlines())
    row_overlap = len(previous_rows & current_rows) / max(min(len(previous_rows), len(current_rows)), 1)
    body_similarity = SequenceMatcher(None, previous_text, current_text).ratio()
    if row_overlap >= 0.8 or body_similarity >= 0.9:
        return 0.45
    if row_overlap >= 0.5 or body_similarity >= 0.82:
        return 0.25
    return 0.0


def _continuation_decision(
    *,
    previous_asset: TableAsset,
    previous_rag: dict[str, Any],
    previous_signature: tuple[str, ...],
    asset: TableAsset,
    rag_table: dict[str, Any],
    signature: tuple[str, ...],
) -> ContinuationDecision:
    page_gap = asset.page - previous_asset.page
    header_similarity = _signature_similarity(previous_signature, signature)
    bbox_alignment_similarity = _bbox_alignment_similarity(previous_asset.bbox, asset.bbox)
    current_caption_text = str(rag_table.get("caption_text") or "").strip()
    current_caption_distance = rag_table.get("caption_distance")
    repeated_template_penalty = _repeated_template_penalty(previous_rag, rag_table)
    adjacency_score = 1.0 if page_gap == 1 else 0.0
    confidence = round(
        max(
            0.0,
            min(
                1.0,
                (0.45 * header_similarity)
                + (0.35 * bbox_alignment_similarity)
                + (0.20 * adjacency_score)
                - repeated_template_penalty,
            ),
        ),
        4,
    )
    features: dict[str, Any] = {
        "page_gap": page_gap,
        "header_similarity": header_similarity,
        "bbox_alignment_similarity": bbox_alignment_similarity,
        "current_caption_distance": current_caption_distance,
        "repeated_template_penalty": repeated_template_penalty,
    }
    rejected_reasons: list[str] = []
    if page_gap != 1:
        rejected_reasons.append("non_adjacent_page")
    if header_similarity < 0.95:
        rejected_reasons.append("header_similarity_below_threshold")
    if bbox_alignment_similarity < 0.8:
        rejected_reasons.append("bbox_alignment_below_threshold")
    if current_caption_text:
        rejected_reasons.append("current_caption_present")
    if repeated_template_penalty >= 0.35:
        rejected_reasons.append("repeated_template_penalty")
    if confidence < 0.82:
        rejected_reasons.append("continuation_confidence_below_threshold")

    reasons = [
        "adjacent_page",
        "header_similarity_high",
        "bbox_alignment_high",
        "no_current_caption",
        "repeated_template_penalty_clear",
    ]
    return ContinuationDecision(
        accepted=not rejected_reasons,
        confidence=confidence,
        reasons=reasons if not rejected_reasons else [],
        rejected_reasons=rejected_reasons,
        features=features,
    )


def _store_continuation_diagnostics(
    *,
    asset: TableAsset,
    rag_table: dict[str, Any],
    quality: dict[str, Any] | None,
    decision: ContinuationDecision,
) -> None:
    if decision.reasons:
        asset.continuation_reasons = decision.reasons
        rag_table["continuation_reasons"] = decision.reasons
        if quality is not None:
            quality["continuation_reasons"] = decision.reasons
    if decision.rejected_reasons:
        asset.continuation_rejected_reasons = decision.rejected_reasons
        rag_table["continuation_rejected_reasons"] = decision.rejected_reasons
        if quality is not None:
            quality["continuation_rejected_reasons"] = decision.rejected_reasons
    asset.continuation_features = decision.features
    rag_table["continuation_features"] = decision.features
    if quality is not None:
        quality["continuation_features"] = decision.features


def _annotate_table_continuations(result: TableExtractionResult) -> None:
    """Link adjacent-page tables only when continuation evidence is high confidence."""
    rag_by_key = {
        (int(table.get("page", 0)), int(table.get("table_index", 0))): table
        for table in result.rag_tables
    }
    quality_by_key = {
        (int(item.get("page", 0)), int(item.get("table_index", 0))): item
        for item in result.table_quality
    }
    previous: tuple[TableAsset, dict[str, Any], tuple[str, ...]] | None = None
    group_counter = 1
    for asset in sorted(result.assets, key=lambda item: (item.page, item.index)):
        rag_table = rag_by_key.get((asset.page, asset.index))
        if rag_table is None:
            previous = None
            continue
        signature = _normalize_header_signature([str(header) for header in rag_table.get("headers", [])])
        if not signature:
            previous = (asset, rag_table, signature)
            continue
        if previous is None:
            previous = (asset, rag_table, signature)
            continue

        previous_asset, previous_rag, previous_signature = previous
        decision = _continuation_decision(
            previous_asset=previous_asset,
            previous_rag=previous_rag,
            previous_signature=previous_signature,
            asset=asset,
            rag_table=rag_table,
            signature=signature,
        )
        current_quality = quality_by_key.get((asset.page, asset.index))
        if not decision.accepted:
            _store_continuation_diagnostics(
                asset=asset,
                rag_table=rag_table,
                quality=current_quality,
                decision=decision,
            )
            previous = (asset, rag_table, signature)
            continue

        group = previous_asset.continuation_group or f"table-continuation-{group_counter:03d}"
        if previous_asset.continuation_group is None:
            group_counter += 1
        confidence = decision.confidence
        previous_asset.continuation_group = group
        previous_asset.continued_to_page = asset.page
        previous_asset.continuation_confidence = confidence
        asset.continuation_group = group
        asset.continued_from_page = previous_asset.page
        asset.continuation_confidence = confidence
        previous_rag["continuation_group"] = group
        previous_rag["continued_to_page"] = asset.page
        previous_rag["continuation_confidence"] = confidence
        rag_table["continuation_group"] = group
        rag_table["continued_from_page"] = previous_asset.page
        rag_table["continuation_confidence"] = confidence
        previous_quality = quality_by_key.get((previous_asset.page, previous_asset.index))
        _store_continuation_diagnostics(
            asset=previous_asset,
            rag_table=previous_rag,
            quality=previous_quality,
            decision=decision,
        )
        _store_continuation_diagnostics(
            asset=asset,
            rag_table=rag_table,
            quality=current_quality,
            decision=decision,
        )
        if previous_quality is not None:
            previous_quality["continuation_group"] = group
            previous_quality["continued_to_page"] = asset.page
            previous_quality["continuation_confidence"] = confidence
        if current_quality is not None:
            current_quality["continuation_group"] = group
            current_quality["continued_from_page"] = previous_asset.page
            current_quality["continuation_confidence"] = confidence
        for record in previous_rag.get("records", []):
            record["continuation_group"] = group
            record["continued_to_page"] = asset.page
            record["continuation_confidence"] = confidence
            record["continuation_reasons"] = decision.reasons
            record["continuation_features"] = decision.features
        for record in rag_table.get("records", []):
            record["continuation_group"] = group
            record["continued_from_page"] = previous_asset.page
            record["continuation_confidence"] = confidence
            record["continuation_reasons"] = decision.reasons
            record["continuation_features"] = decision.features
        previous = (asset, rag_table, signature)


def extract_tables(
    pdf_path: Path,
    selected_pages: list[int],
    password: Optional[str],
    table_mode: TableMode,
    pdf: Any = None,
    text_lines_by_page: dict[int, list[dict]] | None = None,
) -> TableExtractionResult:
    result = TableExtractionResult()

    try:
        if pdf is not None:
            opened_pdf = pdf
            close_after = False
        else:
            opened_pdf = pdfplumber.open(str(pdf_path), password=password)
            close_after = True
        try:
            for page_number in selected_pages:
                page = opened_pdf.pages[page_number - 1]
                logger.debug("Extracting tables for page=%s", page_number)
                candidates = _collect_candidates_for_page(page)
                deduped, debug_candidates = _prune_candidates_with_debug(page, candidates)
                result.debug_candidates_by_page[page_number] = debug_candidates

                page_blocks: list[TableBlock] = []
                for index, candidate in enumerate(deduped, start=1):
                    mode, fallback_reason, reasons = _pick_mode(
                        table_mode,
                        candidate.rows,
                        complexity_reasons=candidate.decision.reasons,
                    )
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
                    caption_match = _find_table_caption_match(
                        page,
                        candidate.bbox,
                        text_lines=(text_lines_by_page or {}).get(page_number),
                    )
                    caption_text = caption_match.text if caption_match is not None else None
                    caption_distance = caption_match.distance if caption_match is not None else None
                    caption_position = caption_match.position if caption_match is not None else None
                    fallback_reasons = reasons if asset_mode == TableModeEmission.HTML else []

                    page_blocks.append(
                        TableBlock(
                            page=page_number,
                            index=index,
                            mode=asset_mode,
                            markdown=f"{comment}\n{rendered}",
                            top=top,
                            bbox=(x0, top, x1, bottom),
                            rows=candidate.rows,
                            caption_text=caption_text,
                            quality_score=candidate.metrics.quality_score,
                            fallback_reasons=fallback_reasons,
                        )
                    )
                    result.assets.append(
                        TableAsset(
                            page=page_number,
                            index=index,
                            mode=asset_mode,
                            bbox=[x0, top, x1, bottom],
                            quality_score=candidate.metrics.quality_score,
                            fallback_reasons=fallback_reasons,
                            caption_text=caption_text,
                            caption_source="nearby_table_caption" if caption_text else None,
                        )
                    )
                    result.rag_tables.append(
                        _build_rag_table_payload(
                            page_number=page_number,
                            table_index=index,
                            source_mode=asset_mode,
                            candidate=candidate,
                            caption_text=caption_text,
                            fallback_reasons=fallback_reasons,
                            caption_distance=caption_distance,
                            caption_position=caption_position,
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
                            "caption_text": caption_text,
                            "caption_distance": caption_distance,
                            "caption_position": caption_position,
                            "caption_source": "nearby_table_caption" if caption_text else None,
                            "header_depth": candidate.diagnostics.header_depth,
                            "header_confidence": candidate.diagnostics.header_confidence,
                            "stub_column_count": candidate.diagnostics.stub_column_count,
                            "footnote_row_count": candidate.diagnostics.footnote_row_count,
                            "merged_cell_suspected": candidate.diagnostics.merged_cell_suspected,
                            "rag_header_strategy": candidate.diagnostics.rag_header_strategy,
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
            _annotate_table_continuations(result)
        finally:
            if close_after:
                close = getattr(opened_pdf, "close", None)
                if close is not None:
                    close()
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(
            WarningEntry(
                code=WarningCode.TABLE_EXTRACTION_FAILED,
                message=f"Failed to extract tables: {exc}",
            )
        )

    return result
