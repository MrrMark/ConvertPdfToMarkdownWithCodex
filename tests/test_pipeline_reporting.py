from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pdf2md.pipeline as pipeline_module
from fixtures.pdf_builder import build_image_only_pdf
from pdf2md.config import Config
from pdf2md.constants import WarningCode, WarningDomain, WarningSeverity, warning_code_spec
from pdf2md.extractors.images import ImageExtractionResult
from pdf2md.extractors.ocr import OcrMetrics, OcrResult
from pdf2md.extractors.tables import TableExtractionResult
from pdf2md.extractors.text import PageLayoutMetadata, TextLayoutResult, TextLine
from pdf2md.models import DomainAdapterMode, ImageMode, TableAsset, TableMode, WarningEntry
from pdf2md.pipeline import EXIT_PARTIAL, EXIT_SUCCESS, run_conversion
from pdf2md.reporting import determine_conversion_status, is_advisory_warning, warning_affects_exit_code


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return cls(2024, 1, 2, 3, 4, 5, tzinfo=tz or timezone.utc)


def test_pipeline_report_schema_and_partial_status(sample_pdf: Path, tmp_path: Path, monkeypatch) -> None:
    def fake_run_ocr(*args, **kwargs) -> OcrResult:
        return OcrResult(
            warnings=[WarningEntry(code="OCR_CONFIDENCE_WARN", message="warn", page=1)],
            page_texts={},
            ocr_pages=[],
            used_ocr=False,
        )

    def fake_extract_tables(*args, **kwargs) -> TableExtractionResult:
        result = TableExtractionResult(
            warnings=[
                WarningEntry(
                    code="TABLE_COMPLEXITY_HTML_FALLBACK",
                    message="fallback",
                    page=1,
                    details={"table_index": 1, "reasons": ["AMBIGUOUS_GRID"]},
                )
            ],
            assets=[TableAsset(page=1, index=1, mode="html", bbox=[10.0, 20.0, 30.0, 40.0])],
            fallbacks=[
                {
                    "page": 1,
                    "table_index": 1,
                    "mode": "html",
                    "reasons": ["AMBIGUOUS_GRID"],
                    "selected_strategy": "default",
                    "quality_score": 0.42,
                }
            ],
            table_quality=[],
            table_counts={
                "table_total": 1,
                "table_html_count": 1,
                "table_gfm_count": 0,
                "table_recovered_count": 0,
                "table_unresolved_count": 1,
                "table_markdown_forced_count": 0,
                "table_html_forced_count": 0,
            },
        )
        return result

    monkeypatch.setattr(pipeline_module, "run_ocr", fake_run_ocr)
    monkeypatch.setattr(pipeline_module, "extract_tables", fake_extract_tables)
    monkeypatch.setattr(pipeline_module, "extract_images", lambda *args, **kwargs: ImageExtractionResult())

    output_dir = tmp_path / "reporting"
    result = run_conversion(
        Config(
            input_pdf=sample_pdf,
            output_dir=output_dir,
            image_mode=ImageMode.REFERENCED,
            table_mode=TableMode.AUTO,
        )
    )

    assert result.exit_code == EXIT_PARTIAL
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert report["schema_version"] == "1.0"
    assert manifest["schema_version"] == "1.0"
    assert report["status"] == "partial_success"
    assert report["summary"]["table_fallback_count"] == 1
    assert report["summary"]["table_expected_fallback_count"] == 1
    assert report["summary"]["table_actionable_fallback_count"] == 0
    assert report["summary"]["advisory_warning_count"] == 1
    assert report["summary"]["actionable_warning_count"] == 1
    assert report["summary"]["ocr_actionable_warning_count"] == 1
    assert report["summary"]["ocr_advisory_warning_count"] == 0
    assert report["summary"]["table_actionable_low_quality_count"] == 0
    assert report["summary"]["table_advisory_low_quality_count"] == 0
    assert report["summary"]["table_mode_requested"] == "auto"
    assert report["summary"]["page_status_counts"]["partial_success"] == 1
    assert report["summary"]["page_status_counts"]["success"] == 1
    assert report["summary"]["structure_marker_suppressed_count"] == 0
    assert report["summary"]["structure_marker_recovered_count"] == 0
    assert report["summary"]["structure_marker_recovered_exact_count"] == 0
    assert report["summary"]["structure_marker_recovered_context_count"] == 0
    assert report["summary"]["structure_marker_suppressed_no_candidate_count"] == 0
    assert report["summary"]["structure_marker_suppressed_ambiguous_count"] == 0


