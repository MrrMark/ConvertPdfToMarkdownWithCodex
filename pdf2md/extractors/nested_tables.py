"""Recover child grids only when original PDF cell boundaries establish ownership."""

from __future__ import annotations

from copy import deepcopy
import html
from typing import Any, Callable

TOLERANCE = 1.0
MAX_DEPTH = 8


def _contains(outer: Any, inner: Any) -> bool:
    return (
        outer[0] - TOLERANCE <= inner[0]
        and outer[1] - TOLERANCE <= inner[1]
        and outer[2] + TOLERANCE >= inner[2]
        and outer[3] + TOLERANCE >= inner[3]
    )


def _area(box: Any) -> float:
    return (box[2] - box[0]) * (box[3] - box[1])


def recover_cell_structure(
    table: Any,
    tables: list[Any],
    rows: list[list[str]],
    process: Callable[[Any], list[list[str]]],
    sanitize: Callable[[Any], str],
) -> tuple[list[dict] | None, str | None]:
    """Return a complete bounded tree, or preserve flat text with a loss reason.

    Only line-derived tables are supplied by the caller. Strictly decreasing
    areas and a depth bound prevent cycles, even for malformed geometry.
    """
    descendants = [
        other
        for other in tables
        if other is not table
        and _area(other.bbox) < _area(table.bbox) - TOLERANCE
        and _contains(table.bbox, other.bbox)
    ]
    if not descendants:
        return None, None

    def build(current: Any, current_rows: list[list[str]], depth: int) -> list[dict]:
        if depth > MAX_DEPTH:
            raise ValueError("nested_depth_limit")
        raw_rows = current.extract() or []
        if len(raw_rows) != len(current_rows):
            raise ValueError("parent_row_mapping_ambiguous")
        cells = []
        raw_columns: dict[int, set[int]] = {}
        assignments = []
        for r, row in enumerate(current_rows):
            used = set()
            for c, text in enumerate(row):
                matches = [
                    i
                    for i, raw in enumerate(raw_rows[r])
                    if i not in used and current.rows[r].cells[i] is not None and sanitize(raw) == text
                ]
                if not matches and not text:
                    # A None slot may be covered by a merged neighbour. Verify
                    # coverage after deriving spans from physical boundaries.
                    continue
                if len(matches) != 1:
                    raise ValueError("parent_cell_mapping_ambiguous")
                i = matches[0]
                used.add(i)
                raw_columns.setdefault(i, set()).add(c)
                assignments.append((r, c, i, text))
        for r, c, i, text in assignments:
            box = current.rows[r].cells[i]
            next_column = next(
                (j for j in range(i + 1, len(raw_rows[r])) if current.rows[r].cells[j] is not None), len(raw_rows[r])
            )
            columns = {column for j in range(i, next_column) for column in raw_columns.get(j, set())}
            col_span = max(columns | {c}) - c + 1
            row_span = sum(
                1 for row in current.rows[r:] if row.bbox[1] >= box[1] - TOLERANCE and row.bbox[3] <= box[3] + TOLERANCE
            )
            cells.append(
                dict(
                    row=r,
                    column=c,
                    row_span=max(1, row_span),
                    col_span=col_span,
                    bbox=list(box),
                    raw_text=text,
                    text=text,
                    children=[],
                )
            )
        covered = set()
        for cell in cells:
            for r in range(cell["row"], cell["row"] + cell["row_span"]):
                for c in range(cell["column"], cell["column"] + cell["col_span"]):
                    if r >= len(current_rows) or c >= len(current_rows[r]) or (r, c) in covered:
                        raise ValueError("merged_cell_mapping_ambiguous")
                    covered.add((r, c))
        if covered != {(r, c) for r, row in enumerate(current_rows) for c in range(len(row))}:
            raise ValueError("missing_cell_boundary")
        inside = [
            other
            for other in descendants
            if other is not current
            and _area(other.bbox) < _area(current.bbox) - TOLERANCE
            and _contains(current.bbox, other.bbox)
        ]
        direct = [
            child
            for child in inside
            if not any(
                other is not child
                and _area(other.bbox) > _area(child.bbox) + TOLERANCE
                and _contains(other.bbox, child.bbox)
                for other in inside
            )
        ]
        direct.sort(key=lambda child: (child.bbox[1], child.bbox[0], child.bbox[3], child.bbox[2]))
        for child in direct:
            owners = [cell for cell in cells if _contains(cell["bbox"], child.bbox)]
            if len(owners) != 1:
                raise ValueError("child_crosses_parent_cells")
            owner = owners[0]
            if any(
                _area(existing["bbox"]) == _area(child.bbox) and _contains(existing["bbox"], child.bbox)
                for existing in owner["children"]
            ):
                raise ValueError("duplicate_child_boundary")
            if any(min(existing['bbox'][2], child.bbox[2]) - max(existing['bbox'][0], child.bbox[0]) > TOLERANCE
                   and min(existing['bbox'][3], child.bbox[3]) - max(existing['bbox'][1], child.bbox[1]) > TOLERANCE
                   for existing in owner['children']):
                raise ValueError("overlapping_child_boundaries")
            child_rows = process(child.extract() or [])
            owner["children"].append(dict(bbox=list(child.bbox), cells=build(child, child_rows, depth + 1)))
        for cell in cells:
            if cell["children"]:
                # Extract only the parent's own characters. Child text remains
                # once in HTML and unchanged in raw_text for existing RAG rows.
                boxes = [child["bbox"] for child in cell["children"]]
                chars = [
                    char
                    for char in current.page.chars
                    if _contains(cell["bbox"], (char["x0"], char["top"], char["x1"], char["bottom"]))
                    and not any(
                        box[0] <= (char["x0"] + char["x1"]) / 2 <= box[2]
                        and box[1] <= (char["top"] + char["bottom"]) / 2 <= box[3]
                        for box in boxes
                    )
                ]
                from pdfplumber.utils import extract_text

                visible_chars = [char for char in chars if str(char.get('text', '')).strip()]
                if visible_chars and max(char['bottom'] for char in visible_chars) > min(box[1] for box in boxes) + TOLERANCE:
                    raise ValueError("parent_text_interleaves_children")
                cell["text"] = sanitize(extract_text(chars) or "")
        return cells

    try:
        return build(table, rows, 0), None
    except ValueError as exc:
        return None, str(exc)


