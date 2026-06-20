from __future__ import annotations

import importlib
from typing import Any

from pdf2md.extractors.ocr_backends.base import OCRBackendMetadata, OCRBackendResult


class RapidOCROCRBackend:
    """Optional RapidOCR adapter loaded only when the dependency is installed."""

    metadata = OCRBackendMetadata(
        name="rapidocr",
        raw_confidence_unit="0_to_1",
        normalized_confidence_unit="0_to_1",
        higher_is_better=True,
        supports_languages=False,
    )

    def __init__(self) -> None:
        self._module: Any | None = None
        self._engine: Any | None = None

    def is_available(self) -> bool:
        return _load_rapidocr_module() is not None

    def configure_runtime(self) -> str | None:
        module = _load_rapidocr_module()
        if module is None:
            return "dependency_unavailable"
        engine_cls = getattr(module, "RapidOCR", None)
        if engine_cls is None:
            return "rapidocr_engine_unavailable"
        try:
            self._engine = engine_cls()
        except Exception:  # noqa: BLE001
            return "rapidocr_runtime_unavailable"
        self._module = module
        return None

    def recognize(self, image: object, *, lang: str) -> OCRBackendResult:  # noqa: ARG002
        if self._engine is None:
            runtime_error = self.configure_runtime()
            if runtime_error is not None:
                raise RuntimeError(runtime_error)
        result = self._engine(image)
        return OCRBackendResult(text=_rapidocr_text(result), confidence_data=_rapidocr_confidence_data(result))


def _load_rapidocr_module() -> Any | None:
    for module_name in ("rapidocr_onnxruntime", "rapidocr"):
        try:
            return importlib.import_module(module_name)
        except Exception:  # noqa: BLE001
            continue
    return None


def _rapidocr_items(result: Any) -> list[Any]:
    if isinstance(result, tuple) and result:
        first = result[0]
        return list(first or []) if isinstance(first, list) else []
    if isinstance(result, list):
        return result
    return []


def _rapidocr_item_text_confidence(item: Any) -> tuple[str, float | None]:
    if isinstance(item, dict):
        text = str(item.get("text") or "").strip()
        confidence = item.get("confidence") or item.get("score")
        return text, _float_or_none(confidence)
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        payload = item[1]
        if isinstance(payload, (list, tuple)) and payload:
            text = str(payload[0] or "").strip()
            confidence = _float_or_none(payload[1] if len(payload) > 1 else None)
            return text, confidence
    return "", None


def _rapidocr_text(result: Any) -> str:
    texts = [text for item in _rapidocr_items(result) if (text := _rapidocr_item_text_confidence(item)[0])]
    return "\n".join(texts).strip()


def _rapidocr_confidence_data(result: Any) -> dict[str, list[str]]:
    texts: list[str] = []
    confidences: list[str] = []
    for item in _rapidocr_items(result):
        text, confidence = _rapidocr_item_text_confidence(item)
        if not text:
            continue
        texts.append(text)
        confidences.append(str(round((confidence or 0.0) * 100.0, 2)))
    return {"text": texts, "conf": confidences}


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
