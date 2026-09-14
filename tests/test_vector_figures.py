from pathlib import Path
import json

import pytest

from fixtures.pdf_builder import PageSpec, PositionedText, TableSpec, write_pdf
from pdf2md.config import Config
from pdf2md.pipeline import run_conversion
from scripts.validate_artifact_integrity import validate_artifact_integrity
from pdf2md.extractors.vector_figures import detect_framed_vector_figures


def vector_pdf(path: Path, page_count: int = 1) -> None:
    """Two captioned framed diagrams and a genuine Figure-captioned table."""
    graphics, texts = [], [PositionedText("Body before diagrams.", 50, 780)]
    def frame(x, y, width, height):
        # Diagram exporters use closed paths with sub-point transform drift,
        # unlike the exact ruled grid used by the actual table below.
        return f"{x} {y} m {x+width} {y+.001} l {x+width+.001} {y+height} l {x+.001} {y+height+.001} l h S"
    for number, y in [(1, 650), (2, 470)]:
        graphics.extend([frame(50, y, 400, 90), frame(70, y+25, 70, 40),
                         frame(340, y+25, 80, 40), f"140 {y+45} m 340 {y+45} l S"])
        texts.extend([PositionedText(f"Figure {number}: Network configuration", 90, y+105),
                      PositionedText(f"HOST{number}", 80, y+40), PositionedText(f"NODE{number}", 350, y+40)])
    texts.extend([PositionedText("Figure 3: Protocol values", 90, 390), PositionedText("Body after diagrams.", 50, 270)])
    write_pdf(path, [PageSpec(texts=texts, graphics=graphics,
        tables=[TableSpec([["Protocol", "Value"], ["TCP", "1h"]], 50, 370, [150, 250])])] * page_count)


def test_default_preserves_two_diagrams_without_cropping_real_table(tmp_path: Path) -> None:
    source, output = tmp_path / "source.pdf", tmp_path / "output"
    vector_pdf(source)
    run_conversion(Config(input_pdf=source, output_dir=output, rag_figure_text_chunks=True))
    manifest = json.loads((output / "manifest.json").read_text())
    figures = [row for row in manifest["images"] if row.get("crop_reason") == "captioned_vector_diagram"]
    assert len(figures) == 2
    assert len(manifest["tables"]) == 1
    markdown = (output / "document.md").read_text()
    assert "HOST1" not in markdown and "HOST2" not in markdown
    assert "Body before diagrams." in markdown and "Body after diagrams." in markdown
    assert markdown.index("Figure 1:") < markdown.index("![Image") < markdown.index("Figure 2:")
    second_image = markdown.index("![Image", markdown.index("![Image") + 1)
    assert markdown.index("Figure 2:") < second_image < markdown.index("Figure 3:")
    records = [json.loads(line) for line in (output / "figures_rag.jsonl").read_text().splitlines()]
    assert all(record.get("source_text_lines") for record in records if record.get("crop_reason") == "captioned_vector_diagram")
    assert validate_artifact_integrity(output_dir=output)["passed"]


def test_final_empty_html_table_is_integrity_error(tmp_path: Path) -> None:
    source, output = tmp_path / "source.pdf", tmp_path / "output"
    write_pdf(source, [PageSpec(texts=[PositionedText("Text", 50, 700)])])
    run_conversion(Config(input_pdf=source, output_dir=output))
    with (output / "document.md").open("a") as file:
        file.write('\n<!-- table: page=1 index=1 mode=html -->\n<table><tr><th></th></tr></table>')
    report = validate_artifact_integrity(output_dir=output)
    assert not report["passed"]
    assert any(row["code"] == "empty_html_table" for row in report["findings"])


def test_empty_grid_is_not_published_as_table(tmp_path: Path) -> None:
    source, output = tmp_path / "source.pdf", tmp_path / "output"
    write_pdf(source, [PageSpec(tables=[TableSpec([["", ""], ["", ""]], 50, 700, [150, 250])])])
    run_conversion(Config(input_pdf=source, output_dir=output))
    assert json.loads((output / "manifest.json").read_text())["tables"] == []


def test_crop_failure_keeps_source_text(monkeypatch, tmp_path: Path) -> None:
    import pdf2md.extractors.images as images
    def fail(**kwargs):
        raise RuntimeError("render failure")
    monkeypatch.setattr(images, "_render_page_crop", fail)
    source, output = tmp_path / "source.pdf", tmp_path / "output"
    vector_pdf(source)
    result = run_conversion(Config(input_pdf=source, output_dir=output))
    text = (output / "document.md").read_text()
    assert "HOST1" in text and "HOST2" in text
    assert any(w.code == "IMAGE_EXTRACTION_FAILED" for w in result.report.warnings)


