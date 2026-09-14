"""Q155 boundary ownership, source retention and nested indexing regressions."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fixtures.pdf_builder import PageSpec, PositionedText, build_nested_cell_table_pdf, write_pdf
from pdf2md.config import Config
from pdf2md.extractors.nested_tables import recover_cell_structure
from pdf2md.pipeline import run_conversion
from scripts.validate_artifact_integrity import validate_artifact_integrity


@pytest.mark.parametrize("mode", ["auto", "gfm-only", "markdown"])
def test_nested_html_keeps_flat_rag_rows_and_resolvable_cell_refs(tmp_path: Path, mode: str) -> None:
    source = tmp_path / "nested.pdf"
    build_nested_cell_table_pdf(source)
    output = tmp_path / "output"
    run_conversion(Config(input_pdf=source, output_dir=output, table_mode=mode, rag_table_output="both"))
    manifest = json.loads((output / "manifest.json").read_text())
    assert len(manifest["tables"]) == 1
    asset = manifest["tables"][0]
    assert asset["mode"] == "html"
    cells = asset["cell_structure"]
    parent = next(cell for cell in cells if cell["children"])
    child = parent["children"][0]
    assert parent["row"] == 1 and parent["column"] == 1
    assert parent["text"] == "Identifier"
    assert "07:04" in parent["raw_text"] and "03:00" in parent["raw_text"]
    assert child["id"] == parent["id"] + "-table-0001"
    ids = [cell["id"] for cell in cells + child["cells"]]
    assert len(ids) == len(set(ids))
    records = [json.loads(line) for line in (output / "tables_rag.jsonl").read_text().splitlines()]
    assert len(records) == 1
    assert set(records[0]["cell_refs"]) <= set(ids)
    assert records[0]["row_text"].count("07:04") == 1
    markdown = (output / "document.md").read_text()
    assert markdown.count("<table>") == 2
    assert markdown.count("07:04") == 1
    assert validate_artifact_integrity(output_dir=output)["passed"]
    records[0]["cell_refs"] = ["missing-cell"]
    (output / "tables_rag.jsonl").write_text(json.dumps(records[0]) + "\n")
    assert any(item['code'] == 'invalid_table_cell_ref'
               for item in validate_artifact_integrity(output_dir=output)['findings'])


@pytest.mark.parametrize("span", ["column", "row"])
def test_child_merged_header_preserves_colspan(tmp_path: Path, span: str) -> None:
    source = tmp_path / "merged.pdf"
    write_pdf(
        source,
        [
            PageSpec(
                texts=[
                    PositionedText(text, x, y, 10)
                    for text, x, y in [
                        ("Bytes", 55, 684),
                        ("Description", 145, 684),
                        ("15", 55, 620),
                        ("Identifier", 145, 655),
                        ("Bits Meaning", 155, 626),
                        ("07:04", 155, 606),
                        ("Type 0h", 220, 606),
                        ("03:00", 155, 586),
                        ("Subtype 1h", 220, 586),
                    ]
                    if span != "row" or text != "03:00"
                ],
                graphics=[
                    "1 w 50 570 420 130 re S",
                    "140 570 m 140 700 l S",
                    "50 675 m 470 675 l S",
                    "150 580 300 60 re S",
                    "215 600 m 450 600 l S" if span == "row" else "150 600 m 450 600 l S",
                    "150 620 m 450 620 l S",
                    "215 580 m 215 620 l S",
                ],
            )
        ],
    )
    output = tmp_path / "output"
    run_conversion(Config(input_pdf=source, output_dir=output))
    assert '<th colspan="2">Bits Meaning</th>' in (output / "document.md").read_text()
    cells = json.loads((output / "manifest.json").read_text())["tables"][0]["cell_structure"]
    assert cells[-1]["children"][0]["cells"][0]["col_span"] == 2
    if span == "row":
        assert '<td rowspan="2">07:04</td>' in (output / "document.md").read_text()


@pytest.mark.parametrize("failure", ["crosses_cells", "duplicate", "missing_boundary"])
def test_unverifiable_ownership_returns_structure_loss(failure: str) -> None:
    def table(box, cells, rows):
        return SimpleNamespace(
            bbox=box,
            rows=[SimpleNamespace(cells=cells, bbox=box)],
            extract=lambda: rows,
            page=SimpleNamespace(chars=[]),
        )

    parent = table([0, 0, 100, 100], [[0, 0, 50, 100], [50, 0, 100, 100]], [["left", "right"]])
    box = [25, 20, 75, 80] if failure == "crosses_cells" else [60, 20, 90, 80]
    child = table(box, [box], [["child"]])
    tables = [parent, child]
    if failure == "duplicate":
        tables.append(table(box, [box], [["child"]]))
    rows = [["left", "right", ""]] if failure == "missing_boundary" else [["left", "right"]]
    structure, loss = recover_cell_structure(
        parent, tables, rows, process=lambda rows: rows, sanitize=lambda value: value or ""
    )
    assert structure is None
    assert loss in {"child_crosses_parent_cells", "duplicate_child_boundary", "missing_cell_boundary"}


def test_parallel_and_repeated_conversion_preserve_nested_ids(tmp_path: Path) -> None:
    from pypdf import PdfReader, PdfWriter

    single = tmp_path / "single.pdf"
    build_nested_cell_table_pdf(single)
    writer = PdfWriter()
    page = PdfReader(single).pages[0]
    writer.add_page(page)
    writer.add_page(page)
    source = tmp_path / "two.pdf"
    writer.write(source)
    structures = []
    for workers in (1, 2, 1):
        output = tmp_path / str(len(structures))
        run_conversion(Config(input_pdf=source, output_dir=output, page_workers=workers))
        manifest = json.loads((output / "manifest.json").read_text())
        assert len(manifest["tables"]) == 2
        structures.append(manifest["tables"])
    assert structures[0] == structures[1] == structures[2]


def test_verified_parent_wins_over_high_scoring_child(tmp_path: Path) -> None:
    import pdfplumber
    from pdf2md.extractors.tables import _extract_strategy_candidates, _prune_candidates
    source = tmp_path / "nested.pdf"
    build_nested_cell_table_pdf(source)
    with pdfplumber.open(source) as pdf:
        page = pdf.pages[0]
        candidates = _extract_strategy_candidates(page, strategy="default", table_settings=None)
        for candidate in candidates:
            candidate.quality_score = 0 if candidate.cell_structure else 1
        selected = _prune_candidates(page, candidates)
    assert len(selected) == 1 and selected[0].cell_structure


def test_structure_loss_keeps_source_and_emits_actionable_warning(tmp_path: Path, monkeypatch) -> None:
    import pdf2md.extractors.tables as tables
    source = tmp_path / "nested.pdf"
    build_nested_cell_table_pdf(source)
    monkeypatch.setattr(tables, "recover_cell_structure", lambda *args, **kwargs: (None, "child_crosses_parent_cells"))
    output = tmp_path / "output"
    result = run_conversion(Config(input_pdf=source, output_dir=output))
    assert result.exit_code == 2
    assert "07:04" in (output / "document.md").read_text()
    assert any(w.code == "TABLE_STRUCTURE_LOSS" and w.details['reason'] == 'structure_loss'
               for w in result.report.warnings)
