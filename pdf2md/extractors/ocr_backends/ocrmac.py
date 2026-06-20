from __future__ import annotations

import importlib
import platform
from typing import Any

from pdf2md.extractors.ocr_backends.base import OCRBackendMetadata, OCRBackendResult


class OcrMacOCRBackend:
    """Optional macOS Vision OCR adapter via the ocrmac package."""

    metadata = OCRBackendMetadata(
        name="ocrmac",
        raw_confidence_unit="backend_specific",
        normalized_confidence_unit="0_to_1",
        higher_is_better=True,
        supports_languages=False,
    )

    def __init__(self) -> None:
        self._module: Any | None = None

    def is_available(self) -> bool:
        return platform.system() == "Darwin" and _load_ocrmac_module() is not None

    def configure_runtime(self) -> str | None:
        if platform.system() != "Darwin":
            return "platform_unsupported"
        module = _load_ocrmac_module()
        if module is None:
            return "dependency_unavailable"
        self._module = module
        return None

    def recognize(self, image: object, *, lang: str) -> OCRBackendResult:  # noqa: ARG002
        if self._module is None:
            runtime_error = self.configure_runtime()
            if runtime_error is not None:
                raise RuntimeError(runtime_error)
        ocr_cls = getattr(self._module, "OCR", None)
        if ocr_cls is None:
            raise RuntimeError("ocrmac OCR class is unavailable")
        result = ocr_cls(image).recognize()
        return OCRBackendResult(text=_ocrmac_text(result), confidence_data=_ocrmac_confidence_data(result))


def _load_ocrmac_module() -> Any | None:
    try:
        return importlib.import_module("ocrmac")
    except Exception:  # noqa: BLE001
        return None


def _ocrmac_text(result: Any) -> str:
    texts = [text for text, _confidence in _ocrmac_items(result) if text]
    return "\n".join(texts).strip()


def _ocrmac_confidence_data(result: Any) -> dict[str, list[str]]:
    texts: list[str] = []
    confidences: list[str] = []
    for text, confidence in _ocrmac_items(result):
        if not text:
            continue
        texts.append(text)
        confidences.append(str(round((confidence or 0.0) * 100.0, 2)))
    return {"text": texts, "conf": confidences}


def _ocrmac_items(result: Any) -> list[tuple[str, float | None]]:
    items: list[tuple[str, float | None]] = []
    if not isinstance(result, list):
        return items
    for item in result:
        if isinstance(item, dict):
            text = str(item.get("text") or item.get("recognized_text") or "").strip()
            confidence = _float_or_none(item.get("confidence"))
            items.append((text, confidence))
        elif isinstance(item, (list, tuple)) and item:
            text = str(item[0] or "").strip()
            confidence = _float_or_none(item[1] if len(item) > 1 else None)
            items.append((text, confidence))
    return items


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
