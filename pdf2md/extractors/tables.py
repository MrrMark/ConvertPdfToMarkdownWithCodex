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


@dataclass
class TableExtractionResult:
    warnings: list[WarningEntry] = field(default_factory=list)
    assets: list[TableAsset] = field(default_factory=list)
    blocks_by_page: dict[int, list[TableBlock]] = field(default_factory=dict)


def _sanitize_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return text


def is_simple_table(rows: list[list[str]]) -> bool:
    """Return True only when table is safe enough for GFM serialization."""
    if not rows:
        return False
    width = len(rows[0])
    if width == 0:
        return False
    for row in rows:
        if len(row) != width:
            return False
        for cell in row:
            if "\n" in cell:
                return False
    return True


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
    simple = is_simple_table(rows)
    if table_mode == TableMode.HTML_ONLY:
        return "html", None
    if table_mode == TableMode.GFM_ONLY:
        if simple:
            return "gfm", None
        return "html", "Requested gfm-only but table was unsafe for GFM; used HTML fallback."
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
                raw_tables = page.extract_tables() or []
                page_blocks: list[TableBlock] = []

                for index, raw in enumerate(raw_tables, start=1):
                    rows = [[_sanitize_cell(cell) for cell in row] for row in (raw or []) if row is not None]
                    if not rows:
                        continue

                    mode, fallback_reason = _pick_mode(table_mode, rows)
                    if fallback_reason:
                        result.warnings.append(
                            WarningEntry(
                                code="TABLE_GFM_UNSAFE_FALLBACK_HTML",
                                message=fallback_reason,
                                page=page_number,
                                details={"table_index": index},
                            )
                        )

                    rendered = _serialize_gfm(rows) if mode == "gfm" else _serialize_html(rows)
                    comment = f"<!-- table: page={page_number} index={index} mode={mode} -->"
                    page_blocks.append(
                        TableBlock(
                            page=page_number,
                            index=index,
                            mode=mode,
                            markdown=f"{comment}\n{rendered}",
                        )
                    )
                    result.assets.append(TableAsset(page=page_number, index=index, mode=mode))

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
