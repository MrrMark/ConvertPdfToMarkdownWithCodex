from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil

from pdf2md.models import WarningEntry

try:
    import pypdfium2 as pdfium
except Exception:  # noqa: BLE001
    pdfium = None

try:
    import pytesseract
except Exception:  # noqa: BLE001
    pytesseract = None


@dataclass
class OcrResult:
    warnings: list[WarningEntry] = field(default_factory=list)
    page_texts: dict[int, str] = field(default_factory=dict)
    ocr_pages: list[int] = field(default_factory=list)
    used_ocr: bool = False
    confidence_by_page: dict[int, float] = field(default_factory=dict)


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
            confidences: list[float] = []
            for raw_conf in data.get("conf", []):
                try:
                    conf = float(raw_conf)
                except Exception:  # noqa: BLE001
                    continue
                if conf >= 0:
                    confidences.append(conf)
            avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.0

            if text:
                result.page_texts[page_number] = text
                result.ocr_pages.append(page_number)
                result.used_ocr = True
                result.confidence_by_page[page_number] = avg_conf
                if avg_conf < 60.0:
                    result.warnings.append(
                        WarningEntry(
                            code="OCR_LOW_CONFIDENCE",
                            message=f"OCR confidence is low ({avg_conf}).",
                            page=page_number,
                            details={"avg_confidence": avg_conf},
                        )
                    )
            else:
                result.warnings.append(
                    WarningEntry(
                        code="OCR_EMPTY_RESULT",
                        message="OCR returned empty text.",
                        page=page_number,
                        details={"avg_confidence": avg_conf},
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
