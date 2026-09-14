"""Offline source-truth checks, independent of artifact integrity checks.

Truth is authored from the source PDF. Output artifacts are observations only.
Reports intentionally omit source text so aggregate reports can be shared.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TruthPage(BaseModel):
    """Map an output page to the original physical and printed page."""

    model_config = ConfigDict(extra="forbid")
    page: int = Field(gt=0)
    physical_page: int = Field(gt=0)
    printed_page: str | None = None


class TruthCheck(BaseModel):
    """One narrow source assertion and, optionally, its exact known failures."""

    model_config = ConfigDict(extra="forbid")
    check_id: str = Field(min_length=1)
    kind: Literal[
        "text_sequence", "table_count", "table_cell", "nested_table",
        "figure_region", "no_empty_tables", "no_decorative_ocr",
    ]
    page: int = Field(gt=0)
    record_id: str | None = None
    tokens: list[str] = Field(default_factory=list)
    count: int | None = Field(default=None, ge=0)
    bbox: tuple[float, float, float, float] | None = None
    minimum_iou: float = Field(default=0.7, gt=0, le=1)
    row_label: str | None = None
    column: int | None = Field(default=None, ge=0)
    # Exact record IDs keep a known defect from hiding new failures on the same page.
    known_failure_records: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_check(self) -> TruthCheck:
        """Reject incomplete assertions instead of silently passing them."""
        if self.kind in {"text_sequence", "table_cell", "nested_table", "figure_region"} and (
            not self.tokens or any(not token.strip() for token in self.tokens)
        ):
            raise ValueError(f"{self.kind} requires nonempty tokens")
        if self.kind in {"table_cell", "nested_table"} and (
            not self.record_id or not self.row_label or self.column is None
        ):
            raise ValueError("cell checks require record_id, row_label and column")
        if self.kind in {"table_count", "no_decorative_ocr"} and self.count is None:
            raise ValueError(f"{self.kind} requires count")
        if self.kind == "figure_region" and self.bbox is None:
            raise ValueError("figure_region requires bbox")
        if self.bbox and (self.bbox[0] >= self.bbox[2] or self.bbox[1] >= self.bbox[3]):
            raise ValueError("bbox must have positive area")
        if len(set(self.known_failure_records)) != len(self.known_failure_records):
            raise ValueError("duplicate known failure record")
        return self


class SourceTruth(BaseModel):
    """Versioned, manually reviewed source truth for one exact PDF slice."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"
    case_id: str = Field(min_length=1)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewed_from: Literal["rendered_source_pdf", "synthetic_source_definition"]
    review_note: str = Field(min_length=1)
    pages: list[TruthPage] = Field(min_length=1)
    checks: list[TruthCheck] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identifiers(self) -> SourceTruth:
        """Require unique checks and unambiguous page mappings."""
        page_ids = [page.page for page in self.pages]
        if len(set(page_ids)) != len(page_ids):
            raise ValueError("duplicate page mapping")
        if len({check.check_id for check in self.checks}) != len(self.checks):
            raise ValueError("duplicate check_id")
        if any(check.page not in page_ids for check in self.checks):
            raise ValueError("check has no page mapping")
        return self


class QualityCheckResult(BaseModel):
    """A source assertion result without copies of source text."""

    check_id: str
    kind: str
    page: int
    physical_page: int
    printed_page: str | None = None
    status: Literal["passed", "known_failure", "regression", "stale_allowlist"]
    failed_records: list[str] = Field(default_factory=list)
    expected_failure_records: list[str] = Field(default_factory=list)


class SourceQualityReport(BaseModel):
    """Keep regression-gate success distinct from source-quality success."""

    schema_version: Literal["1.0"] = "1.0"
    purpose: Literal["source_quality_evaluation"] = "source_quality_evaluation"
    case_id: str
    input_sha256: str
    truth_sha256: str
    quality_passed: bool
    gate_passed: bool
    results: list[QualityCheckResult]


@dataclass
class _Cell:
    text: list[str] = field(default_factory=list)
    children: list[_Table] = field(default_factory=list)
    has_image: bool = False


@dataclass
class _Table:
    record_id: str
    page: int
    rows: list[list[_Cell]] = field(default_factory=list)


