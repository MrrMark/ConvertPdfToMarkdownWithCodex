from __future__ import annotations

import re
import shutil
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from pdf2md.constants import WarningCode
from pdf2md.models import WarningEntry

try:
    import pypdfium2 as pdfium
except Exception:  # noqa: BLE001
    pdfium = None

try:
    import pytesseract
except Exception:  # noqa: BLE001
    pytesseract = None

ALNUM_PATTERN = re.compile(r"[A-Za-z0-9]")
LANGUAGE_DATA_MISSING_PATTERN = re.compile(
    r"(?:failed loading language|error opening data file|could not initialize tesseract|traineddata)",
    re.IGNORECASE,
)
OCR_LOW_CONFIDENCE_MEAN_THRESHOLD = 75.0
OCR_CRITICAL_CONFIDENCE_MEAN_THRESHOLD = 50.0
OCR_LOW_CONFIDENCE_TOKEN_RATIO_THRESHOLD = 0.25
OCR_CRITICAL_CONFIDENCE_TOKEN_RATIO_THRESHOLD = 0.5


@dataclass
class OcrMetrics:
    mean: float
    median: float
    low_conf_token_ratio: float


@dataclass
class OcrResult:
    warnings: list[WarningEntry] = field(default_factory=list)
    page_texts: dict[int, str] = field(default_factory=dict)
    ocr_pages: list[int] = field(default_factory=list)
    attempted_pages: list[int] = field(default_factory=list)
    reasons_by_page: dict[int, str] = field(default_factory=dict)
    used_ocr: bool = False
    runtime_available: bool = False
    pdf_open_count: int = 0
    metrics_by_page: dict[int, OcrMetrics] = field(default_factory=dict)


def _extract_confidence_metrics(data: dict) -> OcrMetrics:
    confidences: list[float] = []
    low_count = 0
    total_count = 0
    texts = data.get("text", [])
    confs = data.get("conf", [])
    for idx, raw_conf in enumerate(confs):
        token = texts[idx] if idx < len(texts) else ""
        token = str(token).strip()
        if not token or not ALNUM_PATTERN.search(token):
            continue
        try:
            conf = float(raw_conf)
        except Exception:  # noqa: BLE001
            continue
        if conf < 0:
            continue
        confidences.append(conf)
        total_count += 1
        if conf < 60.0:
            low_count += 1

    if not confidences:
        return OcrMetrics(mean=0.0, median=0.0, low_conf_token_ratio=1.0)
    mean = round(sum(confidences) / len(confidences), 2)
    median = round(float(statistics.median(confidences)), 2)
    low_ratio = round(low_count / total_count, 4) if total_count else 1.0
    return OcrMetrics(mean=mean, median=median, low_conf_token_ratio=low_ratio)


def _is_language_data_missing(exc: Exception) -> bool:
    return bool(LANGUAGE_DATA_MISSING_PATTERN.search(str(exc)))


def _resolve_tesseract_cmd() -> str | None:
    executable = shutil.which("tesseract")
    if executable:
        return executable
    homebrew_tesseract = Path("/opt/homebrew/bin/tesseract")
    if homebrew_tesseract.exists():
        return str(homebrew_tesseract)
    return None


