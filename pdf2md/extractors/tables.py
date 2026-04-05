from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pdfplumber

from pdf2md.models import TableAsset, TableMode, WarningEntry


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


def _prune_empty_columns(rows: list[list[str]]) -> list[list[str]]:
    if not rows or not rows[0]:
        return rows
    width = len(rows[0])
    counts = [0] * width
    header = rows[0]
    for r in rows:
        for idx, cell in enumerate(r):
            if idx < width and cell.strip():
                counts[idx] += 1
    keep_indices = [idx for idx in range(width) if counts[idx] >= 2 or header[idx].strip()]
    if not keep_indices or len(keep_indices) == width:
        return rows
    return [[row[idx] for idx in keep_indices] for row in rows]


def analyze_table_complexity(rows: list[list[str]]) -> tuple[bool, list[str]]:
    reasons: set[str] = set()
    if not rows:
        return False, ["AMBIGUOUS_GRID"]
    if len(rows) < 2:
        reasons.add("AMBIGUOUS_GRID")
    width = len(rows[0])
    if width == 0:
        reasons.add("AMBIGUOUS_GRID")
    if width > 12:
        reasons.add("SPARSE_LAYOUT")

    for row in rows:
        if len(row) != width:
            reasons.add("AMBIGUOUS_GRID")
            break

    header = rows[0] if rows else []
    if header and all(not c.strip() for c in header):
        reasons.add("SPARSE_LAYOUT")

    col_non_empty = [0] * width if width > 0 else []
    multiline_cells = 0
    long_cells = 0
    sparse_rows = 0
    for row in rows:
        non_empty = 0
        for idx, cell in enumerate(row):
            stripped = cell.strip()
            if stripped:
                non_empty += 1
                if idx < len(col_non_empty):
                    col_non_empty[idx] += 1
            if "\n" in cell:
                multiline_cells += 1
            if len(stripped) > 120:
                long_cells += 1
        if width > 0 and (non_empty / width) < 0.35:
            sparse_rows += 1

    if multiline_cells > 0:
        reasons.add("MULTILINE_CELL")
    if long_cells > 0:
        reasons.add("AMBIGUOUS_GRID")
    if len(rows) > 0 and sparse_rows / len(rows) >= 0.5:
        reasons.add("SPARSE_LAYOUT")
    if width > 0:
        near_empty_cols = sum(1 for c in col_non_empty if c <= 1)
        if near_empty_cols / width >= 0.3:
            reasons.add("AMBIGUOUS_GRID")

    return len(reasons) == 0, sorted(reasons)


def is_simple_table(rows: list[list[str]]) -> bool:
    return analyze_table_complexity(rows)[0]


def _serialize_gfm(rows: list[list[str]]) -> str:
    header = rows[0]
    body = rows[1:]
    lines: list[str] = []
    lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for row in body:
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |")
    return "\n".join(lines)


def _serialize_html(rows: list[list[str]]) -> str:
    if not rows:
        return "<table></table>"
    lines: list[str] = ["<table>", "  <thead>", "    <tr>"]
    for cell in rows[0]:
        lines.append(f"      <th>{cell}</th>")
    lines.extend(["    </tr>", "  </thead>", "  <tbody>"])
    for row in rows[1:]:
        lines.append("    <tr>")
        for cell in row:
            lines.append(f"      <td>{cell}</td>")
        lines.append("    </tr>")
    lines.extend(["  </tbody>", "</table>"])
    return "\n".join(lines)


def _header_pattern_score(rows: list[list[str]]) -> float:
    if not rows:
        return 0.0
    header = rows[0]
    filled = sum(1 for cell in header if cell.strip())
    if not header:
        return 0.0
    ratio = filled / len(header)
    return max(0.0, min(ratio, 1.0))


