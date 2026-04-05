from pdf2md.extractors.tables import (
    _compact_columns,
    _merge_columns,
    _split_notes,
    _quality_score,
    analyze_table_complexity,
    is_simple_table,
)


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


def test_compact_columns_removes_fully_empty_columns() -> None:
    rows = [
        ["A", "", "B", ""],
        ["1", "", "2", ""],
    ]
    compacted, removed = _compact_columns(rows)
    assert removed == 2
    assert compacted == [["A", "B"], ["1", "2"]]


def test_merge_columns_conservative_complements_neighbor() -> None:
    rows = [
        ["Bits", "", "Description"],
        ["63:0", "", "KV key"],
        ["", "M", ""],
        ["31:0", "", "Reserved"],
    ]
    merged, count = _merge_columns(rows)
    assert count == 1
    assert len(merged[0]) == 2
    assert merged[0] == ["Bits", "Description"]


def test_split_notes_and_empty_rows() -> None:
    rows = [
        ["Col1", "Col2"],
        ["", ""],
        ["Notes: 1. O optional", ""],
        ["A", "B"],
    ]
    normalized, notes, removed = _split_notes(rows)
    assert removed == 1
    assert notes == ["Notes: 1. O optional"]
    assert normalized == [["Col1", "Col2"], ["A", "B"]]


def test_quality_score_improves_after_sparse_recovery() -> None:
    raw = [
        ["", "Bits", "", "Description", ""],
        ["", "63:0", "", "KV key", ""],
        ["", "", "", "", ""],
    ]
    dense = [
        ["Bits", "Description"],
        ["63:0", "KV key"],
    ]
    raw_score = _quality_score(raw, removed_rows=0, compacted=0, merged=0)
    dense_score = _quality_score(dense, removed_rows=1, compacted=2, merged=1)
    assert dense_score > raw_score
