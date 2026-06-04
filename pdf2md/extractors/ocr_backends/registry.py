from __future__ import annotations

from pdf2md.extractors.ocr_backends.base import OCRBackend
from pdf2md.extractors.ocr_backends.tesseract import TesseractOCRBackend

SUPPORTED_OCR_BACKENDS = ("tesseract",)


def supported_ocr_backends() -> tuple[str, ...]:
    """Return OCR backends that are implemented for the conversion path."""
    return SUPPORTED_OCR_BACKENDS


def get_ocr_backend(name: str, *, pytesseract_module: object | None) -> OCRBackend:
    """Return an implemented OCR backend adapter by name."""
    if name == "tesseract":
        return TesseractOCRBackend(pytesseract_module)
    raise ValueError(f"Unsupported OCR backend: {name}")
