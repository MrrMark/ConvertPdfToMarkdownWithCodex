from pathlib import Path

import pytest
import pdf2md.serializers.rag_figure_semantics as semantics
import pdf2md.serializers.rag_ocr_evidence as evidence
from pdf2md.extractors.ocr_backends import OCRBackendResult


class Backend:
    def __init__(self):
        self.calls = 0

    def recognize(self, image, *, lang):
        self.calls += 1
        return OCRBackendResult(text="NVME1", confidence_data={"text": ["NVME1"], "conf": ["90"]})


class Document:
    def __init__(self, path, **kwargs):
        self.rendered = []
        self.closed_pages = []
        self.closed = False

    def get_page(self, index):
        document = self

        class Page:
            def render(self, *, scale):
                from PIL import Image
                document.rendered.append(index)
                return type("Bitmap", (), {"to_pil": lambda self: Image.new("RGB", (400, 400)), "close": lambda self: None})()

            def close(self):
                document.closed_pages.append(index)

        return Page()

    def close(self):
        self.closed = True


def figure(page=1, index=1, **kwargs):
    return {"page": page, "figure_index": index, "figure_id": f"f{page}-{index}",
            "bbox": [10, 10, 60, 60], **kwargs}


def test_excluded_decorations_skip_ocr_but_other_exclusions_remain(monkeypatch, tmp_path):
    backend = Backend()
    document = Document("")
    monkeypatch.setattr(semantics, "_region_ocr_runtime", lambda **kw: (
        type("Pdfium", (), {"PdfDocument": lambda path: document}), backend, None))
    records = [figure(status="excluded", classification_reasons=["TINY_DECORATIVE"]),
               figure(index=2, status="excluded", classification_reasons=["OTHER"]),
               figure(index=3, status="available", classification_reasons=["TINY_DECORATIVE"])]
    augmented, metrics = semantics.augment_figure_records_with_region_ocr(records, pdf_path=tmp_path / "a.pdf")
    assert augmented[0]["figure_region_ocr"]["region_ocr"]["status"] == "not_attempted"
    assert augmented[0]["figure_region_ocr"]["region_ocr"]["reason"] == "tiny_decorative"
    assert all(row["figure_region_ocr"]["region_ocr"]["attempted"] for row in augmented[1:])
    assert metrics["region_ocr_skipped_decorative_count"] == 1
    assert backend.calls == 1  # Equal retained crops reuse one backend call.
    assert document.rendered == [0]
    assert document.closed_pages == [0] and document.closed
    assert "figure_region_ocr" not in records[0]


def test_figures_and_tables_share_page_render_and_result(monkeypatch, tmp_path):
    backend = Backend()
    document = Document("")
    monkeypatch.setattr(evidence, "_region_ocr_runtime", lambda **kw: (
        type("Pdfium", (), {"PdfDocument": lambda path: document}), backend, None))
    figures = [figure(page=2), figure(page=1)]
    tables = [{"page": 1, "table_index": 1, "source_mode": "image", "bbox": [10, 10, 60, 60], "records": [{}]}]
    results, table_results, metrics = evidence.prepare_region_ocr_results(
        figure_records=figures, rag_tables=tables, pdf_path=tmp_path / "a.pdf", ocr_lang="eng", ocr_backend="tesseract",
    )
    assert len(results) == 2 and list(table_results) == ["page-0001-table-0001"]
    assert metrics["region_ocr_backend_call_count"] == backend.calls == 2
    assert metrics["region_ocr_page_render_count"] == 2
    assert metrics["region_ocr_result_cache_hit_count"] == 1
    assert document.rendered == [0, 1]
    assert document.closed_pages == [0, 1] and document.closed
    assert results[1]["candidate"] == table_results["page-0001-table-0001"]["candidate"]


def test_all_decorative_records_need_no_runtime(monkeypatch):
    def unavailable(**kw):
        raise AssertionError("runtime must not initialize")
    monkeypatch.setattr(evidence, "_region_ocr_runtime", unavailable)
    results, _, metrics = evidence.prepare_region_ocr_results(
        figure_records=[figure(status="excluded", classification_reasons=["TINY_DECORATIVE"])],
        rag_tables=[], pdf_path=Path("missing.pdf"), ocr_lang="eng", ocr_backend="tesseract",
    )
    assert results[0]["status"] == "not_attempted"
    assert metrics["region_ocr_backend_call_count"] == metrics["region_ocr_page_render_count"] == 0


def test_cache_does_not_cross_languages_backends_pages_or_sessions():
    document, backend, other_backend = Document(""), Backend(), Backend()
    cache = semantics.RegionOCRCache()
    def run(record, language="eng", engine=backend):
        return semantics._region_ocr_result(document=document, backend=engine, record=record,
            ocr_lang=language, ocr_backend="test", runtime_unavailable_reason=None, cache=cache)
    first = run(figure())
    same_pixels = run(figure(bbox=[10.01, 10, 60, 60]))
    assert backend.calls == 1
    assert first["candidate"]["bbox"] != same_pixels["candidate"]["bbox"]
    run(figure(), "kor")
    run(figure(), engine=other_backend)
    run(figure(page=2))
    assert backend.calls == 3 and other_backend.calls == 1
    assert document.closed_pages == [0]
    cache.close()
    assert document.closed_pages == [0, 1]
    run(figure(page=2))
    assert backend.calls == 4
    cache.close()


