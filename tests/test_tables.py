from pdf2md.extractors.tables import analyze_table_complexity, is_simple_table


def test_is_simple_table_true_for_rectangular_single_line_cells() -> None:
    rows = [
        ["col1", "col2"],
        ["a", "b"],
    ]
    assert is_simple_table(rows) is True


def test_is_simple_table_false_for_multiline_cell() -> None:
    rows = [
        ["col1", "col2"],
        ["line1\nline2", "b"],
    ]
    assert is_simple_table(rows) is False


def test_analyze_table_complexity_detects_sparse_and_long_cells() -> None:
    rows = [
        ["", ""],
        ["A" * 130, ""],
    ]
    simple, reasons = analyze_table_complexity(rows)
    assert simple is False
    assert "SPARSE_LAYOUT" in reasons
    assert "AMBIGUOUS_GRID" in reasons