@pytest.mark.parametrize("missing", ["caption", "connector", "nodes", "table_overlap"])
def test_detector_requires_independent_geometry_evidence(tmp_path: Path, missing: str) -> None:
    import pdfplumber
    from types import SimpleNamespace
    source = tmp_path / "source.pdf"
    vector_pdf(source)
    with pdfplumber.open(source) as pdf:
        original = pdf.pages[0]
        page = SimpleNamespace(rects=original.rects, curves=original.curves, lines=original.lines,
                               width=original.width, height=original.height)
        lines = original.extract_text_lines()
        tables = []
        if missing == "caption":
            lines = [line for line in lines if not line["text"].startswith("Figure")]
        elif missing == "connector":
            page.lines = []
        elif missing == "nodes":
            page.curves = [curve for curve in page.curves if curve["width"] > 300]
        else:
            tables = [[0, 0, page.width, page.height]]
        assert detect_framed_vector_figures(page, text_lines=lines, confirmed_table_bboxes=tables) == []


@pytest.mark.parametrize("options", [{"image_mode": "placeholder"}, {"rag_sidecar_scope": "none"}])
def test_text_is_preserved_when_assets_or_sidecars_are_omitted(tmp_path: Path, options: dict) -> None:
    source, output = tmp_path / "source.pdf", tmp_path / "output"
    vector_pdf(source)
    run_conversion(Config(input_pdf=source, output_dir=output, **options))
    manifest = json.loads((output / "manifest.json").read_text())
    vectors = [asset for asset in manifest["images"] if asset.get("crop_reason") == "captioned_vector_diagram"]
    assert len(vectors) == 2
    assert "HOST1" in " ".join(line["text"] for asset in vectors for line in asset["source_text_lines"])
    if options.get("image_mode") == "placeholder":
        assert "HOST1" in (output / "document.md").read_text()


def test_vector_page_timeout_keeps_unrendered_source(monkeypatch, tmp_path: Path) -> None:
    import pdf2md.extractors.images as images
    from functools import partial
    from itertools import count
    # A microsecond real-time limit depends on the platform's clock resolution.
    # Advance a deterministic clock beyond the limit before the crop is started.
    ticks = count(step=0.01)
    monkeypatch.setattr("pdf2md.pipeline.extract_images", partial(images.extract_images, time_provider=lambda: next(ticks)))
    source, output = tmp_path / "source.pdf", tmp_path / "output"
    vector_pdf(source)
    render = images._render_page_crop
    calls = 0
    def slow_render(**kwargs):
        nonlocal calls
        calls += 1
        return render(**kwargs)
    monkeypatch.setattr(images, "_render_page_crop", slow_render)
    run_conversion(Config(input_pdf=source, output_dir=output, image_extraction_page_timeout_seconds=0.000001))
    text = (output / "document.md").read_text()
    assert calls == 0 and "HOST1" in text and "HOST2" in text


def test_empty_html_detection_handles_nested_tables_and_images(tmp_path: Path) -> None:
    from scripts.validate_artifact_integrity import _HtmlTableContentParser
    parser = _HtmlTableContentParser()
    parser.feed('<table><tr><td>Outer<table><tr><td> </td></tr></table></td></tr></table>'
                '<table><tr><td><img src="cell.png"></td></tr></table>')
    parser.close()
    assert len(parser.empty_tables) == 1


def test_parallel_page_worker_preserves_vector_result(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    vector_pdf(source, page_count=2)
    for workers in (1, 2):
        run_conversion(Config(input_pdf=source, output_dir=tmp_path / str(workers), page_workers=workers))
    assert (tmp_path / '1/document.md').read_bytes() == (tmp_path / '2/document.md').read_bytes()
    before, after = [json.loads((tmp_path / str(workers) / 'manifest.json').read_text()) for workers in (1, 2)]
    assert after['options']['page_parallel_enabled'] is True
    assert before['images'] == after['images'] and before['tables'] == after['tables']


def test_empty_html_detection_ignores_fenced_examples() -> None:
    from scripts.validate_artifact_integrity import _HtmlTableContentParser, _without_fenced_code
    parser = _HtmlTableContentParser()
    parser.feed(_without_fenced_code("````html\n<table></table>\n```\n````\n"
                                    "~~~html\n<table></table>\n~~~\n<table></table>\n"))
    parser.close()
    assert len(parser.empty_tables) == 1
    assert parser.empty_tables[0]["line"] == 8


def test_ambiguous_caption_frames_are_reported_without_guessing() -> None:
    from types import SimpleNamespace
    def rect(x, y, width, height):
        return dict(x0=x, top=y, x1=x+width, bottom=y+height, width=width, height=height)
    rectangles, lines = [], []
    for x in (50, 500):
        rectangles.extend([rect(x, 100, 400, 90), rect(x+20, 125, 70, 40), rect(x+290, 125, 80, 40)])
        lines.append(dict(x0=x+90, top=145, x1=x+290, bottom=145, pts=[(x+90, 145), (x+290, 145)]))
    page = SimpleNamespace(rects=rectangles, curves=[], lines=lines, width=1000, height=800)
    diagnostics = []
    found = detect_framed_vector_figures(page,
        text_lines=[dict(text="Figure 1: Network", x0=50, x1=900, top=75, bottom=90)],
        confirmed_table_bboxes=[], diagnostics=diagnostics)
    assert found == []
    assert len(diagnostics) == 2 and all(row['reason'] == 'ambiguous_caption_frames' for row in diagnostics)
