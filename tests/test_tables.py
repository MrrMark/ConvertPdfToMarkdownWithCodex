from types import SimpleNamespace

from pdf2md.extractors.tables import (
    _compact_columns,
    _pick_mode,
    _serialize_html,
    _serialize_markdown_forced,
    _merge_columns,
    _realign_header_columns,
    _split_notes,
    _quality_score,
    analyze_table_complexity,
    collect_table_candidates_for_page,
    extract_tables,
    is_simple_table,
)
from pdf2md.models import TableMode


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


def test_realign_header_columns_moves_header_to_data_column() -> None:
    rows = [
        ["", "Bits", "", "Description"],
        ["63:0", "", "KV key", ""],
    ]
    aligned, shifts = _realign_header_columns(rows)
    assert shifts == 2
    assert aligned[0] == ["Bits", "", "Description", ""]
    assert aligned[1] == ["63:0", "", "KV key", ""]


def test_html_serializer_escapes_cell_content() -> None:
    rendered = _serialize_html(
        rows=[["<head>", "A&B"], ['<script>alert("x")</script>', "safe"]],
        notes=["Note: 1 < 2 & 3"],
    )
    assert "&lt;head&gt;" in rendered
    assert "A&amp;B" in rendered
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in rendered
    assert "Note: 1 &lt; 2 &amp; 3" in rendered


def test_pick_mode_supports_new_html_and_markdown_modes() -> None:
    rows = [["A", "B"], ["1", "2"]]
    html_mode, _, _ = _pick_mode(TableMode.HTML, rows)
    markdown_mode, _, _ = _pick_mode(TableMode.MARKDOWN, rows)
    assert html_mode == "html"
    assert markdown_mode == "markdown"


def test_markdown_forced_serializer_fills_blank_headers_and_escapes_content() -> None:
    rendered = _serialize_markdown_forced(
        rows=[["", "Description"], ["Line|1", "alpha\nbeta"], ["", ""]],
        notes=["Notes: preserve original"],
    )
    assert "| Column 1 | Description |" in rendered
    assert "Line\\|1" in rendered
    assert "alpha<br>beta" in rendered
    assert "Notes: preserve original" in rendered
    assert "<table>" not in rendered


class _FakeTable:
    def __init__(self, bbox: tuple[float, float, float, float], rows: list[list[str]]) -> None:
        self.bbox = bbox
        self._rows = rows

    def extract(self) -> list[list[str]]:
        return self._rows


class _FakePage:
    width = 595.0
    height = 842.0

    def __init__(self, rows: list[list[str]]) -> None:
        self._rows = rows

    def find_tables(self, table_settings=None):  # noqa: ANN001
        return [_FakeTable((10.0, 20.0, 100.0, 150.0), self._rows)]


class _FakePageWithTables:
    width = 595.0
    height = 842.0

    def __init__(self, tables: list[_FakeTable]) -> None:
        self._tables = tables

    def find_tables(self, table_settings=None):  # noqa: ANN001
        return self._tables


class _FakePdf:
    def __init__(self, rows: list[list[str]]) -> None:
        self.pages = [_FakePage(rows)]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return None


class _FakePdfWithPage:
    def __init__(self, page) -> None:  # noqa: ANN001
        self.pages = [page]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return None


class _FakePdfWithPages:
    def __init__(self, pages) -> None:  # noqa: ANN001
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return None


class _CountingPage(_FakePage):
    def __init__(self, rows: list[list[str]]) -> None:
        super().__init__(rows)
        self.find_table_settings: list[object] = []

    def find_tables(self, table_settings=None):  # noqa: ANN001
        self.find_table_settings.append(table_settings)
        return super().find_tables(table_settings=table_settings)


def test_collect_table_candidates_skips_fallback_strategies_for_safe_default() -> None:
    page = _CountingPage([["Field", "Value"], ["alpha", "beta"]])

    result = collect_table_candidates_for_page(page, page_number=1)

    assert len(page.find_table_settings) == 1
    assert page.find_table_settings == [None]
    assert result.strategy_runs == ["default"]
    assert result.adaptive_skipped_strategies == ["lines_strict", "mixed_lines_text"]
    assert result.adaptive_skip_reason == "default_candidate_quality_sufficient"
    assert result.candidates[0].metrics.selected_strategy == "default"


