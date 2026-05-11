from __future__ import annotations

from types import SimpleNamespace

import pdf2md.extractors.ocr as ocr_module
from pdf2md.extractors.ocr import run_ocr


class _FakePage:
    def render(self, scale: float):  # noqa: ANN201, ARG002
        return SimpleNamespace(to_pil=lambda: object())

    def close(self) -> None:
        return None


class _FakeDocument:
    def __init__(self, path: str) -> None:  # noqa: ARG002
        self.path = path

    def get_page(self, index: int) -> _FakePage:  # noqa: ARG002
        return _FakePage()


def test_run_ocr_passes_language_to_tesseract(sample_pdf, monkeypatch) -> None:  # noqa: ANN001
    calls: list[tuple[str, str]] = []

    def image_to_string(image, lang: str):  # noqa: ANN001
        calls.append(("string", lang))
        return "ocr text"

    def image_to_data(image, lang: str, output_type):  # noqa: ANN001, ARG001
        calls.append(("data", lang))
        return {"text": ["ocr", "text"], "conf": ["95", "92"]}

    fake_tesseract = SimpleNamespace(
        Output=SimpleNamespace(DICT="dict"),
        image_to_string=image_to_string,
        image_to_data=image_to_data,
    )
    monkeypatch.setattr(ocr_module, "pytesseract", fake_tesseract)
    monkeypatch.setattr(ocr_module, "pdfium", SimpleNamespace(PdfDocument=_FakeDocument))
    monkeypatch.setattr(ocr_module.shutil, "which", lambda name: "/usr/bin/tesseract")

    result = run_ocr(sample_pdf, [1], {1: ""}, force_ocr=False, ocr_lang="kor+eng")

    assert result.used_ocr is True
    assert result.runtime_available is True
    assert result.attempted_pages == [1]
    assert result.reasons_by_page == {1: "empty_text_layer"}
    assert calls == [("string", "kor+eng"), ("data", "kor+eng")]


def test_run_ocr_runtime_unavailable_records_attempt_without_text(sample_pdf, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(ocr_module, "pytesseract", None)
    monkeypatch.setattr(ocr_module, "pdfium", None)

    result = run_ocr(sample_pdf, [1], {1: ""}, force_ocr=False, ocr_lang="eng")

    assert result.used_ocr is False
    assert result.runtime_available is False
    assert result.attempted_pages == [1]
    assert result.warnings[0].code == "OCR_RUNTIME_UNAVAILABLE"
