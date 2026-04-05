from pdf2md.extractors.structure_normalizer import BlockRegion, normalize_page_lines
from pdf2md.extractors.text import TextLine
from pdf2md.models import LineType


def _line(text: str, top: float, x0: float = 72.0) -> TextLine:
    return TextLine(
        text=text,
        top=top,
        bottom=top + 10.0,
        x0=x0,
        x1=x0 + max(len(text) * 5.0, 10.0),
    )


def test_heading_index_is_not_merged_with_body() -> None:
    result = normalize_page_lines(
        page=1,
        lines=[
            _line("2.2.1 Command Completion", 100),
            _line("This paragraph should", 120),
            _line("stay merged together", 132),
        ],
    )
    assert result.lines[0].line_type is LineType.HEADING_INDEX
    assert result.lines[0].text == "2.2.1 Command Completion"
    assert result.lines[1].line_type is LineType.BODY_LINE
    assert result.lines[1].text == "This paragraph should stay merged together"
    assert result.line_merge_count == 1


def test_near_duplicate_figure_caption_is_deduplicated() -> None:
    result = normalize_page_lines(
        page=2,
        lines=[
            _line("Figure 10: List – Command Dword 10", 200),
            _line("Figure 10: List – Command Dword 10", 214),
        ],
    )
    assert len(result.lines) == 1
    assert result.lines[0].line_type is LineType.FIGURE_CAPTION
    assert result.dedupe_count == 1
    assert result.deduplicated_blocks[0].reason == "NEAR_DUPLICATE_CAPTION"


def test_toc_line_is_not_reflowed() -> None:
    result = normalize_page_lines(
        page=3,
        lines=[
            _line("Figure 1: NVMe Family of Specifications ......... 5", 80),
            _line("Alpha", 100),
            _line("Beta", 112),
        ],
    )
    assert result.lines[0].line_type is LineType.TOC_LINE
    assert result.structure_line_count == 1
    assert result.lines[1].text == "Alpha Beta"


def test_hyphen_split_is_restored_on_merge() -> None:
    result = normalize_page_lines(
        page=4,
        lines=[
            _line("charac-", 50),
            _line("teristics", 62),
        ],
    )
    assert len(result.lines) == 1
    assert result.lines[0].text == "characteristics"


def test_line_suppression_for_overlapping_block() -> None:
    result = normalize_page_lines(
        page=5,
        lines=[
            _line("line inside table", 100, x0=100),
            _line("line outside table", 200, x0=100),
        ],
        block_regions=[BlockRegion(block_type="table", block_index=1, bbox=(90, 90, 220, 140))],
    )
    assert len(result.lines) == 1
    assert result.lines[0].text == "line outside table"
    assert result.suppressed_line_count == 1
    assert result.suppressed_lines[0].reason == "BLOCK_OVERLAP_SUPPRESSION"