def test_collect_table_candidates_runs_fallback_strategies_for_complex_default() -> None:
    page = _CountingPage([["Bits", "Description"], ["63:0", "A" * 130]])

    result = collect_table_candidates_for_page(page, page_number=1)

    assert len(page.find_table_settings) == 3
    assert result.strategy_runs == ["default", "lines_strict", "mixed_lines_text"]
    assert result.adaptive_skipped_strategies == []
    assert result.adaptive_skip_reason is None


def test_extract_tables_markdown_mode_never_uses_html(monkeypatch) -> None:
    rows = [["Bits", "Description"], ["63:0", "A" * 130]]
    monkeypatch.setattr("pdf2md.extractors.tables.pdfplumber.open", lambda *args, **kwargs: _FakePdf(rows))

    result = extract_tables(
        pdf_path=SimpleNamespace(),
        selected_pages=[1],
        password=None,
        table_mode=TableMode.MARKDOWN,
    )

    block = result.blocks_by_page[1][0].markdown
    assert "<table>" not in block
    assert "| Bits | Description |" in block
    assert result.assets[0].mode == "gfm"
    assert result.warnings[0].code == "TABLE_COMPLEXITY_MARKDOWN_COERCED"


def test_extract_tables_html_alias_matches_html_only(monkeypatch) -> None:
    rows = [["Col1", "Col2"], ["A", "B"]]
    monkeypatch.setattr("pdf2md.extractors.tables.pdfplumber.open", lambda *args, **kwargs: _FakePdf(rows))

    html_result = extract_tables(
        pdf_path=SimpleNamespace(),
        selected_pages=[1],
        password=None,
        table_mode=TableMode.HTML,
    )
    legacy_result = extract_tables(
        pdf_path=SimpleNamespace(),
        selected_pages=[1],
        password=None,
        table_mode=TableMode.HTML_ONLY,
    )

    assert html_result.blocks_by_page[1][0].markdown == legacy_result.blocks_by_page[1][0].markdown
    assert html_result.assets[0].mode == "html"


def test_extract_tables_materializes_precomputed_page_candidates(monkeypatch) -> None:
    rows = [["Field", "Value"], ["alpha", "beta"]]
    page = _FakePage(rows)
    candidate_result = collect_table_candidates_for_page(page, page_number=1)
    monkeypatch.setattr(
        "pdf2md.extractors.tables.pdfplumber.open",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("parent PDF should not be reopened")),
    )

    result = extract_tables(
        pdf_path=SimpleNamespace(),
        selected_pages=[1],
        password=None,
        table_mode=TableMode.AUTO,
        precomputed_candidates_by_page={1: candidate_result},
    )

    assert result.assets[0].page == 1
    assert result.assets[0].index == 1
    assert result.assets[0].mode == "gfm"
    assert "| Field | Value |" in result.blocks_by_page[1][0].markdown


def test_extract_tables_records_adaptive_strategy_skip_diagnostics(monkeypatch) -> None:
    rows = [["Field", "Value"], ["alpha", "beta"]]
    monkeypatch.setattr("pdf2md.extractors.tables.pdfplumber.open", lambda *args, **kwargs: _FakePdf(rows))

    result = extract_tables(
        pdf_path=SimpleNamespace(),
        selected_pages=[1],
        password=None,
        table_mode=TableMode.AUTO,
    )

    quality = result.table_quality[0]
    debug = result.debug_candidates_by_page[1][0]
    assert quality["strategy_runs"] == ["default"]
    assert quality["adaptive_skipped_strategies"] == ["lines_strict", "mixed_lines_text"]
    assert quality["adaptive_skip_reason"] == "default_candidate_quality_sufficient"
    assert debug["strategy_runs"] == ["default"]
    assert debug["adaptive_skipped_strategies"] == ["lines_strict", "mixed_lines_text"]
    assert debug["adaptive_skip_reason"] == "default_candidate_quality_sufficient"


