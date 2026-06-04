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


@dataclass(frozen=True)
class PageWorkerBatchInput:
    pdf_path: Path
    pages: tuple[int, ...]
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


def _failed_page_worker_result(
    *,
    page: int,
    message: str,
    started: float,
    pdf_open_count: int = 0,
) -> PageWorkerResult:
    result = PageWorkerResult(page=page, pdf_open_count=pdf_open_count)
    result.failed = True
    result.warnings.append(
        WarningEntry(
            code=WarningCode.TEXT_EXTRACTION_FAILED,
            message=message,
            page=page,
        )
    )
    result.duration_ms = max(int((perf_counter() - started) * 1000), 0)
    return result


def _extract_opened_page_worker(
    *,
    opened_pdf: object,
    batch_input: PageWorkerBatchInput,
    page_number: int,
    pdf_open_count: int,
) -> PageWorkerResult:
    started = perf_counter()
    result = PageWorkerResult(page=page_number, pdf_open_count=pdf_open_count)
    try:
        layout = extract_page_text_layout_result(
            batch_input.pdf_path,
            [page_number],
            password=batch_input.password,
            pdf=opened_pdf,
        )
        result.text_lines = layout.lines_by_page.get(page_number, [])
        result.raw_lines = layout.raw_lines_by_page.get(page_number, [])
        result.text_metadata = layout.metadata_by_page.get(page_number)
        result.page_text = "\n".join(line.text for line in result.text_lines).strip()

        if batch_input.collect_table_candidates:
            page = opened_pdf.pages[page_number - 1]
            try:
                result.table_candidate_result = collect_table_candidates_for_page(page, page_number)
            except Exception as exc:  # noqa: BLE001
                result.table_candidate_result = PageTableCandidateResult(
                    page=page_number,
                    page_width=float(getattr(page, "width", 0.0)),
                    page_height=float(getattr(page, "height", 0.0)),
                )
                result.warnings.append(
                    WarningEntry(
                        code=WarningCode.TABLE_EXTRACTION_FAILED,
                        message=f"Page worker failed to collect table candidates on page {page_number}: {exc}",
                        page=page_number,
                        details={"phase": "table_candidate_collection"},
                    )
                )
    except Exception as exc:  # noqa: BLE001
        result.failed = True
        result.warnings.append(
            WarningEntry(
                code=WarningCode.TEXT_EXTRACTION_FAILED,
                message=f"Page worker failed on page {page_number}: {exc}",
                page=page_number,
            )
        )
    finally:
        result.duration_ms = max(int((perf_counter() - started) * 1000), 0)
    return result


def extract_page_worker(worker_input: PageWorkerInput) -> PageWorkerResult:
    """Extract one page of text layout and optional table candidates."""
    return extract_page_worker_batch(
        PageWorkerBatchInput(
            pdf_path=worker_input.pdf_path,
            pages=(worker_input.page,),
            password=worker_input.password,
            collect_table_candidates=worker_input.collect_table_candidates,
        )
    )[0]


def extract_page_worker_batch(worker_input: PageWorkerBatchInput) -> list[PageWorkerResult]:
    """Extract a chunk of pages while opening the PDF only once for the worker."""
    started = perf_counter()
    if not worker_input.pages:
        return []

    try:
        with pdfplumber.open(str(worker_input.pdf_path), password=worker_input.password) as opened_pdf:
            return [
                _extract_opened_page_worker(
                    opened_pdf=opened_pdf,
                    batch_input=worker_input,
                    page_number=page_number,
                    pdf_open_count=1 if index == 0 else 0,
                )
                for index, page_number in enumerate(worker_input.pages)
            ]
    except Exception as exc:  # noqa: BLE001
        return [
            _failed_page_worker_result(
                page=page_number,
                message=f"Page worker failed on page {page_number}: {exc}",
                started=started,
                pdf_open_count=1 if index == 0 else 0,
            )
            for index, page_number in enumerate(worker_input.pages)
        ]