def test_expected_table_fallback_warning_is_advisory_for_status(sample_pdf: Path, tmp_path: Path, monkeypatch) -> None:
    def fake_extract_tables(*args, **kwargs) -> TableExtractionResult:
        return TableExtractionResult(
            warnings=[
                WarningEntry(
                    code="TABLE_COMPLEXITY_HTML_FALLBACK",
                    message="fallback",
                    page=1,
                    details={"table_index": 1, "reasons": ["AMBIGUOUS_GRID"]},
                )
            ],
            assets=[TableAsset(page=1, index=1, mode="html", bbox=[10.0, 20.0, 30.0, 40.0])],
            fallbacks=[
                {
                    "page": 1,
                    "table_index": 1,
                    "mode": "html",
                    "reasons": ["AMBIGUOUS_GRID"],
                    "selected_strategy": "default",
                    "quality_score": 0.95,
                }
            ],
            table_quality=[
                {
                    "page": 1,
                    "table_index": 1,
                    "quality_score": 0.95,
                    "reasons": ["AMBIGUOUS_GRID"],
                    "unresolved": True,
                    "mode": "html",
                }
            ],
            table_counts={
                "table_total": 1,
                "table_html_count": 1,
                "table_gfm_count": 0,
                "table_recovered_count": 0,
                "table_unresolved_count": 1,
                "table_markdown_forced_count": 0,
                "table_html_forced_count": 0,
            },
        )

    monkeypatch.setattr(pipeline_module, "run_ocr", lambda *args, **kwargs: OcrResult())
    monkeypatch.setattr(pipeline_module, "extract_tables", fake_extract_tables)
    monkeypatch.setattr(pipeline_module, "extract_images", lambda *args, **kwargs: ImageExtractionResult())

    output_dir = tmp_path / "expected-fallback-advisory"
    result = run_conversion(
        Config(
            input_pdf=sample_pdf,
            output_dir=output_dir,
            image_mode=ImageMode.REFERENCED,
            table_mode=TableMode.AUTO,
        )
    )

    assert result.exit_code == EXIT_SUCCESS
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert report["status"] == "success"
    assert report["warnings"][0]["code"] == "TABLE_COMPLEXITY_HTML_FALLBACK"
    assert manifest["warnings"][0]["code"] == "TABLE_COMPLEXITY_HTML_FALLBACK"
    assert report["summary"]["partial_success"] is False
    assert report["summary"]["warning_count"] == 1
    assert report["summary"]["actionable_warning_count"] == 0
    assert report["summary"]["advisory_warning_count"] == 1
    assert report["summary"]["table_fallback_count"] == 1
    assert report["summary"]["table_expected_fallback_count"] == 1
    assert report["summary"]["table_actionable_fallback_count"] == 0
    assert report["summary"]["table_low_quality_count"] == 0
    assert report["summary"]["table_actionable_low_quality_count"] == 0
    assert report["summary"]["table_advisory_low_quality_count"] == 0
    assert report["summary"]["page_status_counts"]["partial_success"] == 0
    assert report["summary"]["page_status_counts"]["success"] == 2
    page_one = next(page for page in report["page_results"] if page["page"] == 1)
    assert page_one["warning_count"] == 1
    assert page_one["status"] == "success"