def test_extract_tables_legacy_gfm_only_still_falls_back_to_html(monkeypatch) -> None:
    rows = [["Bits", "Description"], ["63:0", "A" * 130]]
    monkeypatch.setattr("pdf2md.extractors.tables.pdfplumber.open", lambda *args, **kwargs: _FakePdf(rows))

    result = extract_tables(
        pdf_path=SimpleNamespace(),
        selected_pages=[1],
        password=None,
        table_mode=TableMode.GFM_ONLY,
    )

    block = result.blocks_by_page[1][0].markdown
    assert "<table>" in block
    assert result.assets[0].mode == "html"
    assert result.warnings[0].code == "TABLE_GFM_UNSAFE_FALLBACK_HTML"


def test_extract_tables_suppresses_redundant_text_fragment(monkeypatch) -> None:
    full = _FakeTable((10.0, 20.0, 230.0, 130.0), [["Field", "Value"], ["alpha", "beta"]])
    fragment = _FakeTable((238.0, 42.0, 270.0, 60.0), [["alpha"]])
    page = _FakePageWithTables([full, fragment])
    monkeypatch.setattr("pdf2md.extractors.tables.pdfplumber.open", lambda *args, **kwargs: _FakePdfWithPage(page))

    result = extract_tables(
        pdf_path=SimpleNamespace(),
        selected_pages=[1],
        password=None,
        table_mode=TableMode.AUTO,
    )

    assert len(result.assets) == 1
    assert len(result.debug_candidates_by_page[1]) == 2
    suppressed = [item for item in result.debug_candidates_by_page[1] if not item["accepted"]]
    assert suppressed[0]["suppression_reason"] == "TEXT_FRAGMENT_SUPPRESSION"


def test_extract_tables_keeps_html_fallback_and_builds_rag_payload(monkeypatch) -> None:
    table = _FakeTable((10.0, 100.0, 230.0, 180.0), [["Bits", "Description"], ["63:0", "A" * 130]])

    class _FakeCaptionPage(_FakePageWithTables):
        def extract_text_lines(self):  # noqa: ANN201
            return [
                {
                    "text": "Table 1: Register fields",
                    "top": 70.0,
                    "bottom": 84.0,
                    "x0": 10.0,
                    "x1": 180.0,
                }
            ]

    page = _FakeCaptionPage([table])
    monkeypatch.setattr("pdf2md.extractors.tables.pdfplumber.open", lambda *args, **kwargs: _FakePdfWithPage(page))

    result = extract_tables(
        pdf_path=SimpleNamespace(),
        selected_pages=[1],
        password=None,
        table_mode=TableMode.AUTO,
    )

    assert "<table>" in result.blocks_by_page[1][0].markdown
    assert result.assets[0].mode == "html"
    assert result.assets[0].caption_text == "Table 1: Register fields"
    assert result.rag_tables[0]["source_mode"] == "html"
    assert result.rag_tables[0]["caption_text"] == "Table 1: Register fields"
    assert result.assets[0].table_confidence_v2_bucket in {"low", "medium"}
    assert "caption_linked" in result.assets[0].table_confidence_v2_reasons
    assert result.rag_tables[0]["table_confidence_v2"] == result.assets[0].table_confidence_v2
    assert result.rag_tables[0]["table_confidence_v2_bucket"] == result.assets[0].table_confidence_v2_bucket
    assert result.rag_tables[0]["records"][0]["row_text"] == f"Bits = 63:0 | Description = {'A' * 130}"
    assert result.rag_tables[0]["records"][0]["fallback_reasons"] == ["AMBIGUOUS_GRID", "LONG_CELL"]
    assert result.rag_tables[0]["records"][0]["table_confidence_v2"] == result.assets[0].table_confidence_v2


def test_extract_tables_flattens_multi_row_headers_for_rag(monkeypatch) -> None:
    rows = [
        ["", "Latency", "Latency"],
        ["Command", "Min", "Max"],
        ["Read", "1", "3"],
    ]
    monkeypatch.setattr("pdf2md.extractors.tables.pdfplumber.open", lambda *args, **kwargs: _FakePdf(rows))

    result = extract_tables(
        pdf_path=SimpleNamespace(),
        selected_pages=[1],
        password=None,
        table_mode=TableMode.AUTO,
    )

    quality = result.table_quality[0]
    assert result.assets[0].mode == "html"
    assert "MULTI_ROW_HEADER" in quality["reasons"]
    assert quality["header_depth"] == 2
    assert quality["rag_header_strategy"] == "multi_row_flattened"
    assert result.rag_tables[0]["headers"] == ["Command", "Latency / Min", "Latency / Max"]
    assert result.rag_tables[0]["records"][0]["cells"]["Latency / Max"] == "3"