def test_result_cache_is_bounded_and_closes_crops():
    cache, document, backend = semantics.RegionOCRCache(), Document(""), Backend()
    cache.page_image(document, 0)
    for index in range(semantics.REGION_OCR_MAX_CACHED_CROPS + 1):
        cache.recognize(backend, (index, 0, index + 5, 5), lang="eng")
    assert len(cache.results) == semantics.REGION_OCR_MAX_CACHED_CROPS
    cache.recognize(backend, (0, 0, 5, 5), lang="eng")
    assert backend.calls == semantics.REGION_OCR_MAX_CACHED_CROPS + 2
    cache.close()
    assert cache.image is None and not cache.results


@pytest.mark.parametrize("bbox,expected", [(None, "missing_bbox"), ([10, 10, 10.5, 10.5], "invalid_bbox")])
def test_invalid_crop_does_not_call_backend(monkeypatch, tmp_path, bbox, expected):
    backend, document = Backend(), Document("")
    monkeypatch.setattr(evidence, "_region_ocr_runtime", lambda **kw: (
        type("Pdfium", (), {"PdfDocument": lambda path: document}), backend, None))
    results, _, metrics = evidence.prepare_region_ocr_results(figure_records=[figure(bbox=bbox)], rag_tables=[],
        pdf_path=tmp_path / "a.pdf", ocr_backend="test", ocr_lang="eng")
    assert results[0]["reason"] == expected
    assert backend.calls == metrics["region_ocr_backend_call_count"] == 0
    assert document.closed


def test_runtime_unavailable_preserves_skip_and_retained_diagnostics(monkeypatch, tmp_path):
    monkeypatch.setattr(evidence, "_region_ocr_runtime", lambda **kw: (None, None, "dependency_unavailable"))
    results, _, metrics = evidence.prepare_region_ocr_results(figure_records=[figure(),
        figure(index=2, status="excluded", classification_reasons=["TINY_DECORATIVE"])], rag_tables=[],
        pdf_path=tmp_path / "a.pdf", ocr_backend="test", ocr_lang="eng")
    assert results[0]["status"] == "runtime_unavailable"
    assert results[1]["status"] == "not_attempted"
    assert metrics["region_ocr_backend_call_count"] == 0


def test_page_and_backend_failures_are_partial_and_release_resources(monkeypatch, tmp_path):
    document = Document("")
    original_page = document.get_page
    def get_page(index):
        if index == 0:
            raise RuntimeError("bad page")
        return original_page(index)
    document.get_page = get_page
    class FlakyBackend(Backend):
        def recognize(self, image, *, lang):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("recognize failed")
            return OCRBackendResult(text="NVME1", confidence_data={"text": ["NVME1"], "conf": ["90"]})
    backend = FlakyBackend()
    monkeypatch.setattr(evidence, "_region_ocr_runtime", lambda **kw: (
        type("Pdfium", (), {"PdfDocument": lambda path, **kwargs: document}), backend, None))
    results, _, metrics = evidence.prepare_region_ocr_results(figure_records=[figure(page=i) for i in (1, 2, 3)],
        rag_tables=[], pdf_path=tmp_path / "a.pdf", password="secret", ocr_backend="test", ocr_lang="eng")
    assert [result["status"] for result in results] == ["rejected", "rejected", "candidate"]
    assert metrics["region_ocr_backend_call_count"] == 2
    assert document.closed_pages == [1, 2] and document.closed


def test_prepared_results_preserve_evidence_order_and_source_refs(monkeypatch, tmp_path):
    document, backend = Document(""), Backend()
    monkeypatch.setattr(evidence, "_region_ocr_runtime", lambda **kw: (
        type("Pdfium", (), {"PdfDocument": lambda path: document}), backend, None))
    figures = [figure(page=2), figure(page=1)]
    tables = [{"page": 1, "table_index": 1, "source_mode": "image", "bbox": [10, 10, 60, 60], "records": [{}]}]
    prepared, prepared_tables, _ = evidence.prepare_region_ocr_results(figure_records=figures, rag_tables=tables,
        pdf_path=tmp_path / "a.pdf", ocr_backend="test", ocr_lang="eng")
    augmented, _ = semantics.augment_figure_records_with_region_ocr(figures, region_results=prepared)
    calls = backend.calls
    records, _ = evidence.build_region_ocr_evidence_records(figure_records=augmented, rag_tables=tables,
        source_sha256="a" * 64, table_region_results=prepared_tables)
    assert [record["target_id"] for record in records] == ["f1-1", "f2-1", "page-0001-table-0001"]
    assert [record["evidence_id"] for record in records] == [f"ocr-evidence-{i:06d}" for i in (1, 2, 3)]
    assert [record["source_refs"][0]["page"] for record in records] == [1, 2, 1]
    assert backend.calls == calls
