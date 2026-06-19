from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from pdf2md.models import ImageAsset, PageResult, TableAsset


@dataclass(frozen=True)
class SourceRef:
    """Stable internal pointer from a document IR node to extracted source evidence."""

    source_type: str
    source_id: str
    page: int
    bbox: list[float] | None = None
    source_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready source reference record."""
        record: dict[str, Any] = {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "page": self.page,
        }
        if self.bbox is not None:
            record["bbox"] = list(self.bbox)
        if self.source_index is not None:
            record["source_index"] = self.source_index
        if self.metadata:
            record["metadata"] = dict(sorted(self.metadata.items()))
        return record


@dataclass(frozen=True)
class DocumentTextBlock:
    """Internal text block representation shared by Markdown and RAG serializers."""

    page: int
    block_index: int
    block_id: str
    block_type: str
    text: str
    bbox: list[float]
    line_indices: list[int]
    heading_path: list[str]
    parent_heading_block_id: str | None
    classification_confidence: float
    classification_reasons: list[str] = field(default_factory=list)
    source_ref: SourceRef | None = None

    def to_legacy_record(self) -> dict[str, Any]:
        """Return the current public text block record without changing output schema."""
        return {
            "block_id": self.block_id,
            "page": self.page,
            "block_index": self.block_index,
            "block_type": self.block_type,
            "text": self.text,
            "bbox": list(self.bbox),
            "line_indices": list(self.line_indices),
            "heading_path": list(self.heading_path),
            "parent_heading_block_id": self.parent_heading_block_id,
            "classification_confidence": self.classification_confidence,
            "classification_reasons": list(self.classification_reasons),
        }


@dataclass(frozen=True)
class TableBlockRef:
    """Internal reference to a table block/asset without copying table payloads."""

    page: int
    table_index: int
    table_id: str
    mode: str | None = None
    bbox: list[float] | None = None
    anchor_line_index: int | None = None
    source_ref: SourceRef | None = None


@dataclass(frozen=True)
class FigureBlockRef:
    """Internal reference to a figure/image block without copying binary assets."""

    page: int
    figure_index: int
    figure_id: str
    bbox: list[float] | None = None
    anchor_line_index: int | None = None
    source_ref: SourceRef | None = None


@dataclass(frozen=True)
class PageLayoutSummary:
    """Compact per-page layout evidence used by downstream serializers."""

    page: int
    reading_order_strategy: str = "top"
    column_count_estimate: int = 1
    char_count: int = 0
    text_block_count: int = 0
    table_count: int = 0
    figure_count: int = 0
    used_ocr: bool = False


@dataclass(frozen=True)
class Pdf2MdPage:
    """Internal document page grouping text, table, figure, and layout nodes."""

    page: int
    layout: PageLayoutSummary
    text_blocks: list[DocumentTextBlock] = field(default_factory=list)
    table_blocks: list[TableBlockRef] = field(default_factory=list)
    figure_blocks: list[FigureBlockRef] = field(default_factory=list)


@dataclass(frozen=True)
class Pdf2MdDocument:
    """Internal conversion document IR; not a public artifact schema."""

    source_sha256: str
    selected_pages: list[int]
    pages: list[Pdf2MdPage] = field(default_factory=list)

    @property
    def pages_by_number(self) -> dict[int, Pdf2MdPage]:
        return {page.page: page for page in self.pages}


def build_pdf2md_document_ir(
    *,
    source_sha256: str,
    selected_pages: Iterable[int],
    text_blocks_by_page: Mapping[int, Iterable[Any]],
    page_results: Mapping[int, PageResult] | None = None,
    table_assets: Iterable[TableAsset | Mapping[str, Any]] | None = None,
    figure_assets: Iterable[ImageAsset | Mapping[str, Any]] | None = None,
) -> Pdf2MdDocument:
    """Build the internal document IR from current pipeline extraction outputs."""
    page_numbers = sorted(dict.fromkeys(int(page) for page in selected_pages))
    page_results = page_results or {}
    tables_by_page = _group_table_refs(table_assets or [])
    figures_by_page = _group_figure_refs(figure_assets or [])
    text_by_page: dict[int, list[DocumentTextBlock]] = {
        int(page): [_coerce_text_block(block) for block in blocks]
        for page, blocks in text_blocks_by_page.items()
    }

    pages: list[Pdf2MdPage] = []
    for page in page_numbers:
        text_blocks = text_by_page.get(page, [])
        table_blocks = tables_by_page.get(page, [])
        figure_blocks = figures_by_page.get(page, [])
        page_result = page_results.get(page)
        pages.append(
            Pdf2MdPage(
                page=page,
                layout=_build_layout_summary(
                    page=page,
                    page_result=page_result,
                    text_block_count=len(text_blocks),
                    table_count=len(table_blocks),
                    figure_count=len(figure_blocks),
                ),
                text_blocks=text_blocks,
                table_blocks=table_blocks,
                figure_blocks=figure_blocks,
            )
        )

    return Pdf2MdDocument(
        source_sha256=source_sha256,
        selected_pages=page_numbers,
        pages=pages,
    )


def ir_text_blocks_by_page(document: Pdf2MdDocument) -> dict[int, list[dict[str, Any]]]:
    """Return legacy text block records grouped for the Markdown serializer."""
    return {
        page.page: [block.to_legacy_record() for block in page.text_blocks]
        for page in document.pages
    }


def ir_text_block_records(document: Pdf2MdDocument) -> list[dict[str, Any]]:
    """Return legacy text block records in deterministic page/block order."""
    records: list[dict[str, Any]] = []
    for page in document.pages:
        records.extend(block.to_legacy_record() for block in page.text_blocks)
    return records


def _build_layout_summary(
    *,
    page: int,
    page_result: PageResult | None,
    text_block_count: int,
    table_count: int,
    figure_count: int,
) -> PageLayoutSummary:
    if page_result is None:
        return PageLayoutSummary(
            page=page,
            text_block_count=text_block_count,
            table_count=table_count,
            figure_count=figure_count,
        )
    return PageLayoutSummary(
        page=page_result.page,
        reading_order_strategy=page_result.reading_order_strategy,
        column_count_estimate=page_result.column_count_estimate,
        char_count=page_result.char_count,
        text_block_count=text_block_count,
        table_count=table_count,
        figure_count=figure_count,
        used_ocr=page_result.used_ocr,
    )


def _coerce_text_block(block: Any) -> DocumentTextBlock:
    record = block.to_record() if hasattr(block, "to_record") else dict(block)
    page = int(record["page"])
    block_index = int(record["block_index"])
    block_id = str(record.get("block_id") or f"page-{page:04d}-block-{block_index:04d}")
    bbox = [float(value) for value in record.get("bbox", [])]
    return DocumentTextBlock(
        page=page,
        block_index=block_index,
        block_id=block_id,
        block_type=str(record.get("block_type", "paragraph")),
        text=str(record.get("text", "")),
        bbox=bbox,
        line_indices=[int(value) for value in record.get("line_indices", [])],
        heading_path=[str(value) for value in record.get("heading_path", [])],
        parent_heading_block_id=record.get("parent_heading_block_id"),
        classification_confidence=float(record.get("classification_confidence", 0.0)),
        classification_reasons=[str(value) for value in record.get("classification_reasons", [])],
        source_ref=SourceRef(
            source_type="text_block",
            source_id=block_id,
            page=page,
            bbox=bbox,
            source_index=block_index,
        ),
    )


def _group_table_refs(assets: Iterable[TableAsset | Mapping[str, Any]]) -> dict[int, list[TableBlockRef]]:
    refs_by_page: dict[int, list[TableBlockRef]] = {}
    for asset in assets:
        record = _model_or_mapping(asset)
        page = int(record["page"])
        table_index = int(record["index"])
        table_id = str(record.get("table_id") or f"page-{page:04d}-table-{table_index:04d}")
        bbox = _optional_float_list(record.get("bbox"))
        refs_by_page.setdefault(page, []).append(
            TableBlockRef(
                page=page,
                table_index=table_index,
                table_id=table_id,
                mode=record.get("mode"),
                bbox=bbox,
                anchor_line_index=record.get("anchor_line_index"),
                source_ref=SourceRef(
                    source_type="table",
                    source_id=table_id,
                    page=page,
                    bbox=bbox,
                    source_index=table_index,
                ),
            )
        )
    return {
        page: sorted(refs, key=lambda ref: ref.table_index)
        for page, refs in sorted(refs_by_page.items())
    }


def _group_figure_refs(assets: Iterable[ImageAsset | Mapping[str, Any]]) -> dict[int, list[FigureBlockRef]]:
    refs_by_page: dict[int, list[FigureBlockRef]] = {}
    for asset in assets:
        record = _model_or_mapping(asset)
        page = int(record["page"])
        figure_index = int(record["index"])
        figure_id = str(record.get("figure_id") or f"page-{page:04d}-figure-{figure_index:04d}")
        bbox = _optional_float_list(record.get("bbox"))
        refs_by_page.setdefault(page, []).append(
            FigureBlockRef(
                page=page,
                figure_index=figure_index,
                figure_id=figure_id,
                bbox=bbox,
                anchor_line_index=record.get("anchor_line_index"),
                source_ref=SourceRef(
                    source_type="figure",
                    source_id=figure_id,
                    page=page,
                    bbox=bbox,
                    source_index=figure_index,
                ),
            )
        )
    return {
        page: sorted(refs, key=lambda ref: ref.figure_index)
        for page, refs in sorted(refs_by_page.items())
    }


def _model_or_mapping(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return dict(value)


def _optional_float_list(value: Any) -> list[float] | None:
    if value is None:
        return None
    return [float(item) for item in value]