def test_extract_tables_promotes_blank_descriptor_header_row_for_rag(monkeypatch) -> None:
    rows = [
        ["", "", ""],
        ["Bytes", "Field", "Description"],
        ["0", "CAP", "Controller capabilities"],
        ["1", "VS", "Version"],
    ]
    monkeypatch.setattr("pdf2md.extractors.tables.pdfplumber.open", lambda *args, **kwargs: _FakePdf(rows))

    result = extract_tables(
        pdf_path=SimpleNamespace(),
        selected_pages=[1],
        password=None,
        table_mode=TableMode.AUTO,
    )

    quality = result.table_quality[0]
    assert quality["header_rows_promoted"] == 1
    assert quality["rag_header_strategy"] == "promoted_header_row"
    assert result.rag_tables[0]["headers"] == ["Bytes", "Field", "Description"]
    assert result.rag_tables[0]["records"][0]["cells"] == {
        "Bytes": "0",
        "Field": "CAP",
        "Description": "Controller capabilities",
    }


def test_extract_tables_auto_falls_back_for_complex_accuracy_pack(monkeypatch) -> None:
    rows = [
        ["", "Latency", "Latency", "Latency"],
        ["Command", "Min", "Max", "Typical"],
        ["Read", "1", "3", "2"],
        ["Write", "2", "4", "3"],
        ["Notes: values are cycles", "", "", ""],
    ]
    monkeypatch.setattr("pdf2md.extractors.tables.pdfplumber.open", lambda *args, **kwargs: _FakePdf(rows))

    result = extract_tables(
        pdf_path=SimpleNamespace(),
        selected_pages=[1],
        password=None,
        table_mode=TableMode.AUTO,
    )

    markdown = result.blocks_by_page[1][0].markdown
    fallback_reasons = result.rag_tables[0]["fallback_reasons"]
    assert result.assets[0].mode == "html"
    assert "<table>" in markdown
    assert "| Command |" not in markdown
    assert "MULTI_ROW_HEADER" in fallback_reasons
    assert "MERGED_CELL_SUSPECTED" in fallback_reasons
    assert "STUB_COLUMN" in fallback_reasons
    assert "FOOTNOTE_ROW" in fallback_reasons
    assert result.rag_tables[0]["headers"] == [
        "Command",
        "Latency / Min",
        "Latency / Max",
        "Latency / Typical",
    ]
    assert result.rag_tables[0]["records"][0]["stub_cells"] == ["Read"]


def test_extract_tables_records_stub_and_footnote_diagnostics(monkeypatch) -> None:
    rows = [
        ["", "Min", "Max"],
        ["Read", "1", "3"],
        ["Write", "2", "4"],
        ["Notes: values are cycles", "", ""],
    ]
    monkeypatch.setattr("pdf2md.extractors.tables.pdfplumber.open", lambda *args, **kwargs: _FakePdf(rows))

    result = extract_tables(
        pdf_path=SimpleNamespace(),
        selected_pages=[1],
        password=None,
        table_mode=TableMode.AUTO,
    )

    quality = result.table_quality[0]
    assert result.assets[0].mode == "html"
    assert "FOOTNOTE_ROW" in quality["reasons"]
    assert "STUB_COLUMN" in quality["reasons"]
    assert quality["stub_column_count"] == 1
    assert quality["footnote_row_count"] == 1
    assert result.rag_tables[0]["records"][0]["stub_cells"] == ["Read"]