class _TableParser(HTMLParser):
    """Parse actual HTML nesting; flattened words cannot satisfy a child table."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[_Table] = []
        self.stack: list[_Table] = []
        self.cells: list[_Cell | None] = []
        self.page = 0
        self.pending_id = ""

    def handle_comment(self, data: str) -> None:
        page = re.fullmatch(r"\s*page:\s*(\d+)\s*", data)
        if page:
            self.page = int(page[1])
        table = re.match(r"\s*table:\s*page=(\d+)\s+index=(\d+)", data)
        if table:
            self.pending_id = f"page-{int(table[1]):04d}-table-{int(table[2]):04d}"
            self.page = int(table[1])

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            table = _Table(self.pending_id or f"unidentified-table-{len(self.tables) + 1}", self.page)
            if self.stack and self.cells[-1] is not None:
                self.cells[-1].children.append(table)
            elif not self.stack:
                self.tables.append(table)
            self.stack.append(table)
            self.cells.append(None)
            self.pending_id = ""
        elif self.stack and tag == "tr":
            self.stack[-1].rows.append([])
        elif self.stack and tag in {"td", "th"}:
            if not self.stack[-1].rows:
                self.stack[-1].rows.append([])
            cell = _Cell()
            self.stack[-1].rows[-1].append(cell)
            self.cells[-1] = cell
        elif self.cells and self.cells[-1] is not None and tag == "img":
            self.cells[-1].has_image = bool(dict(attrs).get("src"))

    def handle_endtag(self, tag: str) -> None:
        if self.stack and tag == "table":
            self.stack.pop()
            self.cells.pop()
        elif self.cells and tag in {"td", "th"}:
            self.cells[-1] = None

    def handle_data(self, data: str) -> None:
        if self.cells and self.cells[-1] is not None:
            self.cells[-1].text.append(data)


def _normalized(text: str) -> str:
    # Whitespace and NFC only: case, punctuation and technical identifiers matter.
    return " ".join(unicodedata.normalize("NFC", text).split())


def _sequence_present(text: str, tokens: list[str]) -> bool:
    cursor = 0
    normalized = _normalized(text)
    for token in tokens:
        start = normalized.find(_normalized(token), cursor)
        if start < 0:
            return False
        cursor = start + len(_normalized(token))
    return True


def _table_text(table: _Table) -> str:
    return " ".join(
        " ".join(cell.text) + " " + " ".join(_table_text(child) for child in cell.children)
        for row in table.rows for cell in row
    )


def _table_has_content(table: _Table) -> bool:
    return any(
        _normalized(" ".join(cell.text)) or cell.has_image or any(_table_has_content(child) for child in cell.children)
        for row in table.rows for cell in row
    )


def _gfm_tables(markdown: str) -> list[_Table]:
    tables = []
    pattern = r"<!--\s*table:\s*page=(\d+)\s+index=(\d+)\s+mode=gfm\s*-->\s*\n((?:\|[^\n]*\n?)+)"
    for match in re.finditer(pattern, markdown):
        rows = []
        for line in match[3].splitlines():
            values = re.split(r"(?<!\\)\|", line.strip()[1:-1])
            if all(re.fullmatch(r"\s*:?-+:?\s*", value) for value in values):
                continue
            rows.append([_Cell(text=[unescape(value.strip().replace(r"\|", "|"))]) for value in values])
        tables.append(_Table(f"page-{int(match[1]):04d}-table-{int(match[2]):04d}", int(match[1]), rows))
    return tables


def _read_records(path: Path) -> list[dict[str, Any]]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(not isinstance(record, dict) for record in records):
        raise ValueError(f"Expected JSON objects: {path.name}")
    return records


def _iou(left: Any, right: tuple[float, float, float, float]) -> float:
    if not isinstance(left, (list, tuple)) or len(left) != 4:
        return 0.0
    x0, y0, x1, y1 = map(float, left)
    intersection = max(0.0, min(x1, right[2]) - max(x0, right[0])) * max(
        0.0, min(y1, right[3]) - max(y0, right[1])
    )
    union = max(0.0, x1 - x0) * max(0.0, y1 - y0) + (right[2] - right[0]) * (right[3] - right[1]) - intersection
    return intersection / union if union > 0 else 0.0


def _failed_records(check: TruthCheck, output: Path, markdown: str, tables: list[_Table]) -> list[str]:
    target = check.record_id or f"page-{check.page:04d}"
    page_tables = [table for table in tables if table.page == check.page]
    if check.kind == "no_empty_tables":
        return sorted(table.record_id for table in page_tables if not _table_has_content(table))
    if check.kind == "text_sequence":
        segments = re.split(r"<!--\s*page:\s*(\d+)\s*-->", markdown)
        text = "\n".join(segments[i + 1] for i in range(1, len(segments), 2) if int(segments[i]) == check.page)
        return [] if _sequence_present(unescape(text), check.tokens) else [target]
    if check.kind == "table_count":
        count = len(page_tables)
        return [] if count == check.count else [f"{target}:count={count}"]
    if check.kind in {"table_cell", "nested_table"}:
        for table in page_tables:
            if table.record_id != check.record_id:
                continue
            for row in table.rows:
                if not row or _normalized(" ".join(row[0].text)) != _normalized(check.row_label or ""):
                    continue
                if check.column is None or check.column >= len(row):
                    continue
                cell = row[check.column]
                cell_text = " ".join(cell.text) + " " + " ".join(_table_text(child) for child in cell.children)
                if check.kind == "table_cell" and _sequence_present(cell_text, check.tokens):
                    return []
                if check.kind == "nested_table" and any(
                    _sequence_present(_table_text(child), check.tokens) for child in cell.children
                ):
                    return []
        return [target]
    figures = _read_records(output / "figures_rag.jsonl")
    if len({figure["figure_id"] for figure in figures}) != len(figures):
        raise ValueError("duplicate figure_id in figures_rag.jsonl")
    if check.kind == "figure_region":
        for figure in figures:
            if figure.get("page") != check.page or figure.get("status") != "available":
                continue
            if check.bbox is None or _iou(figure.get("bbox"), check.bbox) < check.minimum_iou:
                continue
            if not _sequence_present(str(figure.get("caption_text") or ""), check.tokens):
                continue
            asset = figure.get("path")
            if isinstance(asset, str):
                path = (output / asset).resolve()
                if path.is_relative_to(output.resolve()) and path.is_file():
                    from PIL import Image

                    try:
                        with Image.open(path) as image:
                            image.verify()
                        return []
                    except (OSError, ValueError):
                        continue
        return [target]
    evidence = _read_records(output / "figure_ocr_evidence_rag.jsonl")
    figure_evidence = [record for record in evidence if record.get("target_type") == "figure"]
    by_id = {record["target_id"]: record for record in figure_evidence}
    if len(by_id) != len(figure_evidence):
        raise ValueError("duplicate figure target in figure_ocr_evidence_rag.jsonl")
    failed = []
    observed_count = 0
    for figure in figures:
        if figure.get("page") != check.page or figure.get("status") != "excluded":
            continue
        if "TINY_DECORATIVE" not in figure.get("classification_reasons", []):
            continue
        observed_count += 1
        record_id = str(figure["figure_id"])
        item = by_id.get(record_id)
        # Missing evidence must not make an unmeasured case appear to pass.
        if item is None or item.get("status") != "not_attempted" or item.get("rejected_reason") != "tiny_decorative":
            failed.append(record_id)
    if observed_count != check.count:
        failed.append(f"{target}:candidate_count={observed_count}")
    return sorted(failed)


def evaluate_source_quality(*, output_dir: Path, input_pdf: Path, truth_path: Path) -> SourceQualityReport:
    """Evaluate exact source assertions; invalid input raises instead of passing.

    Known failures keep the regression gate open but quality_passed remains false.
    A fixed known failure makes the allowlist stale and requires deliberate removal.
    """
    truth_bytes = truth_path.read_bytes()
    truth = SourceTruth.model_validate_json(truth_bytes)
    input_hash = hashlib.sha256(input_pdf.read_bytes()).hexdigest()
    if input_hash != truth.input_sha256:
        raise ValueError("input_sha256 does not match source truth")
    from pypdf import PdfReader

    page_count = len(PdfReader(input_pdf).pages)
    if sorted(page.page for page in truth.pages) != list(range(1, page_count + 1)):
        raise ValueError("truth must map every slice page exactly once")
    markdown = (output_dir / "document.md").read_text(encoding="utf-8")
    parser = _TableParser()
    parser.feed(markdown)
    parser.close()
    tables = parser.tables + _gfm_tables(markdown)
    mappings = {page.page: page for page in truth.pages}
    results = []
    for check in truth.checks:
        failed = _failed_records(check, output_dir, markdown, tables)
        known = sorted(check.known_failure_records)
        if failed:
            status = "known_failure" if failed == known else "regression"
        else:
            status = "stale_allowlist" if known else "passed"
        page = mappings[check.page]
        results.append(QualityCheckResult(
            check_id=check.check_id, kind=check.kind, page=check.page,
            physical_page=page.physical_page, printed_page=page.printed_page,
            status=status, failed_records=failed, expected_failure_records=known,
        ))
    return SourceQualityReport(
        case_id=truth.case_id, input_sha256=input_hash,
        truth_sha256=hashlib.sha256(truth_bytes).hexdigest(),
        quality_passed=all(not result.failed_records for result in results),
        gate_passed=all(result.status in {"passed", "known_failure"} for result in results),
        results=results,
    )
