from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

import pdfplumber

from pdf2md.constants import WarningCode
from pdf2md.extractors.tables import PageTableCandidateResult, collect_table_candidates_for_page
from pdf2md.extractors.text import PageLayoutMetadata, TextLine, extract_page_text_layout_result
from pdf2md.models import WarningEntry


@dataclass(frozen=True)
class PageWorkerInput:
    pdf_path: Path
    page: int
    password: str | None = None
    collect_table_candidates: bool = False


@dataclass
class PageWorkerResult:
    page: int
    text_lines: list[TextLine] = field(default_factory=list)
    raw_lines: list[dict] = field(default_factory=list)
    text_metadata: PageLayoutMetadata | None = None
    page_text: str = ""
    table_assets: list[object] = field(default_factory=list)
    table_blocks: list[object] = field(default_factory=list)
    rag_tables: list[dict] = field(default_factory=list)
    table_debug_candidates: list[dict] = field(default_factory=list)
    table_candidate_result: PageTableCandidateResult | None = None
    warnings: list[WarningEntry] = field(default_factory=list)
    failed: bool = False
    duration_ms: int = 0
    pdf_open_count: int = 0


def extract_page_worker(worker_input: PageWorkerInput) -> PageWorkerResult:
    """Extract page-local text layout and optional table candidates in an isolated PDF open."""
    started = perf_counter()
    result = PageWorkerResult(page=worker_input.page, pdf_open_count=1)
    try:
        with pdfplumber.open(str(worker_input.pdf_path), password=worker_input.password) as opened_pdf:
            layout = extract_page_text_layout_result(
                worker_input.pdf_path,
                [worker_input.page],
                password=worker_input.password,
                pdf=opened_pdf,
            )
            if worker_input.collect_table_candidates:
                page = opened_pdf.pages[worker_input.page - 1]
                try:
                    result.table_candidate_result = collect_table_candidates_for_page(page, worker_input.page)
                except Exception as exc:  # noqa: BLE001
                    result.table_candidate_result = PageTableCandidateResult(
                        page=worker_input.page,
                        page_width=float(getattr(page, "width", 0.0)),
                        page_height=float(getattr(page, "height", 0.0)),
                    )
                    result.warnings.append(
                        WarningEntry(
                            code=WarningCode.TABLE_EXTRACTION_FAILED,
                            message=f"Page worker failed to collect table candidates on page {worker_input.page}: {exc}",
                            page=worker_input.page,
                            details={"phase": "table_candidate_collection"},
                        )
                    )
        result.text_lines = layout.lines_by_page.get(worker_input.page, [])
        result.raw_lines = layout.raw_lines_by_page.get(worker_input.page, [])
        result.text_metadata = layout.metadata_by_page.get(worker_input.page)
        result.page_text = "\n".join(line.text for line in result.text_lines).strip()
    except Exception as exc:  # noqa: BLE001
        result.failed = True
        result.warnings.append(
            WarningEntry(
                code=WarningCode.TEXT_EXTRACTION_FAILED,
                message=f"Page worker failed on page {worker_input.page}: {exc}",
                page=worker_input.page,
            )
        )
    finally:
        result.duration_ms = max(int((perf_counter() - started) * 1000), 0)
    return result
