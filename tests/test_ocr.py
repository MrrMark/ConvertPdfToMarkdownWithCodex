from __future__ import annotations

from types import SimpleNamespace

import pdf2md.extractors.ocr as ocr_module
import pdf2md.extractors.ocr_backends.tesseract as tesseract_backend_module
from pdf2md.extractors.ocr import run_ocr


class _FakePage:
    def __init__(self, index: int = 0) -> None:
        self.index = index

    def render(self, scale: float):  # noqa: ANN201, ARG002
        return SimpleNamespace(to_pil=lambda: SimpleNamespace(page_number=self.index + 1))

    def close(self) -> None:
        return None


class _FakeDocument:
    def __init__(self, path: str) -> None:  # noqa: ARG002
        self.path = path

    def get_page(self, index: int) -> _FakePage:
        return _FakePage(index)

    def close(self) -> None:
        return None


def _patch_ocr_runtime(monkeypatch, image_to_string, image_to_data) -> None:  # noqa: ANN001
    fake_tesseract = SimpleNamespace(
        Output=SimpleNamespace(DICT="dict"),
        image_to_string=image_to_string,
        image_to_data=image_to_data,
    )
    monkeypatch.setattr(ocr_module, "pytesseract", fake_tesseract)
    monkeypatch.setattr(ocr_module, "pdfium", SimpleNamespace(PdfDocument=_FakeDocument))
    monkeypatch.setattr(tesseract_backend_module.shutil, "which", lambda name: "/usr/bin/tesseract")


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
    monkeypatch.setattr(tesseract_backend_module.shutil, "which", lambda name: "/usr/bin/tesseract")

    result = run_ocr(sample_pdf, [1], {1: ""}, force_ocr=False, ocr_lang="kor+eng")

    assert result.used_ocr is True
    assert result.runtime_available is True
    assert result.attempted_pages == [1]
    assert result.reasons_by_page == {1: "empty_text_layer"}
    assert calls == [("string", "kor+eng"), ("data", "kor+eng")]


def test_run_ocr_warns_on_degraded_confidence_without_correcting_text(sample_pdf, monkeypatch) -> None:  # noqa: ANN001
    _patch_ocr_runtime(
        monkeypatch,
        image_to_string=lambda image, lang: "teh SOURCE txt",  # noqa: ARG005
        image_to_data=lambda image, lang, output_type: {  # noqa: ARG005
            "text": ["teh", "SOURCE", "txt"],
            "conf": ["72", "69", "71"],
        },
    )

    result = run_ocr(sample_pdf, [1], {1: ""}, force_ocr=False, ocr_lang="eng")

    assert result.page_texts[1] == "teh SOURCE txt"
    assert result.metrics_by_page[1].mean == 70.67
    assert result.metrics_by_page[1].low_conf_token_ratio == 0.0
    assert result.warnings[0].code == "OCR_CONFIDENCE_WARN"
    assert result.warnings[0].details["ocr_confidence_mean"] == 70.67


def test_run_ocr_marks_critical_confidence_when_low_tokens_dominate(sample_pdf, monkeypatch) -> None:  # noqa: ANN001
    _patch_ocr_runtime(
        monkeypatch,
        image_to_string=lambda image, lang: "noisy scan",  # noqa: ARG005
        image_to_data=lambda image, lang, output_type: {  # noqa: ARG005
            "text": ["noisy", "scan"],
            "conf": ["25", "35"],
        },
    )

    result = run_ocr(sample_pdf, [1], {1: ""}, force_ocr=False, ocr_lang="eng")

    assert result.used_ocr is True
    assert result.metrics_by_page[1].low_conf_token_ratio == 1.0
    assert result.warnings[0].code == "OCR_CONFIDENCE_CRITICAL"


def test_run_ocr_reports_empty_result_with_confidence_metrics(sample_pdf, monkeypatch) -> None:  # noqa: ANN001
    _patch_ocr_runtime(
        monkeypatch,
        image_to_string=lambda image, lang: "   ",  # noqa: ARG005
        image_to_data=lambda image, lang, output_type: {  # noqa: ARG005
            "text": [" "],
            "conf": ["-1"],
        },
    )

    result = run_ocr(sample_pdf, [1], {1: ""}, force_ocr=False, ocr_lang="eng")

    assert result.used_ocr is False
    assert result.page_texts == {}
    assert result.metrics_by_page[1] == ocr_module.OcrMetrics(mean=0.0, median=0.0, low_conf_token_ratio=1.0)
    assert result.warnings[0].code == "OCR_EMPTY_RESULT"
    assert result.warnings[0].details == {
        "ocr_lang": "eng",
        "ocr_backend": "tesseract",
        "reason": "empty_result",
        "ocr_confidence_mean": 0.0,
        "ocr_confidence_median": 0.0,
        "low_conf_token_ratio": 1.0,
        "force_ocr": False,
        "attempt_reason": "empty_text_layer",
        "existing_text_char_count": 0,
    }


def test_run_ocr_reports_missing_language_data_as_runtime_diagnostic(sample_pdf, monkeypatch) -> None:  # noqa: ANN001
    def image_to_string(image, lang: str):  # noqa: ANN001, ARG001
        raise RuntimeError("Failed loading language 'kor'")

    _patch_ocr_runtime(
        monkeypatch,
        image_to_string=image_to_string,
        image_to_data=lambda image, lang, output_type: {},  # noqa: ARG005
    )

    result = run_ocr(sample_pdf, [1], {1: ""}, force_ocr=False, ocr_lang="kor+eng")

    assert result.runtime_available is True
    assert result.used_ocr is False
    assert result.warnings[0].code == "OCR_RUNTIME_UNAVAILABLE"
    assert result.warnings[0].details == {
        "ocr_lang": "kor+eng",
        "ocr_backend": "tesseract",
        "reason": "language_data_missing",
    }


