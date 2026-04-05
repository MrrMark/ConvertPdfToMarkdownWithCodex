from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pdf2md.extractors.images import extract_images
from pdf2md.models import ImageMode


class _FakePdfPlumberPage:
    def __init__(self, *, images: list[dict], text_lines: list[dict]) -> None:
        self.images = images
        self._text_lines = text_lines

    def extract_text_lines(self) -> list[dict]:
        return self._text_lines


class _FakePdfPlumberDocument:
    def __init__(self, pages: list[_FakePdfPlumberPage]) -> None:
        self.pages = pages

    def __enter__(self) -> _FakePdfPlumberDocument:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeImage:
    def __init__(self, data: bytes, name: str = "figure.png") -> None:
        self.data = data
        self.name = name
        self.indirect_reference = {"/Width": 120, "/Height": 80}


def _fake_reader(image: _FakeImage) -> SimpleNamespace:
    return SimpleNamespace(pages=[SimpleNamespace(images=[image])])


def test_extract_images_does_not_write_files_for_embedded_or_placeholder(
    monkeypatch,
    sample_pdf: Path,
    tmp_path: Path,
) -> None:
    fake_page = _FakePdfPlumberPage(
        images=[{"top": 100.0, "bottom": 180.0, "x0": 50.0, "x1": 170.0, "width": 120, "height": 80}],
        text_lines=[{"top": 182.0, "text": "Figure 1: Sample image"}],
    )
    monkeypatch.setattr(
        "pdf2md.extractors.images.pdfplumber.open",
        lambda *args, **kwargs: _FakePdfPlumberDocument([fake_page]),
    )

    for mode in (ImageMode.EMBEDDED, ImageMode.PLACEHOLDER):
        output_dir = tmp_path / mode.value
        result = extract_images(
            reader=_fake_reader(_FakeImage(b"image-bytes")),
            pdf_path=sample_pdf,
            selected_pages=[1],
            password=None,
            output_dir=output_dir,
            image_mode=mode,
        )
        files = list((output_dir / "assets" / "images").glob("*"))
        assert files == []
        assert result.assets[0].caption_text == "Figure 1: Sample image"
        assert result.assets[0].caption_source == "nearby_caption"


def test_extract_images_writes_referenced_file(monkeypatch, sample_pdf: Path, tmp_path: Path) -> None:
    fake_page = _FakePdfPlumberPage(
        images=[{"top": 100.0, "bottom": 180.0, "x0": 50.0, "x1": 170.0, "width": 120, "height": 80}],
        text_lines=[],
    )
    monkeypatch.setattr(
        "pdf2md.extractors.images.pdfplumber.open",
        lambda *args, **kwargs: _FakePdfPlumberDocument([fake_page]),
    )

    output_dir = tmp_path / "referenced"
    result = extract_images(
        reader=_fake_reader(_FakeImage(b"image-bytes")),
        pdf_path=sample_pdf,
        selected_pages=[1],
        password=None,
        output_dir=output_dir,
        image_mode=ImageMode.REFERENCED,
    )

    files = list((output_dir / "assets" / "images").glob("*"))
    assert len(files) == 1
    assert result.assets[0].alt_text == "Image page-0001-figure-001"
