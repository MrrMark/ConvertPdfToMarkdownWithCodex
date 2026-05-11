from pdf2md.extractors.text import TextLine, order_text_lines


def _line(text: str, top: float, x0: float, x1: float) -> TextLine:
    return TextLine(text=text, top=top, bottom=top + 10.0, x0=x0, x1=x1)


def test_order_text_lines_uses_two_column_order_only_when_clear() -> None:
    lines = [
        _line("L1", 100, 50, 240),
        _line("R1", 102, 330, 520),
        _line("L2", 120, 50, 240),
        _line("R2", 122, 330, 520),
        _line("L3", 140, 50, 240),
        _line("R3", 142, 330, 520),
        _line("L4", 160, 50, 240),
        _line("R4", 162, 330, 520),
    ]

    ordered, metadata = order_text_lines(lines, page_width=600.0, page_height=800.0)

    assert [line.text for line in ordered] == ["L1", "L2", "L3", "L4", "R1", "R2", "R3", "R4"]
    assert metadata.reading_order_strategy == "two_column_left_to_right"
    assert metadata.column_count_estimate == 2


def test_order_text_lines_keeps_top_order_for_unclear_layout() -> None:
    lines = [
        _line("A", 100, 50, 500),
        _line("B", 110, 70, 510),
        _line("C", 120, 50, 500),
    ]

    ordered, metadata = order_text_lines(lines, page_width=600.0, page_height=800.0)

    assert [line.text for line in ordered] == ["A", "B", "C"]
    assert metadata.reading_order_strategy == "top"
    assert metadata.column_count_estimate == 1