def _candidate_score(page: pdfplumber.page.Page, table_obj, rows: list[list[str]]) -> float:
    score = 0.0
    if len(rows) >= 2:
        score += 0.25
    if len(rows[0]) >= 2 if rows else False:
        score += 0.15
    score += 0.2 * _header_pattern_score(rows)
    edge_count = len(page.edges or [])
    if edge_count > 0:
        score += 0.2
    area = _bbox_area(tuple(float(v) for v in table_obj.bbox))
    page_area = float(page.width * page.height)
    if page_area > 0 and (area / page_area) >= 0.01:
        score += 0.2
    return score


def _pick_mode(table_mode: TableMode, rows: list[list[str]]) -> tuple[str, Optional[str], list[str]]:
    simple, reasons = analyze_table_complexity(rows)
    if table_mode == TableMode.HTML_ONLY:
        return "html", None, reasons
    if table_mode == TableMode.GFM_ONLY:
        if simple:
            return "gfm", None, reasons
        reason_text = ",".join(reasons) if reasons else "AMBIGUOUS_GRID"
        return "html", f"Requested gfm-only but table was unsafe for GFM ({reason_text}); used HTML fallback.", reasons
    if simple:
        return "gfm", None, reasons
    return "html", None, reasons


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
                raw_candidates = page.find_tables() or []
                scored: list[tuple[float, object, list[list[str]]]] = []
                for table_obj in raw_candidates:
                    raw_rows = table_obj.extract() or []
                    rows = [[_sanitize_cell(cell) for cell in row] for row in raw_rows if row is not None]
                    rows = _prune_empty_columns(rows)
                    if not rows or not rows[0]:
                        continue
                    score = _candidate_score(page, table_obj, rows)
                    if score < 0.35:
                        continue
                    scored.append((score, table_obj, rows))

                scored.sort(key=lambda item: (_bbox_area(tuple(item[1].bbox)), item[0]), reverse=True)
                deduped: list[tuple[float, object, list[list[str]]]] = []
                for item in scored:
                    bbox = tuple(float(v) for v in item[1].bbox)
                    if any(_is_contained(bbox, tuple(float(v) for v in prev[1].bbox)) for prev in deduped):
                        continue
                    deduped.append(item)
                    if len(deduped) >= 20:
                        break
                deduped.sort(key=lambda item: float(item[1].bbox[1]))

                page_blocks: list[TableBlock] = []
                for index, (_, table_obj, rows) in enumerate(deduped, start=1):
                    mode, fallback_reason, reasons = _pick_mode(table_mode, rows)
                    if fallback_reason:
                        result.warnings.append(
                            WarningEntry(
                                code="TABLE_GFM_UNSAFE_FALLBACK_HTML",
                                message=fallback_reason,
                                page=page_number,
                                details={"table_index": index, "reasons": reasons},
                            )
                        )
                    elif mode == "html" and table_mode == TableMode.AUTO:
                        result.warnings.append(
                            WarningEntry(
                                code="TABLE_COMPLEXITY_HTML_FALLBACK",
                                message="Table was treated as complex and serialized as HTML fallback.",
                                page=page_number,
                                details={"table_index": index, "reasons": reasons},
                            )
                        )

                    rendered = _serialize_gfm(rows) if mode == "gfm" else _serialize_html(rows)
                    comment = f"<!-- table: page={page_number} index={index} mode={mode} -->"
                    x0, top, x1, bottom = [float(v) for v in table_obj.bbox]
                    page_blocks.append(
                        TableBlock(
                            page=page_number,
                            index=index,
                            mode=mode,
                            markdown=f"{comment}\n{rendered}",
                            top=top,
                            bbox=(x0, top, x1, bottom),
                        )
                    )
                    result.assets.append(
                        TableAsset(
                            page=page_number,
                            index=index,
                            mode=mode,
                            bbox=[x0, top, x1, bottom],
                        )
                    )

                if page_blocks:
                    result.blocks_by_page[page_number] = page_blocks
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(
            WarningEntry(
                code="TABLE_EXTRACTION_FAILED",
                message=f"Failed to extract tables: {exc}",
            )
        )

    return result