def assign_structure_ids(cells: list[dict], table_id: str) -> list[dict]:
    """Assign stable IDs from parent ownership and zero-based cell positions."""
    result = deepcopy(cells)
    for cell in result:
        cell["id"] = f"{table_id}-cell-{cell['row']:04d}-{cell['column']:04d}"
        for index, child in enumerate(cell["children"], start=1):
            child["id"] = f"{cell['id']}-table-{index:04d}"
            child["cells"] = assign_structure_ids(child["cells"], child["id"])
    return result


def serialize_cell_structure(cells: list[dict]) -> str:
    """Render nested cells with escaped source text and explicit spans."""
    lines = ["<table>"]
    for row in sorted({cell["row"] for cell in cells}):
        lines.append("  <tr>")
        for cell in sorted((cell for cell in cells if cell["row"] == row), key=lambda cell: cell["column"]):
            tag = "th" if row == 0 else "td"
            spans = "".join(
                f' {name}="{cell[key]}"'
                for name, key in [("rowspan", "row_span"), ("colspan", "col_span")]
                if cell[key] > 1
            )
            content = html.escape(cell["text"], quote=True)
            content += "".join(serialize_cell_structure(child["cells"]) for child in cell["children"])
            lines.append(f"    <{tag}{spans}>{content}</{tag}>")
        lines.append("  </tr>")
    lines.append("</table>")
    return "\n".join(lines)