def test_extract_tables_marks_adjacent_same_header_tables_as_continuation(monkeypatch) -> None:
    pages = [
        _FakePage([["Field", "Value"], ["alpha", "1"]]),
        _FakePage([["Field", "Value"], ["beta", "2"]]),
    ]
    monkeypatch.setattr("pdf2md.extractors.tables.pdfplumber.open", lambda *args, **kwargs: _FakePdfWithPages(pages))

    result = extract_tables(
        pdf_path=SimpleNamespace(),
        selected_pages=[1, 2],
        password=None,
        table_mode=TableMode.AUTO,
    )

    assert result.assets[0].continuation_group == "table-continuation-001"
    assert result.assets[0].continued_to_page == 2
    assert result.assets[1].continued_from_page == 1
    assert result.assets[1].continuation_confidence == 1.0
    assert result.assets[1].continuation_reasons == [
        "adjacent_page",
        "header_similarity_high",
        "bbox_alignment_high",
        "no_current_caption",
        "repeated_template_penalty_clear",
    ]
    assert result.table_quality[1]["continuation_features"]["header_similarity"] == 1.0
    assert result.rag_tables[1]["continuation_group"] == "table-continuation-001"
    assert result.rag_tables[1]["continuation_confidence"] == 1.0
    assert result.rag_tables[1]["records"][0]["continuation_group"] == "table-continuation-001"
    assert result.rag_tables[1]["records"][0]["continuation_confidence"] == 1.0


def test_extract_tables_rejects_same_header_table_with_new_caption(monkeypatch) -> None:
    class _CaptionedPage(_FakePage):
        def extract_text_lines(self):  # noqa: ANN201
            return [
                {
                    "text": "Table 2: Independent fields",
                    "top": 0.0,
                    "bottom": 10.0,
                    "x0": 10.0,
                    "x1": 180.0,
                }
            ]

    pages = [
        _FakePage([["Field", "Value"], ["alpha", "1"]]),
        _CaptionedPage([["Field", "Value"], ["beta", "2"]]),
    ]
    monkeypatch.setattr("pdf2md.extractors.tables.pdfplumber.open", lambda *args, **kwargs: _FakePdfWithPages(pages))

    result = extract_tables(
        pdf_path=SimpleNamespace(),
        selected_pages=[1, 2],
        password=None,
        table_mode=TableMode.AUTO,
    )

    assert result.assets[1].continuation_group is None
    assert "current_caption_present" in result.assets[1].continuation_rejected_reasons
    assert result.table_quality[1]["caption_distance"] == 10.0
    assert result.rag_tables[1]["continuation_features"]["current_caption_distance"] == 10.0


def test_extract_tables_rejects_repeated_template_continuation(monkeypatch) -> None:
    pages = [
        _FakePage([["Field", "Value"], ["Total", "100"]]),
        _FakePage([["Field", "Value"], ["Total", "100"]]),
    ]
    monkeypatch.setattr("pdf2md.extractors.tables.pdfplumber.open", lambda *args, **kwargs: _FakePdfWithPages(pages))

    result = extract_tables(
        pdf_path=SimpleNamespace(),
        selected_pages=[1, 2],
        password=None,
        table_mode=TableMode.AUTO,
    )

    assert result.assets[1].continuation_group is None
    assert "repeated_template_penalty" in result.assets[1].continuation_rejected_reasons
    assert result.table_quality[1]["continuation_features"]["repeated_template_penalty"] == 0.45
    assert result.rag_tables[1]["continuation_rejected_reasons"] == [
        "repeated_template_penalty",
        "continuation_confidence_below_threshold",
    ]


def test_extract_tables_rejects_misaligned_same_header_table(monkeypatch) -> None:
    pages = [
        _FakePageWithTables([_FakeTable((10.0, 20.0, 100.0, 150.0), [["Field", "Value"], ["alpha", "1"]])]),
        _FakePageWithTables([_FakeTable((220.0, 20.0, 310.0, 150.0), [["Field", "Value"], ["beta", "2"]])]),
    ]
    monkeypatch.setattr("pdf2md.extractors.tables.pdfplumber.open", lambda *args, **kwargs: _FakePdfWithPages(pages))

    result = extract_tables(
        pdf_path=SimpleNamespace(),
        selected_pages=[1, 2],
        password=None,
        table_mode=TableMode.AUTO,
    )

    assert result.assets[1].continuation_group is None
    assert "bbox_alignment_below_threshold" in result.assets[1].continuation_rejected_reasons
    assert result.table_quality[1]["continuation_features"]["bbox_alignment_similarity"] < 0.8