def test_run_ocr_reports_missing_tesseract_executable_with_attempt_context(sample_pdf, monkeypatch) -> None:  # noqa: ANN001
    _patch_ocr_runtime(
        monkeypatch,
        image_to_string=lambda image, lang: "unused",  # noqa: ARG005
        image_to_data=lambda image, lang, output_type: {},  # noqa: ARG005
    )
    monkeypatch.setattr(tesseract_backend_module, "_resolve_tesseract_cmd", lambda: None)

    result = run_ocr(sample_pdf, [1], {1: ""}, force_ocr=False, ocr_lang="kor+eng")

    assert result.used_ocr is False
    assert result.runtime_available is False
    assert result.attempted_pages == [1]
    assert result.warnings[0].code == "OCR_RUNTIME_UNAVAILABLE"
    assert result.warnings[0].details == {
        "ocr_lang": "kor+eng",
        "ocr_backend": "tesseract",
        "reason": "tesseract_unavailable",
        "attempted_pages": [1],
    }


def test_run_ocr_runtime_unavailable_records_attempt_without_text(sample_pdf, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(ocr_module, "pytesseract", None)
    monkeypatch.setattr(ocr_module, "pdfium", None)

    result = run_ocr(sample_pdf, [1], {1: ""}, force_ocr=False, ocr_lang="eng")

    assert result.used_ocr is False
    assert result.runtime_available is False
    assert result.attempted_pages == [1]
    assert result.warnings[0].code == "OCR_RUNTIME_UNAVAILABLE"
    assert result.warnings[0].details == {
        "ocr_lang": "eng",
        "ocr_backend": "tesseract",
        "reason": "dependency_unavailable",
        "attempted_pages": [1],
    }


def test_run_ocr_reports_unsupported_backend_without_attempting_text(sample_pdf) -> None:  # noqa: ANN001
    result = run_ocr(sample_pdf, [1], {1: ""}, force_ocr=False, ocr_lang="eng", ocr_backend="rapidocr")

    assert result.used_ocr is False
    assert result.runtime_available is False
    assert result.attempted_pages == [1]
    assert result.warnings[0].code == "OCR_RUNTIME_UNAVAILABLE"
    assert result.warnings[0].details == {
        "ocr_lang": "eng",
        "ocr_backend": "rapidocr",
        "reason": "unsupported_ocr_backend",
        "attempted_pages": [1],
    }


def test_run_ocr_parallel_pages_merge_in_page_order(sample_pdf, monkeypatch) -> None:  # noqa: ANN001
    def image_to_string(image, lang: str):  # noqa: ANN001, ARG001
        return f"ocr text page {image.page_number}"

    def image_to_data(image, lang: str, output_type):  # noqa: ANN001, ARG001
        return {"text": ["ocr", "text", str(image.page_number)], "conf": ["95", "92", "91"]}

    _patch_ocr_runtime(monkeypatch, image_to_string=image_to_string, image_to_data=image_to_data)

    sequential = run_ocr(
        sample_pdf,
        [1, 2, 3, 4],
        {1: "", 2: "", 3: "", 4: ""},
        force_ocr=True,
        ocr_lang="eng",
        worker_count=1,
    )
    result = run_ocr(
        sample_pdf,
        [1, 2, 3, 4],
        {1: "", 2: "", 3: "", 4: ""},
        force_ocr=True,
        ocr_lang="eng",
        worker_count=2,
    )

    assert result.runtime_available is True
    assert result.used_ocr is True
    assert result.pdf_open_count == 2
    assert result.attempted_pages == [1, 2, 3, 4]
    assert result.ocr_pages == [1, 2, 3, 4]
    assert list(result.page_texts) == [1, 2, 3, 4]
    assert result.page_texts[4] == "ocr text page 4"
    assert list(result.metrics_by_page) == [1, 2, 3, 4]
    assert result.warnings == []
    assert sequential.pdf_open_count == 1
    assert sequential.ocr_pages == result.ocr_pages
    assert sequential.page_texts == result.page_texts
    assert sequential.metrics_by_page == result.metrics_by_page
    assert sequential.warnings == result.warnings


def test_run_ocr_parallel_warnings_remain_page_ordered(sample_pdf, monkeypatch) -> None:  # noqa: ANN001
    def image_to_string(image, lang: str):  # noqa: ANN001, ARG001
        if image.page_number == 2:
            return " "
        if image.page_number == 3:
            raise RuntimeError("Failed loading language 'eng'")
        return f"ocr text page {image.page_number}"

    def image_to_data(image, lang: str, output_type):  # noqa: ANN001, ARG001
        return {"text": ["ocr", "text"], "conf": ["95", "92"]}

    _patch_ocr_runtime(monkeypatch, image_to_string=image_to_string, image_to_data=image_to_data)

    result = run_ocr(
        sample_pdf,
        [1, 2, 3, 4],
        {1: "", 2: "", 3: "", 4: ""},
        force_ocr=True,
        ocr_lang="eng",
        worker_count=2,
    )

    assert result.pdf_open_count == 2
    assert result.ocr_pages == [1, 4]
    assert [warning.page for warning in result.warnings] == [2, 3]
    assert [warning.code for warning in result.warnings] == ["OCR_EMPTY_RESULT", "OCR_RUNTIME_UNAVAILABLE"]
