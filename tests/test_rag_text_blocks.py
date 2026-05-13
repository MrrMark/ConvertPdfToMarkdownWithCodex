from __future__ import annotations

import json

from pdf2md.models import LineType, NormalizedLine
from pdf2md.serializers.markdown import serialize_markdown_blocks_result
from pdf2md.serializers.rag_text_blocks import build_text_blocks, serialize_text_blocks_jsonl


def _line(
    text: str,
    index: int,
    *,
    top: float,
    size: float | None = 10.0,
    line_type: LineType = LineType.BODY_LINE,
    x0: float = 72.0,
    style: str | None = "regular",
    y_band: str = "middle",
) -> NormalizedLine:
    return NormalizedLine(
        page=1,
        index=index,
        text=text,
        line_type=line_type,
        top=top,
        bottom=top + (size or 10.0),
        x0=x0,
        x1=x0 + max(len(text) * 5.0, 10.0),
        font_size=size,
        font_family="Courier" if style == "monospace" else "Helvetica",
        font_style_hint=style,
        line_height=size,
        left_indent=x0,
        right_indent=500.0 - x0,
        y_band=y_band,
        source_line_indices=[index],
    )


def test_large_font_title_becomes_heading_block() -> None:
    result = build_text_blocks(
        {
            1: [
                _line("Architecture Overview", 0, top=60, size=20),
                _line("This paragraph remains body text.", 1, top=110, size=10),
            ]
        }
    )

    assert result.font_heading_candidate_count == 1
    assert result.records[0]["block_type"] == "heading"
    assert result.records[0]["heading_path"] == ["Architecture Overview"]
    assert result.records[1]["parent_heading_block_id"] == "page-0001-block-0001"


def test_title_only_large_font_line_becomes_heading_block() -> None:
    result = build_text_blocks({1: [_line("Standalone Title", 0, top=60, size=20)]})

    assert result.records[0]["block_type"] == "heading"
    assert result.records[0]["classification_reasons"] == ["large_font", "surrounding_whitespace"]


def test_uppercase_body_is_not_heading_without_font_signal() -> None:
    result = build_text_blocks({1: [_line("THIS IS IMPORTANT BODY TEXT", 0, top=80, size=10)]})

    assert result.records[0]["block_type"] == "paragraph"
    assert result.font_heading_candidate_count == 0


def test_grouped_list_and_code_blocks_are_serialized_for_rag_and_markdown() -> None:
    result = build_text_blocks(
        {
            1: [
                _line("- first", 0, top=100, line_type=LineType.LIST_ITEM),
                _line("- second", 1, top=114, line_type=LineType.LIST_ITEM),
                _line("value = 1", 2, top=150, style="monospace"),
                _line("return value", 3, top=164, style="monospace"),
            ]
        }
    )

    assert [record["block_type"] for record in result.records] == ["list", "code"]
    assert result.records[0]["text"] == "- first\n- second"
    assert result.records[1]["line_indices"] == [2, 3]
    jsonl = serialize_text_blocks_jsonl(result.records)
    assert json.loads(jsonl.splitlines()[0])["block_type"] == "list"

    markdown = serialize_markdown_blocks_result(
        {1: result.records},
        keep_page_markers=False,
    ).markdown
    assert "- first\n- second" in markdown
    assert "```text\nvalue = 1\nreturn value\n```" in markdown


def test_bottom_small_font_marker_becomes_footnote_and_ocr_lines_fallback_to_paragraph() -> None:
    footnote_result = build_text_blocks(
        {
            1: [
                _line("Body text.", 0, top=100, size=10),
                _line("[1] Device-specific note", 1, top=700, size=7, y_band="bottom"),
            ]
        }
    )
    assert footnote_result.footnote_candidate_count == 1
    assert footnote_result.records[1]["block_type"] == "footnote"

    ocr_result = build_text_blocks(
        {
            1: [
                _line("OCR GENERATED TITLE", 0, top=0, size=None, style=None, y_band="top"),
            ]
        }
    )
    assert ocr_result.records[0]["block_type"] == "paragraph"