def run_ocr(
    pdf_path: Path,
    selected_pages: list[int],
    existing_page_texts: dict[int, str],
    force_ocr: bool,
    ocr_lang: str = "eng",
) -> OcrResult:
    result = OcrResult()
    target_pages: list[int] = []
    for page in selected_pages:
        existing_text = existing_page_texts.get(page, "").strip()
        if force_ocr:
            target_pages.append(page)
            result.reasons_by_page[page] = "force"
        elif not existing_text:
            target_pages.append(page)
            result.reasons_by_page[page] = "empty_text_layer"
        elif len(existing_text) < 3:
            target_pages.append(page)
            result.reasons_by_page[page] = "low_text_density"
    if not target_pages:
        return result
    result.attempted_pages = target_pages

    if pytesseract is None or pdfium is None:
        result.warnings.append(
            WarningEntry(
                code=WarningCode.OCR_RUNTIME_UNAVAILABLE,
                message="OCR dependencies are unavailable. Install pytesseract and pypdfium2.",
                details={
                    "ocr_lang": ocr_lang,
                    "reason": "dependency_unavailable",
                    "attempted_pages": target_pages,
                },
            )
        )
        return result

    tesseract_cmd = _resolve_tesseract_cmd()
    if tesseract_cmd is None:
        result.warnings.append(
            WarningEntry(
                code=WarningCode.OCR_RUNTIME_UNAVAILABLE,
                message="Tesseract executable is unavailable. Install tesseract or add it to PATH.",
                details={
                    "ocr_lang": ocr_lang,
                    "reason": "tesseract_unavailable",
                    "attempted_pages": target_pages,
                },
            )
        )
        return result
    if shutil.which("tesseract") is None:
        pytesseract_module = getattr(pytesseract, "pytesseract", None)
        if pytesseract_module is not None:
            pytesseract_module.tesseract_cmd = tesseract_cmd
    result.runtime_available = True

    try:
        document = pdfium.PdfDocument(str(pdf_path))
        result.pdf_open_count = 1
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(
            WarningEntry(
                code=WarningCode.OCR_FAILED,
                message=f"Failed to open PDF for OCR: {exc}",
                details={
                    "ocr_lang": ocr_lang,
                    "reason": "pdf_open_failed",
                    "attempted_pages": target_pages,
                },
            )
        )
        return result

    for page_number in target_pages:
        page = None
        try:
            page = document.get_page(page_number - 1)
            bitmap = page.render(scale=2.0)
            pil_image = bitmap.to_pil()
            text = (pytesseract.image_to_string(pil_image, lang=ocr_lang) or "").strip()
            data = pytesseract.image_to_data(pil_image, lang=ocr_lang, output_type=pytesseract.Output.DICT)

            metrics = _extract_confidence_metrics(data)
            result.metrics_by_page[page_number] = metrics
            if text:
                result.page_texts[page_number] = text
                result.ocr_pages.append(page_number)
                result.used_ocr = True
                if (
                    metrics.mean < OCR_CRITICAL_CONFIDENCE_MEAN_THRESHOLD
                    or metrics.low_conf_token_ratio > OCR_CRITICAL_CONFIDENCE_TOKEN_RATIO_THRESHOLD
                ):
                    result.warnings.append(
                        WarningEntry(
                            code=WarningCode.OCR_CONFIDENCE_CRITICAL,
                            message=f"OCR confidence is critical (mean={metrics.mean}, low_ratio={metrics.low_conf_token_ratio}).",
                            page=page_number,
                            details={
                                "ocr_lang": ocr_lang,
                                "ocr_confidence_mean": metrics.mean,
                                "ocr_confidence_median": metrics.median,
                                "low_conf_token_ratio": metrics.low_conf_token_ratio,
                            },
                        )
                    )
                elif (
                    metrics.mean < OCR_LOW_CONFIDENCE_MEAN_THRESHOLD
                    or metrics.low_conf_token_ratio > OCR_LOW_CONFIDENCE_TOKEN_RATIO_THRESHOLD
                ):
                    result.warnings.append(
                        WarningEntry(
                            code=WarningCode.OCR_CONFIDENCE_WARN,
                            message=f"OCR confidence is degraded (mean={metrics.mean}, low_ratio={metrics.low_conf_token_ratio}).",
                            page=page_number,
                            details={
                                "ocr_lang": ocr_lang,
                                "ocr_confidence_mean": metrics.mean,
                                "ocr_confidence_median": metrics.median,
                                "low_conf_token_ratio": metrics.low_conf_token_ratio,
                            },
                        )
                    )
            else:
                result.warnings.append(
                    WarningEntry(
                        code=WarningCode.OCR_EMPTY_RESULT,
                        message="OCR returned empty text.",
                        page=page_number,
                        details={
                            "ocr_lang": ocr_lang,
                            "reason": "empty_result",
                            "ocr_confidence_mean": metrics.mean,
                            "ocr_confidence_median": metrics.median,
                            "low_conf_token_ratio": metrics.low_conf_token_ratio,
                        },
                    )
                )
        except Exception as exc:  # noqa: BLE001
            if _is_language_data_missing(exc):
                result.warnings.append(
                    WarningEntry(
                        code=WarningCode.OCR_RUNTIME_UNAVAILABLE,
                        message=f"OCR language data is unavailable for '{ocr_lang}'.",
                        page=page_number,
                        details={"ocr_lang": ocr_lang, "reason": "language_data_missing"},
                    )
                )
                continue
            result.warnings.append(
                WarningEntry(
                    code=WarningCode.OCR_FAILED,
                    message=f"OCR failed on page {page_number}: {exc}",
                    page=page_number,
                    details={"ocr_lang": ocr_lang, "reason": "ocr_failed"},
                )
            )
        finally:
            if page is not None:
                page.close()

    close = getattr(document, "close", None)
    if close is not None:
        close()
    return result
