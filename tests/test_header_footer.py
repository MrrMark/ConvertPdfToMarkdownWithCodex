from pdf2md.extractors.header_footer import remove_repeated_header_footer
from pdf2md.extractors.text import TextLine


def _line(text: str, top: float) -> TextLine:
    return TextLine(text=text, top=top, bottom=top + 10.0, x0=72.0, x1=240.0)


def test_remove_repeated_header_footer_removes_only_margin_repeats() -> None:
    lines_by_page = {
        1: [_line("Spec Header", 40), _line("Body repeat", 300), _line("Page 1", 780)],
        2: [_line("Spec Header", 40), _line("Body repeat", 300), _line("Page 2", 780)],
        3: [_line("Spec Header", 40), _line("Body repeat", 300), _line("Page 3", 780)],
    }

    result = remove_repeated_header_footer(lines_by_page, {1: 842.0, 2: 842.0, 3: 842.0})

    assert {page: [line.text for line in lines] for page, lines in result.lines_by_page.items()} == {
        1: ["Body repeat"],
        2: ["Body repeat"],
        3: ["Body repeat"],
    }
    assert len(result.suppressed_lines) == 6
    assert {item.reason for item in result.suppressed_lines} == {"REPEATED_HEADER_FOOTER"}


def test_remove_repeated_header_footer_requires_multiple_pages() -> None:
    lines_by_page = {
        1: [_line("Spec Header", 40), _line("Body", 300)],
        2: [_line("Spec Header", 40), _line("Body", 300)],
    }

    result = remove_repeated_header_footer(lines_by_page, {1: 842.0, 2: 842.0})

    assert [line.text for line in result.lines_by_page[1]] == ["Spec Header", "Body"]
    assert result.suppressed_lines == []
