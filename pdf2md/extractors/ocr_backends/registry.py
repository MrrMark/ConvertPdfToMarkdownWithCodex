from __future__ import annotations

from pdf2md.extractors.ocr_backends.base import OCRBackend
from pdf2md.extractors.ocr_backends.ocrmac import OcrMacOCRBackend
from pdf2md.extractors.ocr_backends.rapidocr import RapidOCROCRBackend
from pdf2md.extractors.ocr_backends.tesseract import TesseractOCRBackend
from pdf2md.extractors.ocr_backends.tesseract_cli import TesseractCliOCRBackend

SUPPORTED_OCR_BACKENDS = ("tesseract", "tesseract-cli", "rapidocr", "ocrmac")


def supported_ocr_backends() -> tuple[str, ...]:
    """Return OCR backends that are implemented for the conversion path."""
    return SUPPORTED_OCR_BACKENDS


def get_ocr_backend(name: str, *, pytesseract_module: object | None) -> OCRBackend:
    """Return an implemented OCR backend adapter by name."""
    if name == "tesseract":
        return TesseractOCRBackend(pytesseract_module)
    if name == "tesseract-cli":
        return TesseractCliOCRBackend()
    if name == "rapidocr":
        return RapidOCROCRBackend()
    if name == "ocrmac":
        return OcrMacOCRBackend()
    raise ValueError(f"Unsupported OCR backend: {name}")
