from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from pdf2md.extractors.ocr_backends.base import OCRBackendMetadata, OCRBackendResult


class TesseractOCRBackend:
    """pytesseract-backed OCR adapter preserving the existing 0-100 confidence contract."""

    metadata = OCRBackendMetadata(
        name="tesseract",
        raw_confidence_unit="0_to_100",
        normalized_confidence_unit="0_to_1",
        higher_is_better=True,
        supports_languages=True,
    )

    def __init__(self, pytesseract_module: object | None) -> None:
        self._pytesseract = pytesseract_module

    def is_available(self) -> bool:
        return self._pytesseract is not None

    def configure_runtime(self) -> str | None:
        if self._pytesseract is None:
            return "dependency_unavailable"
        tesseract_cmd = _resolve_tesseract_cmd()
        if tesseract_cmd is None:
            return "tesseract_unavailable"
        if shutil.which("tesseract") is None:
            pytesseract_runtime = getattr(self._pytesseract, "pytesseract", None)
            if pytesseract_runtime is not None:
                pytesseract_runtime.tesseract_cmd = tesseract_cmd
        return None

    def recognize(self, image: object, *, lang: str) -> OCRBackendResult:
        if self._pytesseract is None:
            raise RuntimeError("pytesseract is unavailable")
        output = getattr(self._pytesseract, "Output")
        text = (self._pytesseract.image_to_string(image, lang=lang) or "").strip()
        data: dict[str, Any] = self._pytesseract.image_to_data(image, lang=lang, output_type=output.DICT)
        return OCRBackendResult(text=text, confidence_data=data)


def _resolve_tesseract_cmd() -> str | None:
    executable = shutil.which("tesseract")
    if executable:
        return executable
    homebrew_tesseract = Path("/opt/homebrew/bin/tesseract")
    if homebrew_tesseract.exists():
        return str(homebrew_tesseract)
    return None
