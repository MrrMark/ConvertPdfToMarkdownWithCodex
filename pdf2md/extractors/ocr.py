from __future__ import annotations

import re
import shutil
import statistics
from dataclasses import dataclass, field
from pathlib import Path

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
    used_ocr: bool = False
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


def run_ocr(
    pdf_path: Path,
    selected_pages: list[int],
    existing_page_texts: dict[int, str],
    force_ocr: bool,
) -> OcrResult:
    result = OcrResult()
    target_pages: list[int] = []
    for page in selected_pages:
        if force_ocr or not existing_page_texts.get(page, "").strip():
            target_pages.append(page)
    if not target_pages:
        return result

    if pytesseract is None or pdfium is None:
        result.warnings.append(
            WarningEntry(
                code="OCR_RUNTIME_UNAVAILABLE",
                message="OCR dependencies are unavailable. Install pytesseract and pypdfium2.",
            )
        )
        return result

    if shutil.which("tesseract") is None:
        homebrew_tesseract = Path("/opt/homebrew/bin/tesseract")
        if homebrew_tesseract.exists():
            pytesseract.pytesseract.tesseract_cmd = str(homebrew_tesseract)

    try:
        document = pdfium.PdfDocument(str(pdf_path))
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(WarningEntry(code="OCR_FAILED", message=f"Failed to open PDF for OCR: {exc}"))
        return result

    for page_number in target_pages:
        try:
            page = document.get_page(page_number - 1)
            bitmap = page.render(scale=2.0)
            pil_image = bitmap.to_pil()
            text = (pytesseract.image_to_string(pil_image) or "").strip()
            data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT)
            page.close()

            metrics = _extract_confidence_metrics(data)
            if text:
                result.page_texts[page_number] = text
                result.ocr_pages.append(page_number)
                result.used_ocr = True
                result.metrics_by_page[page_number] = metrics
                if metrics.mean < 50.0 or metrics.low_conf_token_ratio > 0.5:
                    result.warnings.append(
                        WarningEntry(
                            code="OCR_CONFIDENCE_CRITICAL",
                            message=f"OCR confidence is critical (mean={metrics.mean}, low_ratio={metrics.low_conf_token_ratio}).",
                            page=page_number,
                            details={
                                "ocr_confidence_mean": metrics.mean,
                                "ocr_confidence_median": metrics.median,
                                "low_conf_token_ratio": metrics.low_conf_token_ratio,
                            },
                        )
                    )
                elif metrics.mean < 75.0 or metrics.low_conf_token_ratio > 0.25:
                    result.warnings.append(
                        WarningEntry(
                            code="OCR_CONFIDENCE_WARN",
                            message=f"OCR confidence is degraded (mean={metrics.mean}, low_ratio={metrics.low_conf_token_ratio}).",
                            page=page_number,
                            details={
                                "ocr_confidence_mean": metrics.mean,
                                "ocr_confidence_median": metrics.median,
                                "low_conf_token_ratio": metrics.low_conf_token_ratio,
                            },
                        )
                    )
            else:
                result.warnings.append(
                    WarningEntry(
                        code="OCR_EMPTY_RESULT",
                        message="OCR returned empty text.",
                        page=page_number,
                        details={
                            "ocr_confidence_mean": metrics.mean,
                            "ocr_confidence_median": metrics.median,
                            "low_conf_token_ratio": metrics.low_conf_token_ratio,
                        },
                    )
                )
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(
                WarningEntry(
                    code="OCR_FAILED",
                    message=f"OCR failed on page {page_number}: {exc}",
                    page=page_number,
                )
            )

    return result
