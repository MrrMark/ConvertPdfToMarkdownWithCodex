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


@dataclass
class TableExtractionResult:
    warnings: list[WarningEntry] = field(default_factory=list)
    assets: list[TableAsset] = field(default_factory=list)
    blocks_by_page: dict[int, list[TableBlock]] = field(default_factory=dict)


def _sanitize_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return text


def analyze_table_complexity(rows: list[list[str]]) -> tuple[bool, list[str]]:
    """Return (is_simple, reasons) for conservative GFM safety checks."""
    reasons: list[str] = []
    if not rows:
        return False, ["empty_table"]
    if len(rows) < 2:
        reasons.append("not_enough_rows")
    width = len(rows[0])
    if width == 0:
        reasons.append("zero_columns")
    if width > 12:
        reasons.append("too_many_columns")

    for row in rows:
        if len(row) != width:
            reasons.append("non_rectangular")
            break

    header = rows[0] if rows else []
    if header and all(cell.strip() == "" for cell in header):
        reasons.append("empty_header")

    multiline_cells = 0
    long_cells = 0
    sparse_rows = 0
    list_like_cells = 0
    for row in rows:
        non_empty = 0
        for cell in row:
            stripped = cell.strip()
            if stripped:
                non_empty += 1
            if "\n" in cell:
                multiline_cells += 1
            if len(stripped) > 120:
                long_cells += 1
            if stripped.startswith(("- ", "* ", "1. ", "2. ", "3. ")):
                list_like_cells += 1
        if width > 0 and non_empty <= max(1, width // 3):
            sparse_rows += 1

    if multiline_cells > 0:
        reasons.append("multiline_cells")
    if long_cells > 0:
        reasons.append("very_long_cells")
    if sparse_rows >= max(1, len(rows) // 2):
        reasons.append("sparse_rows")
    if list_like_cells > 0:
        reasons.append("list_like_cells")

    return len(reasons) == 0, reasons


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


def _pick_mode(table_mode: TableMode, rows: list[list[str]]) -> tuple[str, Optional[str]]:
    simple, reasons = analyze_table_complexity(rows)
    if table_mode == TableMode.HTML_ONLY:
        return "html", None
    if table_mode == TableMode.GFM_ONLY:
        if simple:
            return "gfm", None
        reason_text = ",".join(reasons) if reasons else "unknown"
        return "html", f"Requested gfm-only but table was unsafe for GFM ({reason_text}); used HTML fallback."
    if simple:
        return "gfm", None
    return "html", None


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
                table_candidates = page.find_tables() or []
                page_blocks: list[TableBlock] = []

                for index, table_obj in enumerate(table_candidates, start=1):
                    raw = table_obj.extract() or []
                    rows = [[_sanitize_cell(cell) for cell in row] for row in (raw or []) if row is not None]
                    if not rows:
                        continue

                    mode, fallback_reason = _pick_mode(table_mode, rows)
                    simple, reasons = analyze_table_complexity(rows)
                    if fallback_reason:
                        result.warnings.append(
                            WarningEntry(
                                code="TABLE_GFM_UNSAFE_FALLBACK_HTML",
                                message=fallback_reason,
                                page=page_number,
                                details={"table_index": index, "reasons": reasons},
                            )
                        )
                    elif mode == "html" and table_mode == TableMode.AUTO and not simple:
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
                    x0, top, x1, bottom = table_obj.bbox
                    page_blocks.append(
                        TableBlock(
                            page=page_number,
                            index=index,
                            mode=mode,
                            markdown=f"{comment}\n{rendered}",
                            top=float(top),
                        )
                    )
                    result.assets.append(
                        TableAsset(
                            page=page_number,
                            index=index,
                            mode=mode,
                            bbox=[float(x0), float(top), float(x1), float(bottom)],
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
