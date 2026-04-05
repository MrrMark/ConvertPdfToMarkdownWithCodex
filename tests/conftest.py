from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject


def _build_text_page(writer: PdfWriter, text: str) -> None:
    page = writer.add_blank_page(width=595, height=842)

    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)  # noqa: SLF001

    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref}),
        }
    )

    safe_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = StreamObject()
    content._data = f"BT /F1 12 Tf 72 770 Td ({safe_text}) Tj ET".encode("utf-8")  # noqa: SLF001
    page[NameObject("/Contents")] = writer._add_object(content)  # noqa: SLF001


def create_text_pdf(path: Path, page_texts: list[str]) -> None:
    writer = PdfWriter()
    for text in page_texts:
        _build_text_page(writer, text)
    with path.open("wb") as fp:
        writer.write(fp)


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "sample.pdf"
    create_text_pdf(pdf_path, ["Hello PDF Page 1", "Second page text"])
    return pdf_path