def test_pipeline_outputs_are_deterministic_with_fixed_clock(sample_pdf: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(pipeline_module, "datetime", _FixedDateTime)

    first = tmp_path / "first"
    second = tmp_path / "second"
    config_first = Config(input_pdf=sample_pdf, output_dir=first)
    config_second = Config(input_pdf=sample_pdf, output_dir=second)

    result_first = run_conversion(config_first)
    result_second = run_conversion(config_second)

    assert result_first.exit_code == EXIT_SUCCESS
    assert result_second.exit_code == EXIT_SUCCESS
    assert (first / "document.md").read_text(encoding="utf-8") == (second / "document.md").read_text(encoding="utf-8")
    assert (first / "manifest.json").read_text(encoding="utf-8") == (second / "manifest.json").read_text(encoding="utf-8")
    assert (first / "report.json").read_text(encoding="utf-8") == (second / "report.json").read_text(encoding="utf-8")


def test_manifest_uses_canonical_html_mode_for_legacy_alias(sample_pdf: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(pipeline_module, "extract_images", lambda *args, **kwargs: ImageExtractionResult())
    monkeypatch.setattr(pipeline_module, "extract_tables", lambda *args, **kwargs: TableExtractionResult())
    monkeypatch.setattr(pipeline_module, "run_ocr", lambda *args, **kwargs: OcrResult())

    output_dir = tmp_path / "legacy-html-mode"
    result = run_conversion(
        Config(
            input_pdf=sample_pdf,
            output_dir=output_dir,
            image_mode=ImageMode.REFERENCED,
            table_mode=TableMode.HTML_ONLY,
        )
    )

    assert result.exit_code == EXIT_SUCCESS
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert manifest["options"]["table_mode"] == "html"
    assert report["summary"]["table_mode_requested"] == "html"


def test_no_image_mode_skips_image_boxes_and_visual_sidecars(
    sample_pdf: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fail_get_image_boxes(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("get_image_boxes must not run in image_mode=none")

    def fail_extract_images(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("extract_images must not run in image_mode=none")

    def fail_figure_semantics(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("figure semantics must not run in image_mode=none")

    monkeypatch.setattr(pipeline_module.PdfDocumentContext, "get_image_boxes", fail_get_image_boxes)
    monkeypatch.setattr(pipeline_module, "extract_images", fail_extract_images)
    monkeypatch.setattr(pipeline_module, "augment_figure_records_with_region_ocr", fail_figure_semantics)
    monkeypatch.setattr(pipeline_module, "build_figure_description_records", fail_figure_semantics)
    monkeypatch.setattr(pipeline_module, "build_figure_structure_records", fail_figure_semantics)
    monkeypatch.setattr(pipeline_module, "extract_tables", lambda *args, **kwargs: TableExtractionResult())
    monkeypatch.setattr(pipeline_module, "run_ocr", lambda *args, **kwargs: OcrResult())

    output_dir = tmp_path / "no-image"
    result = run_conversion(
        Config(
            input_pdf=sample_pdf,
            output_dir=output_dir,
            image_mode=ImageMode.NONE,
            rag_profile="technical_spec_rag_visual",
            domain_adapter=DomainAdapterMode.NVME,
            rag_figure_text_chunks=True,
            figure_region_ocr=True,
            rag_generated_figure_descriptions=True,
            figure_structure_extraction=True,
        )
    )

    assert result.exit_code == EXIT_SUCCESS
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))

    assert manifest["options"]["image_mode"] == "none"
    assert manifest["options"]["image_extraction_skipped"] is True
    assert manifest["options"]["image_extraction_skip_reason"] == "image_mode_none"
    assert manifest["options"]["figure_sidecars_skipped"] is True
    assert "figures_rag_jsonl_filename" not in manifest["options"]
    assert "figure_descriptions_jsonl_filename" not in manifest["options"]
    assert "figure_structures_jsonl_filename" not in manifest["options"]
    assert manifest["images"] == []
    assert manifest["excluded_images"] == []

    assert report["status"] == "success"
    assert report["warnings"][0]["code"] == WarningCode.IMAGE_EXTRACTION_SKIPPED
    assert report["warnings"][0]["details"]["skip_reason"] == "image_mode_none"
    assert report["summary"]["image_extraction_skipped"] is True
    assert report["summary"]["image_extraction_skip_reason"] == "image_mode_none"
    assert report["summary"]["figure_sidecars_skipped"] is True
    assert report["summary"]["figure_rag_record_count"] == 0
    assert report["summary"]["figure_rag_file_count"] == 0
    assert report["summary"]["advisory_warning_count"] == 1
    assert report["summary"]["actionable_warning_count"] == 0
    assert not (output_dir / "figures_rag.jsonl").exists()
    assert not (output_dir / "figure_descriptions_rag.jsonl").exists()
    assert not (output_dir / "figure_structures_rag.jsonl").exists()


def test_pipeline_applies_structure_marker_recovery_without_inserting_image_block(
    sample_pdf: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_extract_images(*args, **kwargs) -> ImageExtractionResult:
        return ImageExtractionResult(
            structure_recoveries=[
                {
                    "page": 1,
                    "top": 770.0,
                    "title_text": "Hello PDF Page 1",
                    "recovered_text": "2.2.1",
                    "confidence": 97.0,
                    "recovery_strategy": "ocr_exact",
                    "context_validated": False,
                    "source_candidates": [{"text": "2.2.1", "votes": 4, "confidence": 97.0}],
                    "parent_heading_index": "2.2",
                }
            ]
        )

    monkeypatch.setattr(pipeline_module, "extract_images", fake_extract_images)
    monkeypatch.setattr(pipeline_module, "extract_tables", lambda *args, **kwargs: TableExtractionResult())
    monkeypatch.setattr(pipeline_module, "run_ocr", lambda *args, **kwargs: OcrResult())

    output_dir = tmp_path / "structure-recovery"
    result = run_conversion(Config(input_pdf=sample_pdf, output_dir=output_dir, keep_page_markers=True))

    assert result.exit_code == EXIT_SUCCESS
    document = (output_dir / "document.md").read_text(encoding="utf-8")
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert "2.2.1 Hello PDF Page 1" in document
    assert "![Image" not in document
    assert "structure_marker_recovered_count" in report["summary"]


def test_pipeline_reports_markdown_structure_and_hyphenation_counts(
    sample_pdf: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_text_layout(*args, **kwargs) -> TextLayoutResult:  # noqa: ANN001
        return TextLayoutResult(
            lines_by_page={
                1: [
                    TextLine("2.2 Heading", 72.0, 84.0, 72.0, 180.0),
                    TextLine("- bullet", 130.0, 142.0, 72.0, 140.0),
                    TextLine("interoper-", 190.0, 202.0, 72.0, 150.0),
                    TextLine("ability", 230.0, 242.0, 72.0, 130.0),
                ]
            },
            metadata_by_page={1: PageLayoutMetadata(page=1, page_width=595.0, page_height=842.0, raw_line_count=4)},
            raw_lines_by_page={1: []},
        )

    monkeypatch.setattr(pipeline_module, "extract_page_text_layout_result", fake_text_layout)
    monkeypatch.setattr(pipeline_module, "extract_images", lambda *args, **kwargs: ImageExtractionResult())
    monkeypatch.setattr(pipeline_module, "extract_tables", lambda *args, **kwargs: TableExtractionResult())
    monkeypatch.setattr(pipeline_module, "run_ocr", lambda *args, **kwargs: OcrResult())

    output_dir = tmp_path / "markdown-structure"
    result = run_conversion(Config(input_pdf=sample_pdf, output_dir=output_dir, repair_hyphenation=True))

    assert result.exit_code == EXIT_SUCCESS
    document = (output_dir / "document.md").read_text(encoding="utf-8")
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert "## 2.2 Heading" in document
    assert "interoperability" in document
    assert report["summary"]["heading_count"] == 1
    assert report["summary"]["list_item_count"] == 1
    assert report["summary"]["hyphenation_repair_count"] == 1


def test_pipeline_records_ocr_page_diagnostics(sample_pdf: Path, tmp_path: Path, monkeypatch) -> None:
    def fake_run_ocr(*args, **kwargs) -> OcrResult:  # noqa: ANN001
        return OcrResult(
            attempted_pages=[1],
            reasons_by_page={1: "force"},
            runtime_available=True,
        )

    monkeypatch.setattr(pipeline_module, "run_ocr", fake_run_ocr)
    monkeypatch.setattr(pipeline_module, "extract_images", lambda *args, **kwargs: ImageExtractionResult())
    monkeypatch.setattr(pipeline_module, "extract_tables", lambda *args, **kwargs: TableExtractionResult())

    output_dir = tmp_path / "ocr-diagnostics"
    result = run_conversion(Config(input_pdf=sample_pdf, output_dir=output_dir, pages="1", force_ocr=True))

    assert result.exit_code == EXIT_SUCCESS
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    page_result = report["page_results"][0]
    assert page_result["text_layer_char_count"] > 0
    assert page_result["ocr_attempted"] is True
    assert page_result["ocr_reason"] == "force"
    assert page_result["ocr_runtime_available"] is True


def test_pipeline_routes_image_only_scanned_pdf_through_ocr_without_correction(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pdf_path = tmp_path / "image-only.pdf"
    build_image_only_pdf(pdf_path)

    def fake_run_ocr(  # noqa: ANN001
        pdf_path_arg,
        selected_pages,
        existing_page_texts,
        force_ocr,
        ocr_lang,
        ocr_backend,
        worker_count=1,
    ) -> OcrResult:
        assert pdf_path_arg == pdf_path
        assert selected_pages == [1]
        assert existing_page_texts == {1: ""}
        assert force_ocr is False
        assert ocr_lang == "eng"
        assert ocr_backend == "tesseract"
        assert worker_count == 1
        return OcrResult(
            warnings=[
                WarningEntry(
                    code="OCR_CONFIDENCE_WARN",
                    message="warn",
                    page=1,
                    details={
                        "ocr_lang": "eng",
                        "ocr_confidence_mean": 72.0,
                        "ocr_confidence_median": 72.0,
                        "low_conf_token_ratio": 0.0,
                    },
                )
            ],
            page_texts={1: "teh SOURCE scann txt"},
            ocr_pages=[1],
            attempted_pages=[1],
            reasons_by_page={1: "empty_text_layer"},
            used_ocr=True,
            runtime_available=True,
            metrics_by_page={1: OcrMetrics(mean=72.0, median=72.0, low_conf_token_ratio=0.0)},
        )

    monkeypatch.setattr(pipeline_module, "run_ocr", fake_run_ocr)
    monkeypatch.setattr(pipeline_module, "extract_images", lambda *args, **kwargs: ImageExtractionResult())
    monkeypatch.setattr(pipeline_module, "extract_tables", lambda *args, **kwargs: TableExtractionResult())

    output_dir = tmp_path / "scanned-ocr"
    result = run_conversion(Config(input_pdf=pdf_path, output_dir=output_dir, pages="1"))

    assert result.exit_code == EXIT_PARTIAL
    document = (output_dir / "document.md").read_text(encoding="utf-8")
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    page_result = report["page_results"][0]
    assert "teh SOURCE scann txt" in document
    assert page_result["text_layer_char_count"] == 0
    assert page_result["ocr_attempted"] is True
    assert page_result["ocr_reason"] == "empty_text_layer"
    assert page_result["ocr_runtime_available"] is True
    assert page_result["used_ocr"] is True
    assert page_result["ocr_confidence_mean"] == 72.0
    assert report["warnings"][0]["code"] == "OCR_CONFIDENCE_WARN"
    assert report["summary"]["actionable_warning_count"] == 1
    assert report["summary"]["advisory_warning_count"] == 0
    assert report["summary"]["ocr_actionable_warning_count"] == 1
    assert report["summary"]["ocr_advisory_warning_count"] == 0
    assert report["summary"]["low_confidence_pages"] == [1]
    assert manifest["ocr_pages"] == [1]


def test_pipeline_passes_effective_page_workers_to_ocr(sample_pdf: Path, tmp_path: Path, monkeypatch) -> None:
    seen: dict[str, int] = {}

    def fake_run_ocr(*args, worker_count=1, **kwargs) -> OcrResult:  # noqa: ANN001
        seen["worker_count"] = worker_count
        return OcrResult()

    monkeypatch.setattr(pipeline_module, "run_ocr", fake_run_ocr)
    monkeypatch.setattr(pipeline_module, "extract_images", lambda *args, **kwargs: ImageExtractionResult())
    monkeypatch.setattr(pipeline_module, "extract_tables", lambda *args, **kwargs: TableExtractionResult())

    result = run_conversion(
        Config(
            input_pdf=sample_pdf,
            output_dir=tmp_path / "ocr-workers",
            force_ocr=True,
            page_workers=2,
        )
    )

    assert result.exit_code == EXIT_SUCCESS
    assert seen["worker_count"] == 2


def test_pipeline_records_empty_ocr_confidence_metrics_in_report(
    sample_pdf: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_run_ocr(*args, **kwargs) -> OcrResult:  # noqa: ANN001
        return OcrResult(
            warnings=[
                WarningEntry(
                    code="OCR_EMPTY_RESULT",
                    message="empty",
                    page=1,
                    details={
                        "ocr_lang": "eng",
                        "reason": "empty_result",
                        "ocr_confidence_mean": 0.0,
                        "ocr_confidence_median": 0.0,
                        "low_conf_token_ratio": 1.0,
                    },
                )
            ],
            attempted_pages=[1],
            reasons_by_page={1: "force"},
            runtime_available=True,
            metrics_by_page={1: OcrMetrics(mean=0.0, median=0.0, low_conf_token_ratio=1.0)},
        )

    monkeypatch.setattr(pipeline_module, "run_ocr", fake_run_ocr)
    monkeypatch.setattr(pipeline_module, "extract_images", lambda *args, **kwargs: ImageExtractionResult())
    monkeypatch.setattr(pipeline_module, "extract_tables", lambda *args, **kwargs: TableExtractionResult())

    output_dir = tmp_path / "empty-ocr"
    result = run_conversion(Config(input_pdf=sample_pdf, output_dir=output_dir, pages="1", force_ocr=True))

    assert result.exit_code == EXIT_PARTIAL
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    page_result = report["page_results"][0]
    assert page_result["used_ocr"] is False
    assert page_result["ocr_attempted"] is True
    assert page_result["ocr_confidence_mean"] == 0.0
    assert page_result["ocr_confidence_median"] == 0.0
    assert page_result["low_conf_token_ratio"] == 1.0
    assert report["summary"]["low_confidence_pages"] == [1]
    assert report["warnings"][0]["details"]["reason"] == "empty_result"
    assert report["summary"]["ocr_actionable_warning_count"] == 1
    assert report["summary"]["ocr_advisory_warning_count"] == 0


def test_empty_ocr_blank_page_warning_is_advisory_for_status() -> None:
    warning = WarningEntry(
        code="OCR_EMPTY_RESULT",
        message="empty",
        page=24,
        details={
            "force_ocr": False,
            "attempt_reason": "empty_text_layer",
            "existing_text_char_count": 0,
            "page_image_count": 0,
        },
    )

    status, exit_code = determine_conversion_status([warning], [])

    assert is_advisory_warning(warning) is True
    assert status.value == "success"
    assert exit_code == EXIT_SUCCESS


def test_warning_taxonomy_registry_drives_severity_and_exit_policy() -> None:
    table_fallback = WarningEntry(code=WarningCode.TABLE_COMPLEXITY_HTML_FALLBACK, message="fallback", page=1)
    ocr_warning = WarningEntry(code=WarningCode.OCR_CONFIDENCE_WARN, message="ocr", page=1)
    unknown_warning = WarningEntry(code="CUSTOM_WARNING", message="custom", page=1)

    table_spec = warning_code_spec(table_fallback.code)
    ocr_spec = warning_code_spec(ocr_warning.code)
    unknown_spec = warning_code_spec(unknown_warning.code)

    assert table_spec.domain == WarningDomain.TABLE
    assert table_spec.default_severity == WarningSeverity.ADVISORY
    assert table_spec.affects_exit_code is False
    assert ocr_spec.domain == WarningDomain.OCR
    assert is_advisory_warning(table_fallback) is True
    assert warning_affects_exit_code(table_fallback) is False
    assert warning_affects_exit_code(ocr_warning) is True
    assert unknown_spec.domain == WarningDomain.UNKNOWN
    assert warning_affects_exit_code(unknown_warning) is False


def test_technical_profile_missing_domain_warning_is_advisory_for_status() -> None:
    warning = WarningEntry(
        code=WarningCode.TECHNICAL_PROFILE_DOMAIN_ADAPTER_MISSING,
        message="missing domain",
        details={"rag_profile": "technical_spec_rag", "domain_adapter": "none"},
    )

    status, exit_code = determine_conversion_status([warning], [])

    assert is_advisory_warning(warning) is True
    assert status.value == "success"
    assert exit_code == EXIT_SUCCESS


def test_empty_ocr_scanned_page_warning_remains_actionable() -> None:
    warning = WarningEntry(
        code="OCR_EMPTY_RESULT",
        message="empty",
        page=1,
        details={
            "force_ocr": False,
            "attempt_reason": "empty_text_layer",
            "existing_text_char_count": 0,
            "page_image_count": 1,
        },
    )

    status, exit_code = determine_conversion_status([warning], [])

    assert is_advisory_warning(warning) is False
    assert status.value == "partial_success"
    assert exit_code == EXIT_PARTIAL


def test_actionable_low_quality_table_keeps_partial_status(sample_pdf: Path, tmp_path: Path, monkeypatch) -> None:
    def fake_extract_tables(*args, **kwargs) -> TableExtractionResult:
        return TableExtractionResult(
            table_quality=[
                {
                    "page": 1,
                    "table_index": 1,
                    "quality_score": 0.42,
                    "mode": "gfm",
                    "unresolved": True,
                    "reasons": [],
                }
            ],
            table_counts={"table_total": 1, "table_gfm_count": 1},
        )

    monkeypatch.setattr(pipeline_module, "run_ocr", lambda *args, **kwargs: OcrResult())
    monkeypatch.setattr(pipeline_module, "extract_tables", fake_extract_tables)
    monkeypatch.setattr(pipeline_module, "extract_images", lambda *args, **kwargs: ImageExtractionResult())

    output_dir = tmp_path / "actionable-low-quality-table"
    result = run_conversion(Config(input_pdf=sample_pdf, output_dir=output_dir, pages="1"))

    assert result.exit_code == EXIT_PARTIAL
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "partial_success"
    assert report["summary"]["table_low_quality_count"] == 1
    assert report["summary"]["table_actionable_low_quality_count"] == 1
    assert report["summary"]["table_advisory_low_quality_count"] == 0


def test_debug_table_quality_review_pack_records_low_quality_evidence(
    sample_pdf: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_extract_tables(*args, **kwargs) -> TableExtractionResult:
        return TableExtractionResult(
            rag_tables=[
                {
                    "page": 1,
                    "table_index": 1,
                    "source_mode": "html",
                    "headers": ["Bits", "Field", "Description"],
                    "bbox": [10.0, 20.0, 120.0, 80.0],
                    "quality_score": 0.42,
                    "records": [
                        {
                            "page": 1,
                            "table_index": 1,
                            "source_mode": "html",
                            "headers": ["Bits", "Field", "Description"],
                            "row_index": 1,
                            "cells": {
                                "Bits": "0",
                                "Field": "CAP",
                                "Description": "Controller capabilities",
                            },
                            "row_text": "Bits = 0 | Field = CAP | Description = Controller capabilities",
                            "bbox": [10.0, 20.0, 120.0, 80.0],
                            "quality_score": 0.42,
                        }
                    ],
                }
            ],
            table_quality=[
                {
                    "page": 1,
                    "table_index": 1,
                    "quality_score": 0.42,
                    "mode": "html",
                    "reasons": ["LOW_HEADER_CONFIDENCE"],
                    "rag_header_strategy": "fallback_low_confidence",
                    "header_confidence": 0.4,
                    "empty_cell_ratio": 0.5,
                }
            ],
            fallbacks=[
                {
                    "page": 1,
                    "table_index": 1,
                    "mode": "html",
                    "reasons": ["LOW_HEADER_CONFIDENCE"],
                }
            ],
            table_counts={"table_total": 1, "table_html_count": 1},
        )

    monkeypatch.setattr(pipeline_module, "run_ocr", lambda *args, **kwargs: OcrResult())
    monkeypatch.setattr(pipeline_module, "extract_tables", fake_extract_tables)
    monkeypatch.setattr(pipeline_module, "extract_images", lambda *args, **kwargs: ImageExtractionResult())

    output_dir = tmp_path / "table-quality-debug"
    result = run_conversion(Config(input_pdf=sample_pdf, output_dir=output_dir, pages="1", debug=True))

    assert result.exit_code == EXIT_SUCCESS
    pack = json.loads((output_dir / "debug" / "table-quality-review-pack.json").read_text(encoding="utf-8"))
    assert pack["low_quality_count"] == 1
    assert pack["triage_counts"] == {"actionable": 0, "advisory": 1}
    item = pack["items"][0]
    assert item["table_id"] == "page-0001-table-0001"
    assert item["row_count"] == 1
    assert item["technical_table_unit_count"] == 1
    assert item["sample_row_text_sha256"]
    assert "Controller capabilities" in item["sample_row_text_preview"]


def test_pipeline_records_ocr_confidence_matrix_in_report(sample_pdf: Path, tmp_path: Path, monkeypatch) -> None:
    def fake_run_ocr(*args, **kwargs) -> OcrResult:  # noqa: ANN001
        return OcrResult(
            warnings=[
                WarningEntry(
                    code="OCR_CONFIDENCE_WARN",
                    message="warn",
                    page=1,
                    details={
                        "ocr_confidence_mean": 72.0,
                        "ocr_confidence_median": 73.0,
                        "low_conf_token_ratio": 0.0,
                    },
                )
            ],
            page_texts={1: "raw OCR txt"},
            ocr_pages=[1],
            attempted_pages=[1],
            reasons_by_page={1: "force"},
            used_ocr=True,
            runtime_available=True,
            metrics_by_page={1: OcrMetrics(mean=72.0, median=73.0, low_conf_token_ratio=0.0)},
        )

    monkeypatch.setattr(pipeline_module, "run_ocr", fake_run_ocr)
    monkeypatch.setattr(pipeline_module, "extract_images", lambda *args, **kwargs: ImageExtractionResult())
    monkeypatch.setattr(pipeline_module, "extract_tables", lambda *args, **kwargs: TableExtractionResult())

    output_dir = tmp_path / "ocr-confidence"
    result = run_conversion(Config(input_pdf=sample_pdf, output_dir=output_dir, pages="1", force_ocr=True))

    assert result.exit_code == EXIT_PARTIAL
    document = (output_dir / "document.md").read_text(encoding="utf-8")
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    page_result = report["page_results"][0]
    assert "raw OCR txt" in document
    assert page_result["used_ocr"] is True
    assert page_result["ocr_confidence_mean"] == 72.0
    assert page_result["ocr_confidence_median"] == 73.0
    assert page_result["low_conf_token_ratio"] == 0.0
    assert report["summary"]["ocr_confidence_by_page"] == {
        "1": {
            "ocr_confidence_mean": 72.0,
            "ocr_confidence_median": 73.0,
            "low_conf_token_ratio": 0.0,
        }
    }
    assert report["summary"]["low_confidence_pages"] == [1]
