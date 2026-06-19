from __future__ import annotations

from pdf2md.document_ir import build_pdf2md_document_ir, ir_text_block_records, ir_text_blocks_by_page
from pdf2md.models import ImageAsset, LineType, NormalizedLine, PageResult, TableAsset
from pdf2md.serializers.markdown import serialize_markdown_blocks_result
from pdf2md.serializers.rag_text_blocks import build_text_blocks


def _line(
    text: str,
    index: int,
    *,
    top: float,
    line_type: LineType = LineType.BODY_LINE,
) -> NormalizedLine:
    return NormalizedLine(
        page=1,
        index=index,
        text=text,
        line_type=line_type,
        top=top,
        bottom=top + 10.0,
        x0=72.0,
        x1=72.0 + max(len(text) * 5.0, 10.0),
        font_size=10.0,
        font_family="Helvetica",
        font_style_hint="regular",
        line_height=10.0,
        left_indent=72.0,
        right_indent=428.0,
        y_band="middle",
        source_line_indices=[index],
    )


def test_document_ir_preserves_legacy_text_block_records_for_serializers() -> None:
    text_block_result = build_text_blocks(
        {
            1: [
                _line("1.1 Overview", 0, top=72.0, line_type=LineType.HEADING_INDEX),
                _line("Preserve this paragraph.", 1, top=96.0),
            ]
        }
    )

    document = build_pdf2md_document_ir(
        source_sha256="abc123",
        selected_pages=[1],
        text_blocks_by_page=text_block_result.blocks_by_page,
        page_results={
            1: PageResult(
                page=1,
                char_count=36,
                reading_order_strategy="layout",
                column_count_estimate=2,
            )
        },
    )

    assert document.source_sha256 == "abc123"
    assert document.pages[0].layout.reading_order_strategy == "layout"
    assert document.pages[0].layout.column_count_estimate == 2
    assert ir_text_block_records(document) == text_block_result.records
    assert ir_text_blocks_by_page(document) == {1: text_block_result.records}

    markdown = serialize_markdown_blocks_result(
        page_text_blocks=ir_text_blocks_by_page(document),
        keep_page_markers=True,
    ).markdown
    assert "<!-- page: 1 -->" in markdown
    assert "## 1.1 Overview" in markdown
    assert "Preserve this paragraph." in markdown


def test_document_ir_groups_table_and_figure_refs_without_public_schema_changes() -> None:
    document = build_pdf2md_document_ir(
        source_sha256="abc123",
        selected_pages=[2, 1],
        text_blocks_by_page={1: [], 2: []},
        table_assets=[
            TableAsset(
                page=2,
                index=3,
                mode="html",
                bbox=[10.0, 20.0, 30.0, 40.0],
                anchor_line_index=4,
            )
        ],
        figure_assets=[
            ImageAsset(
                page=2,
                index=1,
                path="assets/images/page-0002-figure-001.png",
                bbox=[50.0, 60.0, 70.0, 80.0],
                anchor_line_index=9,
            )
        ],
    )

    assert document.selected_pages == [1, 2]
    assert [page.page for page in document.pages] == [1, 2]
    assert document.pages_by_number[1].layout.table_count == 0
    assert document.pages_by_number[2].layout.table_count == 1
    assert document.pages_by_number[2].layout.figure_count == 1

    table_ref = document.pages_by_number[2].table_blocks[0]
    assert table_ref.table_id == "page-0002-table-0003"
    assert table_ref.source_ref is not None
    assert table_ref.source_ref.to_record() == {
        "source_type": "table",
        "source_id": "page-0002-table-0003",
        "page": 2,
        "bbox": [10.0, 20.0, 30.0, 40.0],
        "source_index": 3,
    }

    figure_ref = document.pages_by_number[2].figure_blocks[0]
    assert figure_ref.figure_id == "page-0002-figure-0001"
    assert figure_ref.source_ref is not None
    assert figure_ref.source_ref.to_record()["source_type"] == "figure"
