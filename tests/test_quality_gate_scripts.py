from __future__ import annotations

import json
import tomllib
import zipfile
from pathlib import Path
from types import SimpleNamespace

from scripts import benchmark_conversion
from scripts import benchmark_docling_comparison
from scripts import benchmark_gui_cli_parity
from scripts import check_ocr_runtime
from scripts import evaluate_figure_descriptions
from scripts import inspect_wheel_contract
from scripts import probe_ocr_backends
from scripts import run_preset_eval
from scripts import run_gui_cli_parity
from scripts import run_corpus_eval
from scripts import run_latest_ocp_datacenter_nvme_ssd_benchmark
from scripts import run_latest_nvme_base_benchmark
from scripts import run_latest_nvme_command_set_eval
from scripts import run_latest_ssd_security_spec_benchmark
from scripts import run_release_gates
from fixtures.pdf_builder import (
    build_caliptra_security_slice_pdf,
    build_nvme_base_slice_pdf,
    build_nvme_command_set_slice_pdf,
    build_ocp_datacenter_nvme_ssd_slice_pdf,
    build_spdm_security_slice_pdf,
)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def test_pyproject_declares_modern_tooling_and_typed_package_contract() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    dev_dependencies = pyproject["project"]["optional-dependencies"]["dev"]
    assert "ruff>=0.8.0" in dev_dependencies
    assert "build>=1.2.0" in dev_dependencies
    assert "pip-audit>=2.7.0" in dev_dependencies
    assert "wheel>=0.43.0" in dev_dependencies
    assert pyproject["tool"]["ruff"]["target-version"] == "py311"
    assert pyproject["tool"]["ruff"]["line-length"] == 120
    assert pyproject["tool"]["ruff"]["lint"]["select"] == ["E9", "F63", "F7", "F82", "SIM"]
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["include"] == ["pdf2md*"]
    assert pyproject["tool"]["setuptools"]["package-data"]["pdf2md"] == ["py.typed"]
    assert Path("pdf2md/py.typed").is_file()


def test_corpus_quality_gate_records_baseline_and_threshold_regressions(tmp_path: Path) -> None:
    payload = {
        "summary": {
            "total_documents": 4,
            "success_count": 2,
            "partial_success_count": 2,
            "failed_count": 0,
            "skipped_count": 0,
            "table_fallback_reason_counts": {"complex_table": 2},
            "total_suppressed_lines": 5,
            "table_low_quality_count": 2,
            "table_total": 4,
            "pages_per_second_min": 1.1,
            "pages_per_second_mean": 2.0,
            "pdf_open_count": 8,
            "text_line_extract_count": 20,
        }
    }
    baseline = {
        "summary": {
            "success_count": 3,
            "partial_success_count": 1,
            "failed_count": 0,
            "skipped_count": 0,
            "table_fallback_reason_counts": {"complex_table": 1},
            "total_suppressed_lines": 4,
            "table_low_quality_count": 1,
            "pages_per_second_min": 1.5,
            "pages_per_second_mean": 2.2,
            "pdf_open_count": 6,
            "text_line_extract_count": 18,
        }
    }

    result = run_corpus_eval.apply_quality_gate(
        payload,
        baseline_report=baseline,
        baseline_report_path=tmp_path / "baseline.json",
        max_partial_rate=0.25,
        max_low_quality_table_rate=0.25,
        min_pages_per_second=1.2,
    )

    metrics = {item["metric"] for item in result["regressions"]}
    assert result["passed_quality_gate"] is False
    assert result["baseline_report"].endswith("baseline.json")
    assert result["summary"]["partial_success_rate"] == 0.5
    assert result["summary"]["low_quality_table_rate"] == 0.5
    assert "summary.success_count" in metrics
    assert "summary.table_fallback_reason_counts.complex_table" in metrics
    assert "summary.partial_success_rate" in metrics
    assert "summary.pages_per_second_min" in metrics


def test_corpus_quality_gate_passes_without_baseline_or_threshold_failures() -> None:
    payload = {
        "summary": {
            "total_documents": 1,
            "success_count": 1,
            "partial_success_count": 0,
            "table_low_quality_count": 0,
            "table_total": 0,
            "pages_per_second_min": 3.0,
        }
    }

    result = run_corpus_eval.apply_quality_gate(payload, min_pages_per_second=2.0)

    assert result["passed_quality_gate"] is True
    assert result["baseline_report"] is None
    assert result["regressions"] == []


def test_benchmark_performance_gate_records_page_count_regressions(tmp_path: Path) -> None:
    payload = {
        "runs": [
            {
                "page_count": 10,
                "elapsed_ms": 1300,
                "total_duration_ms": 1300,
                "peak_memory_bytes": 1500,
                "stage_durations_ms": {"text": 500},
                "pages_per_second": 7.5,
                "pdf_open_count": 3,
                "text_line_extract_count": 25,
            }
        ]
    }
    baseline = {
        "runs": [
            {
                "page_count": 10,
                "total_duration_ms": 1000,
                "peak_memory_bytes": 1000,
                "stage_durations_ms": {"text": 300},
                "pages_per_second": 10.0,
                "pdf_open_count": 2,
                "text_line_extract_count": 20,
            }
        ]
    }

    result = benchmark_conversion.apply_performance_gate(
        payload,
        baseline_report=baseline,
        baseline_report_path=tmp_path / "benchmark_report.json",
        max_duration_regression=0.2,
        max_memory_regression=0.2,
        min_pages_per_second=8.0,
    )

    metrics = {item["metric"] for item in result["regressions"]}
    assert result["passed_performance_gate"] is False
    assert result["baseline_report"].endswith("benchmark_report.json")
    assert "total_duration_ms" in metrics
    assert "peak_memory_bytes" in metrics
    assert "stage_durations_ms.text" in metrics
    assert "pages_per_second" in metrics
    assert "pdf_open_count" in metrics
    assert "text_line_extract_count" in metrics


def test_benchmark_performance_gate_records_worker_equivalence_failures() -> None:
    payload = {
        "runs": [],
        "worker_equivalence": {
            "mismatches": [
                {
                    "page_count": 10,
                    "baseline_page_workers": 1,
                    "page_workers": 2,
                    "different_artifacts": ["tables_rag.jsonl"],
                }
            ],
            "passed": False,
        },
    }

    result = benchmark_conversion.apply_performance_gate(payload)

    assert result["passed_performance_gate"] is False
    assert result["regressions"][0]["type"] == "worker_equivalence_failure"
    assert result["regressions"][0]["metric"] == "worker_output_hashes"
    assert result["regressions"][0]["different_artifacts"] == ["tables_rag.jsonl"]


def test_docling_comparison_writes_sanitized_advisory_pack_when_docling_is_missing(
    monkeypatch,  # noqa: ANN001
    sample_pdf: Path,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(benchmark_docling_comparison, "_module_available", lambda module_name: False)

    report = benchmark_docling_comparison.run_docling_comparison(
        input_pdf=sample_pdf,
        output_dir=tmp_path / "docling-comparison",
        document_label="doc-0001",
    )

    output_dir = tmp_path / "docling-comparison"
    comparison = benchmark_docling_comparison._read_json(  # noqa: SLF001
        output_dir / benchmark_docling_comparison.COMPARISON_FILENAME
    )
    scorecard = (output_dir / benchmark_docling_comparison.SCORECARD_FILENAME).read_text(encoding="utf-8")

    assert (output_dir / benchmark_docling_comparison.REPORT_FILENAME).is_file()
    assert report["summary"]["current_tool_status"] in {"success", "partial_success"}
    assert report["summary"]["docling_status"] == "skipped"
    assert report["summary"]["docling_available"] is False
    assert report["summary"]["warning_count"] == 1
    assert report["findings"][0]["code"] == "docling_not_installed"
    assert report["raw_content_included"] is False
    assert report["image_bytes_included"] is False
    assert report["customer_paths_included"] is False
    assert report["runs"][0]["output_dir"] == "current_tool"
    assert report["runs"][1]["output_dir"] is None
    assert "sample.pdf" not in json.dumps(report, ensure_ascii=False, sort_keys=True)
    assert comparison["summary"]["current_artifact_count"] >= 3
    assert comparison["summary"]["docling_artifact_count"] == 0
    assert comparison["raw_content_included"] is False
    assert comparison["image_bytes_included"] is False
    assert comparison["customer_paths_included"] is False
    assert "# Docling Benchmark Scorecard" in scorecard
    assert "docling_not_installed" in scorecard


def test_docling_comparison_passes_figure_semantics_options_to_current_tool(
    monkeypatch,  # noqa: ANN001
    sample_pdf: Path,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(benchmark_docling_comparison, "_module_available", lambda module_name: False)

    output_dir = tmp_path / "docling-figure-semantics"
    report = benchmark_docling_comparison.run_docling_comparison(
        input_pdf=sample_pdf,
        output_dir=output_dir,
        document_label="doc-figure-semantics",
        figure_region_ocr=True,
        rag_generated_figure_descriptions=True,
        figure_description_backend="docling",
        figure_structure_extraction=True,
    )

    manifest = json.loads((output_dir / "current_tool" / "manifest.json").read_text(encoding="utf-8"))
    current_metrics = report["runs"][0]["metrics"]

    assert manifest["options"]["figure_region_ocr"] is True
    assert manifest["options"]["rag_generated_figure_descriptions"] is True
    assert manifest["options"]["figure_description_backend"] == "docling"
    assert manifest["options"]["figure_structure_extraction"] is True
    assert "figure_region_ocr_attempted_count" in current_metrics
    assert "figure_description_chunk_record_count" in current_metrics
    assert "figure_structure_chunk_record_count" in current_metrics


def test_docling_layout_comparison_collects_sanitized_counts(
    monkeypatch,  # noqa: ANN001
    sample_pdf: Path,
    tmp_path: Path,
) -> None:
    class FakeDocument:
        def export_to_markdown(self) -> str:
            return "# Synthetic Docling Export\n"

        def export_to_dict(self) -> dict:
            return {
                "pages": [
                    {
                        "tables": [{"cells": []}],
                        "pictures": [{"annotations": []}],
                        "text_blocks": [{"kind": "paragraph"}],
                    }
                ],
                "body": {"children": []},
            }

    class FakeConverter:
        def convert(self, input_pdf: str):  # noqa: ANN001
            return SimpleNamespace(document=FakeDocument())

    original_import_module = benchmark_docling_comparison.importlib.import_module

    def fake_import_module(module_name: str):  # noqa: ANN001
        if module_name == "docling.document_converter":
            return SimpleNamespace(DocumentConverter=FakeConverter)
        return original_import_module(module_name)

    monkeypatch.setattr(benchmark_docling_comparison, "_module_available", lambda module_name: module_name == "docling")
    monkeypatch.setattr(benchmark_docling_comparison.importlib, "import_module", fake_import_module)

    output_dir = tmp_path / "docling-layout-comparison"
    report = benchmark_docling_comparison.run_docling_comparison(
        input_pdf=sample_pdf,
        output_dir=output_dir,
        document_label="docling-layout",
        layout_comparison_mode="summary",
    )
    comparison = benchmark_docling_comparison._read_json(  # noqa: SLF001
        output_dir / benchmark_docling_comparison.COMPARISON_FILENAME
    )
    current_metrics = next(run["metrics"] for run in report["runs"] if run["tool"] == "pdf2md")
    docling_metrics = next(run["metrics"] for run in report["runs"] if run["tool"] == "docling")
    deltas = {item["metric"]: item for item in comparison["metric_deltas"]}

    assert report["summary"]["layout_comparison_mode"] == "summary"
    assert report["summary"]["layout_comparison_enabled"] is True
    assert comparison["summary"]["layout_comparison_mode"] == "summary"
    assert comparison["summary"]["layout_comparable"] is True
    assert current_metrics["layout_comparison_mode"] == "summary"
    assert "layout_table_candidate_count" in current_metrics
    assert docling_metrics["layout_comparison_mode"] == "summary"
    assert docling_metrics["layout_table_candidate_count"] >= 1
    assert docling_metrics["layout_figure_candidate_count"] >= 1
    assert docling_metrics["layout_page_candidate_count"] >= 1
    assert "layout_table_candidate_count" in deltas
    assert "layout_figure_candidate_count" in deltas
    assert report["raw_content_included"] is False
    assert comparison["raw_content_included"] is False
    assert "sample.pdf" not in json.dumps(report, ensure_ascii=False, sort_keys=True)


def test_latest_nvme_command_set_eval_writes_sanitized_scorecard(
    monkeypatch,  # noqa: ANN001
    sample_pdf: Path,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(benchmark_docling_comparison, "_module_available", lambda module_name: False)

    output_dir = tmp_path / "latest-nvme-command-set"
    report = run_latest_nvme_command_set_eval.run_latest_nvme_command_set_eval(
        input_pdf=sample_pdf,
        output_dir=output_dir,
        pages="1",
        figure_semantics_mode="visual",
    )
    scorecard = (output_dir / run_latest_nvme_command_set_eval.SCORECARD_FILENAME).read_text(encoding="utf-8")
    manifest = json.loads((output_dir / "current_tool" / "manifest.json").read_text(encoding="utf-8"))

    assert (output_dir / benchmark_docling_comparison.REPORT_FILENAME).is_file()
    assert (output_dir / benchmark_docling_comparison.COMPARISON_FILENAME).is_file()
    assert report["summary"]["current_tool_status"] in {"success", "partial_success"}
    assert "NVM Express NVM Command Set Specification Revision 1.2" in scorecard
    assert "technical_spec_rag + domain_adapter=nvme + image_mode=placeholder" in scorecard
    assert "Raw PDF text, raw Markdown body, image bytes, and customer paths are not embedded" in scorecard
    assert manifest["options"]["domain_adapter"] == "nvme"
    assert manifest["options"]["rag_figure_text_chunks"] is True
    assert manifest["options"]["rag_generated_figure_descriptions"] is True


def test_latest_nvme_base_benchmark_writes_sanitized_summary(tmp_path: Path) -> None:
    input_pdf = tmp_path / "NVM-Express-Base-Synthetic.pdf"
    build_nvme_base_slice_pdf(input_pdf)
    output_dir = tmp_path / "latest-nvme-base-benchmark"

    report = run_latest_nvme_base_benchmark.run_latest_nvme_spec_benchmark(
        run_latest_nvme_base_benchmark.LatestNvmeSpecBenchmarkConfig(
            input_pdf=input_pdf,
            output_dir=output_dir,
            spec_document_type=run_latest_nvme_base_benchmark.BASE_SPEC_DOCUMENT,
            mode=run_latest_nvme_base_benchmark.FAST_SMOKE_MODE,
            source_url=run_latest_nvme_base_benchmark.OFFICIAL_SOURCE_URL,
        )
    )
    persisted = json.loads(
        (output_dir / run_latest_nvme_base_benchmark.REPORT_FILENAME).read_text(encoding="utf-8")
    )
    scorecard = (output_dir / run_latest_nvme_base_benchmark.SCORECARD_FILENAME).read_text(encoding="utf-8")
    counts = report["summary_counts"]

    assert persisted == report
    assert report["purpose"] == "latest_nvme_spec_benchmark"
    assert report["spec_document_type"] == "base"
    assert report["source_url"] == "https://nvmexpress.org/specifications/"
    assert len(report["source_sha256"]) == 64
    assert report["mode"] == "fast_smoke"
    assert report["expected_spec_title"] == "NVM Express Base Specification"
    assert report["option_matrix"]["pages"] == "1-5"
    assert report["option_matrix"]["spec_document_type"] == "base"
    assert report["option_matrix"]["command_set_query_eval"]["enabled"] is False
    assert report["option_matrix"]["domain_adapter"] == "nvme"
    assert report["option_matrix"]["image_mode"] == "placeholder"
    assert report["option_matrix"]["visual_mode"] is False
    assert report["option_matrix"]["rag_figure_text_chunks"] is False
    assert counts["page_count"] == 5
    assert counts["retrieval_chunk_count"] > 0
    assert counts["requirement_count"] > 0
    assert counts["traceability_record_count"] >= 3
    assert counts["technical_table_unit_count"] >= 4
    assert counts["domain_unit_count"] >= 4
    assert counts["figure_text_chunk_record_count"] == 0
    assert counts["figure_description_chunk_record_count"] == 0
    assert counts["figure_structure_chunk_record_count"] == 0
    assert counts["contract_validation_status"] == "passed"
    assert counts["contract_validation_passed"] is True
    assert counts["command_set_eval_status"] == "not_applicable"
    assert counts["command_set_eval_passed"] is True
    assert counts["visual_eval_status"] == "not_applicable"
    assert counts["visual_eval_passed"] is True
    assert report["command_set_eval"]["queries_included"] is False
    assert report["command_set_eval"]["retrieved_text_included"] is False
    assert report["visual_eval"]["queries_included"] is False
    assert report["visual_eval"]["retrieved_text_included"] is False
    assert counts["sidecar_file_sizes"]["retrieval_chunks_rag.jsonl"] > 0
    assert report["raw_content_included"] is False
    assert report["image_bytes_included"] is False
    assert report["local_input_paths_included"] is False
    assert "Raw PDF text, raw Markdown body, generated queries, retrieved text, image bytes" in scorecard
    assert "| figure_rag_record_count |" in scorecard

    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    assert str(input_pdf) not in serialized
    assert "The controller shall report synthetic health status when requested." not in serialized
    assert "Command = Identify" not in serialized


def test_latest_nvme_command_spec_benchmark_uses_same_contract(tmp_path: Path) -> None:
    input_pdf = tmp_path / "NVM-Express-NVM-Command-Set-Synthetic.pdf"
    build_nvme_command_set_slice_pdf(input_pdf)
    output_dir = tmp_path / "latest-nvme-command-spec-benchmark"

    report = run_latest_nvme_base_benchmark.run_latest_nvme_spec_benchmark(
        run_latest_nvme_base_benchmark.LatestNvmeSpecBenchmarkConfig(
            input_pdf=input_pdf,
            output_dir=output_dir,
            spec_document_type=run_latest_nvme_base_benchmark.NVM_COMMAND_SET_SPEC_DOCUMENT,
            mode=run_latest_nvme_base_benchmark.FAST_SMOKE_MODE,
        )
    )
    counts = report["summary_counts"]
    scorecard = (output_dir / run_latest_nvme_base_benchmark.SCORECARD_FILENAME).read_text(encoding="utf-8")

    assert report["spec_document_type"] == "nvm_command_set"
    assert report["expected_spec_title"] == "NVM Express NVM Command Set Specification"
    assert report["expected_revision"] == "1.2"
    assert report["source_url"].endswith("NVM-Express-NVM-Command-Set-Specification-Revision-1.2-2025.08.01-Ratified.pdf")
    assert report["option_matrix"]["domain_adapter"] == "nvme"
    assert report["option_matrix"]["rag_profile"] == "technical_spec_rag"
    assert report["option_matrix"]["visual_mode"] is False
    assert report["option_matrix"]["command_set_query_eval"]["enabled"] is True
    assert counts["retrieval_chunk_count"] > 0
    assert counts["technical_table_unit_count"] >= 4
    assert counts["domain_unit_count"] >= 4
    assert counts["contract_validation_passed"] is True
    assert counts["command_set_eval_status"] == "passed"
    assert counts["command_set_eval_passed"] is True
    assert counts["command_set_eval_query_count"] == 4
    assert counts["command_set_eval_expected_source_coverage"] == 1.0
    assert report["command_set_eval"]["status"] == "passed"
    assert report["command_set_eval"]["profile"] == "nvme_command_set_p2_retrieval"
    assert report["command_set_eval"]["query_count"] == 4
    assert report["command_set_eval"]["missing_unit_types"] == []
    assert report["command_set_eval"]["covered_unit_types"] == [
        "command_opcode",
        "command_dword_field",
        "command_pointer_field",
        "status_code",
    ]
    assert report["command_set_eval"]["metrics"]["hit_at_k"] == 1.0
    assert report["command_set_eval"]["metrics"]["expected_source_coverage"] == 1.0
    assert report["command_set_eval"]["metrics"]["table_field_coverage"] == 1.0
    assert report["command_set_eval"]["raw_content_included"] is False
    assert report["command_set_eval"]["queries_included"] is False
    assert report["command_set_eval"]["retrieved_text_included"] is False
    assert "| command_set_eval_status | passed |" in scorecard
    assert "| command_set_eval_expected_source_coverage | 1.0 |" in scorecard

    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    assert str(input_pdf) not in serialized
    assert "The controller shall report synthetic health status when requested." not in serialized
    assert "The controller shall process a synthetic read command request." not in serialized
    assert "Command Dword = CDW10" not in serialized
    assert "Metadata Pointer = MPTR" not in serialized


def test_latest_ocp_datacenter_nvme_ssd_benchmark_writes_sanitized_summary(tmp_path: Path) -> None:
    input_pdf = tmp_path / "OCP-Datacenter-NVMe-SSD-Synthetic.pdf"
    build_ocp_datacenter_nvme_ssd_slice_pdf(input_pdf)
    output_dir = tmp_path / "latest-ocp-datacenter-nvme-ssd-benchmark"

    report = run_latest_ocp_datacenter_nvme_ssd_benchmark.run_latest_ocp_datacenter_nvme_ssd_benchmark(
        run_latest_ocp_datacenter_nvme_ssd_benchmark.LatestOcpDatacenterNvmeSsdBenchmarkConfig(
            input_pdf=input_pdf,
            output_dir=output_dir,
            mode=run_latest_ocp_datacenter_nvme_ssd_benchmark.FAST_SMOKE_MODE,
        )
    )
    persisted = json.loads(
        (output_dir / run_latest_ocp_datacenter_nvme_ssd_benchmark.REPORT_FILENAME).read_text(encoding="utf-8")
    )
    scorecard = (
        output_dir / run_latest_ocp_datacenter_nvme_ssd_benchmark.SCORECARD_FILENAME
    ).read_text(encoding="utf-8")
    counts = report["summary_counts"]

    assert persisted == report
    assert report["purpose"] == "latest_ocp_datacenter_nvme_ssd_benchmark"
    assert report["expected_spec_title"] == "Datacenter NVMe SSD Specification"
    assert report["expected_version"] == "2.7"
    assert report["expected_date_marker"] == "01082026"
    assert report["source_url"] == run_latest_ocp_datacenter_nvme_ssd_benchmark.OFFICIAL_SOURCE_URL
    assert len(report["source_sha256"]) == 64
    assert report["option_matrix"]["pages"] == "1-5"
    assert report["option_matrix"]["domain_adapter"] == "ocp"
    assert report["option_matrix"]["rag_profile"] == "technical_spec_rag"
    assert report["option_matrix"]["image_mode"] == "placeholder"
    assert report["option_matrix"]["visual_mode"] is False
    assert report["option_matrix"]["rag_figure_text_chunks"] is False
    assert report["option_matrix"]["contract_validator"]["ssd_agent_spec_type"] == "OCP"
    assert report["option_matrix"]["ocp_query_eval"]["enabled"] is True
    assert report["option_matrix"]["ocp_query_eval"]["profile"] == "ocp_datacenter_nvme_ssd_p2_retrieval"
    assert counts["page_count"] == 5
    assert counts["retrieval_chunk_count"] > 0
    assert counts["traceability_record_count"] >= 6
    assert counts["technical_table_unit_count"] >= 6
    assert counts["domain_unit_count"] >= 6
    assert counts["ocp_requirement_unit_count"] >= 6
    assert counts["figure_text_chunk_record_count"] == 0
    assert counts["figure_description_chunk_record_count"] == 0
    assert counts["figure_structure_chunk_record_count"] == 0
    assert counts["contract_validation_status"] == "passed"
    assert counts["contract_validation_passed"] is True
    assert counts["ocp_eval_status"] == "passed"
    assert counts["ocp_eval_passed"] is True
    assert counts["visual_eval_status"] == "not_applicable"
    assert counts["visual_eval_passed"] is True
    assert counts["ocp_eval_query_count"] == 6
    assert counts["ocp_eval_expected_source_coverage"] == 1.0
    assert counts["ocp_eval_hit_at_k"] == 1.0
    assert counts["ocp_eval_table_field_coverage"] == 1.0
    assert report["ocp_eval"]["status"] == "passed"
    assert report["ocp_eval"]["missing_buckets"] == []
    assert report["ocp_eval"]["queries_included"] is False
    assert report["ocp_eval"]["retrieved_text_included"] is False
    assert counts["sidecar_file_sizes"]["domain_units_rag.jsonl"] > 0
    assert report["raw_content_included"] is False
    assert report["image_bytes_included"] is False
    assert report["local_input_paths_included"] is False
    assert "Raw PDF text, raw Markdown body, generated queries, retrieved text, image bytes" in scorecard
    assert "| ocp_requirement_unit_count |" in scorecard
    assert "| ocp_eval_status | passed |" in scorecard

    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    assert str(input_pdf) not in serialized
    assert "SSD shall support Write Zeroes command" not in serialized
    assert "Requirement ID = NVMe-IO-6" not in serialized
    assert "log_page_requirement NVMe-IO-6" not in serialized


def test_latest_ssd_security_spec_benchmark_writes_sanitized_spdm_summary(tmp_path: Path) -> None:
    input_pdf = tmp_path / "DMTF-SPDM-Synthetic.pdf"
    build_spdm_security_slice_pdf(input_pdf)
    output_dir = tmp_path / "latest-ssd-security-spdm-benchmark"

    report = run_latest_ssd_security_spec_benchmark.run_latest_ssd_security_spec_benchmark(
        run_latest_ssd_security_spec_benchmark.LatestSsdSecuritySpecBenchmarkConfig(
            input_pdf=input_pdf,
            output_dir=output_dir,
            spec_document_type=run_latest_ssd_security_spec_benchmark.SPDM_DOCUMENT,
            mode=run_latest_ssd_security_spec_benchmark.FAST_SMOKE_MODE,
            pages="1-2",
        )
    )
    persisted = json.loads(
        (output_dir / run_latest_ssd_security_spec_benchmark.REPORT_FILENAME).read_text(encoding="utf-8")
    )
    scorecard = (output_dir / run_latest_ssd_security_spec_benchmark.SCORECARD_FILENAME).read_text(encoding="utf-8")
    counts = report["summary_counts"]

    assert persisted == report
    assert report["purpose"] == "latest_ssd_security_spec_benchmark"
    assert report["spec_document_type"] == "spdm"
    assert report["latest_spec_set"] == "DMTF SPDM 1.4.0"
    assert report["latest_release_date"] == "2025-05-25"
    assert report["expected_spec_title"] == "Security Protocol and Data Model (SPDM) Specification"
    assert report["expected_revision"] == "1.4.0"
    assert report["source_url"] == "https://www.dmtf.org/standards/spdm"
    assert len(report["source_sha256"]) == 64
    assert report["option_matrix"]["pages"] == "1-2"
    assert report["option_matrix"]["domain_adapter"] == "spdm"
    assert report["option_matrix"]["contract_validator"]["ssd_agent_spec_type"] == "SPDM"
    assert "spdm_message" in report["option_matrix"]["security_unit_taxonomy"]
    assert report["option_matrix"]["image_mode"] == "placeholder"
    assert counts["page_count"] == 2
    assert counts["retrieval_chunk_count"] > 0
    assert counts["technical_table_unit_count"] >= 4
    assert counts["domain_unit_count"] >= 4
    assert counts["security_domain_unit_counts"]["spdm_message"] >= 2
    assert counts["security_domain_unit_counts"]["spdm_algorithm"] >= 2
    assert counts["contract_validation_status"] == "passed"
    assert counts["contract_validation_passed"] is True
    assert report["raw_content_included"] is False
    assert report["image_bytes_included"] is False
    assert report["local_input_paths_included"] is False
    assert "Raw PDF text, raw Markdown body, retrieved text" in scorecard
    assert "| spdm_message |" in scorecard

    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    assert str(input_pdf) not in serialized
    assert "GET_MEASUREMENTS" not in serialized
    assert "Requester shall retrieve measurement blocks." not in serialized


def test_latest_ssd_security_spec_benchmark_writes_sanitized_caliptra_summary(tmp_path: Path) -> None:
    input_pdf = tmp_path / "Caliptra-Synthetic.pdf"
    build_caliptra_security_slice_pdf(input_pdf)
    output_dir = tmp_path / "latest-ssd-security-caliptra-benchmark"

    report = run_latest_ssd_security_spec_benchmark.run_latest_ssd_security_spec_benchmark(
        run_latest_ssd_security_spec_benchmark.LatestSsdSecuritySpecBenchmarkConfig(
            input_pdf=input_pdf,
            output_dir=output_dir,
            spec_document_type=run_latest_ssd_security_spec_benchmark.CALIPTRA_DOCUMENT,
            mode=run_latest_ssd_security_spec_benchmark.FAST_SMOKE_MODE,
            pages="1-2",
        )
    )
    scorecard = (output_dir / run_latest_ssd_security_spec_benchmark.SCORECARD_FILENAME).read_text(encoding="utf-8")
    counts = report["summary_counts"]

    assert report["spec_document_type"] == "caliptra"
    assert report["latest_spec_set"] == "Caliptra 2.1"
    assert report["expected_revision"] == "2.1"
    assert report["source_url"] == "https://spec.caliptra.io/"
    assert report["option_matrix"]["domain_adapter"] == "caliptra"
    assert report["option_matrix"]["contract_validator"]["ssd_agent_spec_type"] == "Caliptra"
    assert "caliptra_asset" in report["option_matrix"]["security_unit_taxonomy"]
    assert counts["security_domain_unit_counts"]["caliptra_asset"] >= 2
    assert counts["security_domain_unit_counts"]["caliptra_mailbox_command"] >= 2
    assert counts["contract_validation_status"] == "passed"
    assert counts["contract_validation_passed"] is True
    assert "| caliptra_asset |" in scorecard
    assert report["raw_content_included"] is False
    assert report["image_bytes_included"] is False
    assert report["local_input_paths_included"] is False

    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    assert str(input_pdf) not in serialized
    assert "GET_SYNTHETIC_MEASUREMENT" not in serialized
    assert "Synthetic device identity seed" not in serialized


def test_latest_ocp_datacenter_nvme_ssd_benchmark_distinguishes_full_and_smoke_modes() -> None:
    full = run_latest_ocp_datacenter_nvme_ssd_benchmark.build_option_matrix(
        mode=run_latest_ocp_datacenter_nvme_ssd_benchmark.FULL_PRECISION_MODE,
        pages=None,
        page_workers=2,
    )
    smoke = run_latest_ocp_datacenter_nvme_ssd_benchmark.build_option_matrix(
        mode=run_latest_ocp_datacenter_nvme_ssd_benchmark.FAST_SMOKE_MODE,
        pages=None,
        page_workers=1,
    )

    assert full["pages"] is None
    assert full["image_mode"] == "referenced"
    assert full["visual_mode"] is False
    assert full["rag_profile"] == "technical_spec_rag"
    assert full["rag_figure_text_chunks"] is False
    assert full["page_workers"] == 2
    assert full["domain_adapter"] == "ocp"
    assert full["ocp_query_eval"]["enabled"] is True
    assert full["ocp_query_eval"]["required_buckets"] == [
        "requirement",
        "log_page_requirement",
        "feature_requirement",
        "telemetry_requirement",
        "security_requirement",
        "form_factor_or_thermal_requirement",
    ]
    assert smoke["pages"] == "1-5"
    assert smoke["image_mode"] == "placeholder"
    assert smoke["contract_validator"]["ssd_agent_spec_type"] == "OCP"

    visual = run_latest_ocp_datacenter_nvme_ssd_benchmark.build_option_matrix(
        mode=run_latest_ocp_datacenter_nvme_ssd_benchmark.FULL_PRECISION_MODE,
        pages=None,
        page_workers=1,
        visual_mode=True,
    )
    assert visual["visual_mode"] is True
    assert visual["rag_profile"] == "technical_spec_rag_visual"
    assert visual["image_mode"] == "referenced"
    assert visual["rag_figure_text_chunks"] is True
    assert visual["figure_region_ocr"] is True
    assert visual["rag_generated_figure_descriptions"] is True
    assert visual["figure_structure_extraction"] is True


def test_latest_ssd_security_spec_benchmark_distinguishes_spec_families() -> None:
    spdm = run_latest_ssd_security_spec_benchmark.build_option_matrix(
        mode=run_latest_ssd_security_spec_benchmark.FULL_PRECISION_MODE,
        pages=None,
        page_workers=1,
        spec_document_type=run_latest_ssd_security_spec_benchmark.SPDM_STORAGE_BINDING_DOCUMENT,
    )
    tcg = run_latest_ssd_security_spec_benchmark.build_option_matrix(
        mode=run_latest_ssd_security_spec_benchmark.FAST_SMOKE_MODE,
        pages=None,
        page_workers=2,
        spec_document_type=run_latest_ssd_security_spec_benchmark.TCG_STORAGE_DOCUMENT,
    )
    pcie = run_latest_ssd_security_spec_benchmark.build_option_matrix(
        mode=run_latest_ssd_security_spec_benchmark.FAST_SMOKE_MODE,
        pages="2",
        page_workers=1,
        spec_document_type=run_latest_ssd_security_spec_benchmark.PCIE_BASE_DOCUMENT,
        visual_mode=True,
    )
    caliptra = run_latest_ssd_security_spec_benchmark.build_option_matrix(
        mode=run_latest_ssd_security_spec_benchmark.FAST_SMOKE_MODE,
        pages=None,
        page_workers=1,
        spec_document_type=run_latest_ssd_security_spec_benchmark.CALIPTRA_DOCUMENT,
    )

    assert spdm["pages"] is None
    assert spdm["domain_adapter"] == "spdm"
    assert spdm["contract_validator"]["ssd_agent_spec_type"] == "SPDM"
    assert "spdm_certificate" in spdm["security_unit_taxonomy"]
    assert tcg["pages"] == "1-3"
    assert tcg["page_workers"] == 2
    assert tcg["domain_adapter"] == "tcg"
    assert tcg["contract_validator"]["ssd_agent_spec_type"] == "TCG"
    assert "security_method" in tcg["security_unit_taxonomy"]
    assert pcie["pages"] == "2"
    assert pcie["domain_adapter"] == "pcie"
    assert pcie["rag_profile"] == "technical_spec_rag_visual"
    assert pcie["contract_validator"]["ssd_agent_spec_type"] == "PCIe"
    assert caliptra["pages"] == "1-3"
    assert caliptra["domain_adapter"] == "caliptra"
    assert caliptra["contract_validator"]["ssd_agent_spec_type"] == "Caliptra"
    assert "caliptra_rot_service" in caliptra["security_unit_taxonomy"]


def test_latest_nvme_base_benchmark_distinguishes_full_and_smoke_modes() -> None:
    full = run_latest_nvme_base_benchmark.build_option_matrix(
        mode=run_latest_nvme_base_benchmark.FULL_PRECISION_MODE,
        pages=None,
        page_workers=1,
        spec_document_type=run_latest_nvme_base_benchmark.BASE_SPEC_DOCUMENT,
    )
    smoke = run_latest_nvme_base_benchmark.build_option_matrix(
        mode=run_latest_nvme_base_benchmark.FAST_SMOKE_MODE,
        pages=None,
        page_workers=1,
        spec_document_type=run_latest_nvme_base_benchmark.NVM_COMMAND_SET_SPEC_DOCUMENT,
    )

    assert full["pages"] is None
    assert full["image_mode"] == "referenced"
    assert full["visual_mode"] is False
    assert full["rag_profile"] == "technical_spec_rag"
    assert full["rag_figure_text_chunks"] is False
    assert full["spec_document_type"] == "base"
    assert full["command_set_query_eval"]["enabled"] is False
    assert smoke["pages"] == "1-5"
    assert smoke["image_mode"] == "placeholder"
    assert smoke["spec_document_type"] == "nvm_command_set"
    assert smoke["command_set_query_eval"]["enabled"] is True
    assert smoke["command_set_query_eval"]["required_unit_types"] == [
        "command_opcode",
        "command_dword_field",
        "command_pointer_field",
        "status_code",
    ]

    visual = run_latest_nvme_base_benchmark.build_option_matrix(
        mode=run_latest_nvme_base_benchmark.FULL_PRECISION_MODE,
        pages=None,
        page_workers=1,
        spec_document_type=run_latest_nvme_base_benchmark.NVM_COMMAND_SET_SPEC_DOCUMENT,
        visual_mode=True,
    )
    assert visual["visual_mode"] is True
    assert visual["rag_profile"] == "technical_spec_rag_visual"
    assert visual["image_mode"] == "referenced"
    assert visual["rag_figure_text_chunks"] is True
    assert visual["figure_region_ocr"] is True
    assert visual["rag_generated_figure_descriptions"] is True
    assert visual["figure_structure_extraction"] is True
    assert visual["command_set_query_eval"]["enabled"] is True


def test_docling_comparison_can_require_installed_docling(
    monkeypatch,  # noqa: ANN001
    sample_pdf: Path,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(benchmark_docling_comparison, "_module_available", lambda module_name: False)

    report = benchmark_docling_comparison.run_docling_comparison(
        input_pdf=sample_pdf,
        output_dir=tmp_path / "docling-required",
        document_label="docling-required",
        require_docling=True,
    )

    assert report["summary"]["docling_status"] == "skipped"
    assert report["summary"]["error_count"] == 1
    assert {finding["code"] for finding in report["findings"]} == {
        "docling_not_installed",
        "docling_required_not_available",
    }


def test_docling_metric_deltas_are_numeric_when_both_tools_report_numbers() -> None:
    current_run = {
        "duration_ms": 100,
        "pages_per_second": 20.0,
        "metrics": {"table_total": 2, "backend_availability": {"tesseract": True}},
    }
    docling_run = {
        "duration_ms": 150,
        "pages_per_second": 10.0,
        "metrics": {"table_total": 3, "backend_availability": {"tesseract": True}},
    }

    deltas = benchmark_docling_comparison.build_metric_deltas(current_run, docling_run)
    by_metric = {delta["metric"]: delta for delta in deltas}

    assert by_metric["duration_ms"]["delta"] == 50.0
    assert by_metric["pages_per_second"]["delta"] == -10.0
    assert by_metric["table_total"]["delta"] == 1.0
    assert by_metric["backend_availability"]["delta"] is None


def test_ocr_runtime_check_reports_missing_tesseract(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(check_ocr_runtime, "_discover_tesseract", lambda: None)
    monkeypatch.setattr(check_ocr_runtime, "_module_available", lambda module_name: module_name == "pytesseract")

    report = check_ocr_runtime.check_ocr_runtime("kor+eng")
    text = check_ocr_runtime.format_text_report(report)

    assert report["ready"] is False
    assert report["checks"]["tesseract_executable"]["ok"] is False
    assert report["checks"]["pypdfium2_import"]["ok"] is False
    assert report["checks"]["language_data"]["missing"] == ["kor", "eng"]
    assert "Tesseract executable: MISSING" in text


def test_ocr_runtime_check_identifies_missing_composite_language(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(check_ocr_runtime, "_discover_tesseract", lambda: "/usr/bin/tesseract")
    monkeypatch.setattr(check_ocr_runtime, "_module_available", lambda module_name: True)
    monkeypatch.setattr(check_ocr_runtime, "_list_tesseract_languages", lambda executable: (["eng"], None))

    report = check_ocr_runtime.check_ocr_runtime("kor+eng")

    assert report["ready"] is False
    assert report["checks"]["language_data"]["requested"] == ["kor", "eng"]
    assert report["checks"]["language_data"]["missing"] == ["kor"]


def test_ocr_backend_probe_reports_ready_tesseract_and_optional_backends(monkeypatch) -> None:  # noqa: ANN001
    def fake_module_available(module_name: str) -> bool:
        return module_name in {"pytesseract", "pypdfium2", "docling"}

    monkeypatch.setattr(probe_ocr_backends, "_module_available", fake_module_available)
    monkeypatch.setattr(probe_ocr_backends, "_discover_tesseract", lambda: "/usr/bin/tesseract")
    monkeypatch.setattr(probe_ocr_backends, "_list_tesseract_languages", lambda executable: (["eng", "kor"], None))

    report = probe_ocr_backends.probe_ocr_backends(
        ocr_lang="kor+eng",
        backends="tesseract,tesseract-cli,rapidocr,ocrmac,docling",
    )
    by_backend = {record["backend"]: record for record in report["backends"]}

    assert report["summary"]["ready_backends"] == ["tesseract", "tesseract-cli", "docling"]
    assert report["summary"]["recommended_backend"] == "tesseract"
    assert by_backend["tesseract"]["ready"] is True
    assert by_backend["tesseract-cli"]["ready"] is True
    assert by_backend["tesseract-cli"]["dependencies"][0]["name"] == "tesseract"
    assert by_backend["tesseract"]["language_data"]["missing"] == []
    assert by_backend["tesseract"]["confidence_normalization"]["raw_unit"] == "0_to_100"
    assert by_backend["rapidocr"]["status"] == "unavailable"
    assert by_backend["ocrmac"]["status"] in {"available", "unavailable"}
    assert by_backend["docling"]["module_available"] is True
    assert report["raw_content_included"] is False


def test_ocr_backend_probe_reports_missing_languages(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(probe_ocr_backends, "_module_available", lambda module_name: True)
    monkeypatch.setattr(probe_ocr_backends, "_discover_tesseract", lambda: "/usr/bin/tesseract")
    monkeypatch.setattr(probe_ocr_backends, "_list_tesseract_languages", lambda executable: (["eng"], None))

    report = probe_ocr_backends.probe_ocr_backends(ocr_lang="kor+eng", backends="tesseract")

    assert report["summary"]["ready_backend_count"] == 0
    assert report["backends"][0]["status"] == "available"
    assert report["backends"][0]["language_data"]["missing"] == ["kor"]


def test_figure_description_eval_passes_context_only_sidecars(tmp_path: Path) -> None:
    output_dir = tmp_path / "figure-description-pass"
    output_dir.mkdir()
    _write_jsonl(output_dir / "figures_rag.jsonl", [{"figure_id": "page-0001-figure-0001", "page": 1}])
    _write_jsonl(
        output_dir / "figure_descriptions_rag.jsonl",
        [
            {
                "description_id": "figure-description-000001",
                "figure_id": "page-0001-figure-0001",
                "text": "Generated figure description (context-only).",
                "observed_text": {
                    "caption_text": "Figure 1: Link state",
                    "heading_path": [],
                    "detected_labels": [],
                    "nearby_texts": [],
                    "ocr_texts": [],
                    "visual_pixels_interpreted": False,
                },
                "generated_description": "Generated figure description (context-only).",
                "generated_text": True,
                "generated_content_scope": "sidecar_only",
                "markdown_inserted": False,
                "generation_strategy": "deterministic_context_summary",
                "backend_status": "not_invoked_context_only",
                "review_required": True,
                "review_reasons": ["generated_content_sidecar_review", "visual_pixels_not_interpreted"],
                "hallucination_risk": "low",
                "classification_confidence": 0.82,
                "source_evidence": {
                    "caption_present": True,
                    "heading_path_present": False,
                    "detected_label_count": 0,
                    "nearby_text_count": 0,
                    "ocr_text_count": 0,
                    "visual_pixels_interpreted": False,
                },
                "evidence_refs": [{"evidence_type": "caption", "source": "caption_text"}],
                "source_refs": [{"source_type": "figure", "source_id": "page-0001-figure-0001", "page": 1}],
            }
        ],
    )
    _write_jsonl(
        output_dir / "retrieval_chunks_rag.jsonl",
        [
            {
                "chunk_id": "chunk-1",
                "chunk_type": "figure_description",
                "source_refs": [
                    {"source_type": "figure_description", "source_id": "figure-description-000001"}
                ],
            }
        ],
    )

    report = evaluate_figure_descriptions.evaluate_figure_descriptions(output_dir=output_dir)

    assert report["summary"]["passed"] is True
    assert report["summary"]["description_record_count"] == 1
    assert report["summary"]["figure_description_chunk_count"] == 1
    assert report["summary"]["evidence_backed_record_count"] == 1
    assert report["findings"] == []


def test_figure_description_eval_reports_local_only_violations(tmp_path: Path) -> None:
    output_dir = tmp_path / "figure-description-fail"
    output_dir.mkdir()
    _write_jsonl(output_dir / "figures_rag.jsonl", [])
    _write_jsonl(
        output_dir / "figure_descriptions_rag.jsonl",
        [
            {
                "description_id": "figure-description-000001",
                "figure_id": "page-0001-figure-0001",
                "text": "Generated figure description (context-only).",
                "observed_text": {"visual_pixels_interpreted": True},
                "generated_description": "Generated figure description (context-only).",
                "generated_text": False,
                "generated_content_scope": "document_body",
                "markdown_inserted": True,
                "backend_status": "vlm_invoked",
                "review_required": False,
                "review_reasons": "missing-list",
                "hallucination_risk": "unknown",
                "classification_confidence": 0.2,
                "source_evidence": {
                    "caption_present": False,
                    "heading_path_present": False,
                    "detected_label_count": 0,
                    "nearby_text_count": 0,
                    "ocr_text_count": 0,
                    "visual_pixels_interpreted": True,
                },
                "source_refs": [],
            }
        ],
    )
    _write_jsonl(output_dir / "retrieval_chunks_rag.jsonl", [])

    report = evaluate_figure_descriptions.evaluate_figure_descriptions(output_dir=output_dir)

    codes = {finding["code"] for finding in report["findings"]}
    assert report["summary"]["passed"] is False
    assert report["summary"]["error_count"] == 10
    assert report["summary"]["warning_count"] == 2
    assert {
        "missing_generated_text_flag",
        "invalid_observed_text_metadata",
        "missing_review_metadata",
        "invalid_hallucination_risk",
        "invalid_generated_content_scope",
        "figure_description_markdown_pollution",
        "missing_source_refs",
        "missing_source_evidence",
        "visual_pixels_interpreted",
        "backend_invoked",
        "low_confidence",
        "missing_retrieval_chunk",
    } <= codes


def test_figure_description_eval_cli_writes_report_and_fails_on_error(tmp_path: Path) -> None:
    output_dir = tmp_path / "figure-description-cli"
    output_dir.mkdir()
    report_file = tmp_path / "figure-description-report.json"

    exit_code = evaluate_figure_descriptions.main(
        [
            "--output-dir",
            str(output_dir),
            "--report-file",
            str(report_file),
            "--fail-on-error",
        ]
    )

    payload = json.loads(report_file.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["purpose"] == "local_figure_description_eval"
    assert payload["summary"]["error_count"] == 1
    assert payload["findings"][0]["code"] == "missing_figure_descriptions"


def test_release_gate_runner_writes_success_summary(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        stdout = '{"ready": true}' if any(str(part).endswith("check_ocr_runtime.py") for part in command) else "ok"
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release",
            gates=["ocr", "corpus", "benchmark", "schema", "packaging"],
            corpus_input_dir=Path("pdf"),
            corpus_baseline_report=Path("pdf/baseline/corpus_eval_report.json"),
            benchmark_baseline_report=Path("pdf/baseline/benchmark_report.json"),
            benchmark_page_counts="10",
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["summary"]["total_gate_commands"] == 8
    assert (tmp_path / "release" / "release_gate_report.json").exists()
    assert (tmp_path / "release" / "ocr_runtime_report.json").exists()
    assert any(any(str(part).endswith("run_corpus_eval.py") for part in command) for command in calls)
    assert any(any(str(part).endswith("benchmark_conversion.py") for part in command) for command in calls)
    assert any(any(str(part).endswith("export_output_schema.py") for part in command) for command in calls)
    assert any(any(str(part).endswith("inspect_wheel_contract.py") for part in command) for command in calls)
    assert any(command[1:] == ["-m", "pdf2md.gui", "--help"] for command in calls)
    benchmark_command = next(command for command in calls if any(str(part).endswith("benchmark_conversion.py") for part in command))
    assert "--page-workers" in benchmark_command


def test_release_gate_runner_supports_lightweight_ci_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "ci-lightweight",
            gates=["ci-lightweight"],
        )
    )

    assert payload["passed_release_gate"] is True
    assert [record["gate"] for record in payload["gates"]] == [
        "ci-lightweight:schema",
        "ci-lightweight:docs-output-contract",
        "ci-lightweight:cli-smoke",
        "ci-lightweight:lint-smoke",
    ]
    assert any(any(str(part).endswith("export_output_schema.py") for part in command) for command in calls)
    assert any("tests/test_docs_examples.py" in command for command in calls)
    assert any(command[1:] == ["-m", "pdf2md", "--help"] for command in calls)
    assert any(command[1:] == ["-m", "ruff", "check", "."] for command in calls)


def test_release_gate_runner_records_dependency_audit_as_advisory(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=1, stdout="", stderr="dependency audit warning")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "dependency-audit",
            gates=["dependency-audit"],
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["summary"]["failed_count"] == 0
    assert payload["gates"] == [
        {
            "gate": "dependency-audit",
            "command": [
                run_release_gates.sys.executable,
                "-m",
                "pip_audit",
                "--format",
                "json",
                "--output",
                str(tmp_path / "dependency-audit" / "dependency_audit_report.json"),
                "--cache-dir",
                str(tmp_path / "dependency-audit" / "pip-audit-cache"),
                "--progress-spinner",
                "off",
            ],
            "exit_code": 1,
            "status": "passed",
            "report_path": str(tmp_path / "dependency-audit" / "dependency_audit_report.json"),
            "stdout_tail": "",
            "stderr_tail": "dependency audit warning",
            "advisory": True,
            "advisory_exit_code": 1,
            "advisory_status": "failed",
        }
    ]
    assert any(command[1:3] == ["-m", "pip_audit"] for command in calls)


def test_release_gate_runner_supports_ocr_backends_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout='{"purpose": "multi_ocr_backend_probe"}', stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "ocr-backends",
            gates=["ocr-backends"],
            ocr_lang="kor+eng",
            ocr_backend_probe_backends="tesseract,docling",
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["gates"][0]["gate"] == "ocr-backends"
    assert payload["gates"][0]["report_path"].endswith("ocr_backend_probe_report.json")
    command = calls[0]
    assert any(str(part).endswith("probe_ocr_backends.py") for part in command)
    assert "--ocr-lang" in command
    assert "kor+eng" in command
    assert "--backends" in command
    assert "tesseract,docling" in command
    assert "--require-ready" in command


def test_release_gate_runner_fails_when_any_gate_command_fails(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    def fake_run(command, **kwargs):  # noqa: ANN001
        returncode = 1 if any(str(part).endswith("benchmark_conversion.py") for part in command) else 0
        stdout = '{"ready": true}' if any(str(part).endswith("check_ocr_runtime.py") for part in command) else ""
        stderr = "benchmark failed" if returncode else ""
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-fail",
            gates=["ocr", "benchmark"],
            benchmark_page_counts="10",
        )
    )

    assert payload["passed_release_gate"] is False
    assert payload["summary"]["failed_count"] == 1
    failed = [record for record in payload["gates"] if record["status"] == "failed"]
    assert failed[0]["gate"] == "benchmark"
    assert "benchmark failed" in failed[0]["stderr_tail"]


def test_release_gate_runner_supports_optional_rag_calibration_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="Wrote rag_eval_report.json", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-rag",
            gates=["rag"],
            rag_output_dir=tmp_path / "converted-spec",
            rag_eval_set=tmp_path / "rag_eval_queries.json",
            rag_min_expected_source_coverage=0.9,
            rag_min_requirement_coverage=0.9,
            rag_min_table_field_coverage=0.85,
            rag_min_cross_ref_resolved_coverage=0.8,
            rag_min_relationship_target_coverage=1.0,
            rag_max_chunk_token_p95=512,
            rag_max_conversion_duration_ms=10_000,
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["gates"][0]["gate"] == "rag"
    command = calls[0]
    assert any(str(part).endswith("run_rag_eval.py") for part in command)
    assert "--fail-on-threshold" in command
    assert "--min-expected-source-coverage" in command
    assert "--min-requirement-coverage" in command
    assert "--min-relationship-target-coverage" in command
    assert "--max-conversion-duration-ms" in command


def test_release_gate_runner_supports_optional_index_contract_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="Wrote index_contract_report.json", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-index",
            gates=["index-contract"],
            index_contract_output_dir=tmp_path / "converted-spec",
            index_contract_target="azure-ai-search",
            index_contract_metadata_max_bytes=2048,
            index_contract_confidential_safe=True,
            index_contract_fail_on_warning=True,
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["gates"][0]["gate"] == "index-contract"
    command = calls[0]
    assert any(str(part).endswith("validate_index_contract.py") for part in command)
    assert "--target" in command
    assert "azure-ai-search" in command
    assert "--metadata-max-bytes" in command
    assert "--confidential-safe" in command
    assert "--fail-on-warning" in command


def test_release_gate_runner_supports_optional_provenance_integrity_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="Wrote provenance_integrity_report.json", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-provenance",
            gates=["provenance-integrity"],
            provenance_integrity_output_dir=tmp_path / "converted-spec",
            provenance_integrity_fail_on_warning=True,
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["gates"][0]["gate"] == "provenance-integrity"
    command = calls[0]
    assert any(str(part).endswith("validate_provenance_integrity.py") for part in command)
    assert "--output-dir" in command
    assert "--fail-on-error" in command
    assert "--fail-on-warning" in command


def test_release_gate_runner_supports_optional_artifact_integrity_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="Wrote artifact_integrity_report.json", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-artifacts",
            gates=["artifact-integrity"],
            artifact_integrity_output_dir=tmp_path / "converted-spec",
            artifact_integrity_confidential_safe=True,
            artifact_integrity_fail_on_warning=True,
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["gates"][0]["gate"] == "artifact-integrity"
    command = calls[0]
    assert any(str(part).endswith("validate_artifact_integrity.py") for part in command)
    assert "--output-dir" in command
    assert "--fail-on-error" in command
    assert "--confidential-safe" in command
    assert "--fail-on-warning" in command


def _clean_validation_report() -> dict:
    return {"passed": True, "status": "passed", "summary": {"error_count": 0, "warning_count": 0}}


def _rag_conversion_report() -> dict:
    return {
        "status": "success",
        "duration_ms": 100,
        "summary": {
            "processed_pages": 2,
            "warning_count": 0,
            "actionable_warning_count": 0,
            "retrieval_chunk_record_count": 4,
            "retrieval_chunk_over_target_count": 0,
            "retrieval_chunk_duplicate_source_ref_count": 0,
            "rag_text_block_file_count": 1,
            "semantic_unit_file_count": 1,
            "retrieval_chunk_file_count": 1,
            "rag_table_record_count": 2,
            "requirement_record_count": 1,
            "requirement_traceability_record_count": 1,
            "technical_table_record_count": 1,
            "figure_rag_record_count": 1,
            "cross_ref_record_count": 2,
            "unresolved_cross_ref_count": 0,
            "pages_per_second": 10.0,
        },
    }


def _technical_conversion_report() -> dict:
    report = _rag_conversion_report()
    report["summary"] = {
        **report["summary"],
        "domain_unit_record_count": 3,
        "technical_table_record_count": 2,
        "requirement_record_count": 2,
        "requirement_traceability_record_count": 2,
    }
    return report


def _rag_eval_report() -> dict:
    return {
        "metrics": {
            "source_ref_presence_coverage": 1.0,
            "duplicate_source_ratio": 0.0,
            "cross_ref_resolved_coverage": 1.0,
            "relationship_target_coverage": 1.0,
        },
        "passed_calibration_gate": True,
    }


def test_preset_eval_scores_rag_optimized_against_100_point_model() -> None:
    result = run_preset_eval.score_preset_result(
        preset="rag_optimized",
        conversion_report=_rag_conversion_report(),
        artifact_report=_clean_validation_report(),
        index_report=_clean_validation_report(),
        provenance_report=_clean_validation_report(),
        rag_eval_report=_rag_eval_report(),
    )

    components = {component["code"]: component for component in result["components"]}
    assert result["score"] == 100
    assert result["gate"]["passed"] is True
    assert components["integrity"]["earned"] == 20
    assert components["chunk_token_compliance"]["earned"] == 15
    assert components["sidecar_coverage"]["earned"] == 15


def test_preset_eval_flags_missing_technical_domain_adapter() -> None:
    result = run_preset_eval.score_preset_result(
        preset="technical_spec_rag",
        domain_adapter="none",
        conversion_report=_technical_conversion_report(),
        artifact_report=_clean_validation_report(),
        index_report=_clean_validation_report(),
        provenance_report=_clean_validation_report(),
        rag_eval_report=_rag_eval_report(),
    )

    failed_codes = {condition["code"] for condition in result["gate"]["failed_conditions"]}
    assert "technical_domain_adapter_present" in failed_codes
    assert "ssd_contract_passed" in failed_codes
    assert result["gate"]["passed"] is False


def test_preset_eval_score_threshold_passes_and_fails() -> None:
    passing = run_preset_eval.score_preset_result(
        preset="rag_optimized",
        conversion_report=_rag_conversion_report(),
        artifact_report=_clean_validation_report(),
        index_report=_clean_validation_report(),
        provenance_report=_clean_validation_report(),
        rag_eval_report=_rag_eval_report(),
        min_score=90,
    )
    failing = run_preset_eval.score_preset_result(
        preset="rag_optimized",
        conversion_report=_rag_conversion_report(),
        artifact_report=_clean_validation_report(),
        index_report=_clean_validation_report(),
        provenance_report=_clean_validation_report(),
        rag_eval_report=_rag_eval_report(),
        min_score=101,
    )

    assert passing["gate"]["passed"] is True
    assert failing["gate"]["passed"] is False
    assert failing["gate"]["failed_conditions"][-1]["code"] == "min_score"


def test_release_gate_runner_supports_optional_preset_eval_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="Wrote preset_eval_report.json", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-preset-eval",
            gates=["preset-eval"],
            preset_eval_input_pdf=tmp_path / "NVMe_Base.pdf",
            preset_eval_domain_adapter="nvme",
            preset_eval_pages="1-2",
            preset_eval_min_score=80,
            rag_min_expected_source_coverage=0.9,
            rag_min_source_ref_presence_coverage=1.0,
            rag_max_chunk_token_p95=512,
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["gates"][0]["gate"] == "preset-eval"
    command = calls[0]
    assert any(str(part).endswith("run_preset_eval.py") for part in command)
    assert "--fail-on-threshold" in command
    assert "--domain-adapter" in command
    assert "nvme" in command
    assert "--pages" in command
    assert "--min-score" in command
    assert "--min-expected-source-coverage" in command
    assert "--min-source-ref-presence-coverage" in command
    assert "--max-chunk-token-p95" in command


def test_release_gate_runner_requires_docling_input_pdf(tmp_path: Path) -> None:
    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-docling-missing-input",
            gates=["docling"],
        )
    )

    assert payload["passed_release_gate"] is False
    assert payload["gates"][0]["gate"] == "docling"
    assert payload["gates"][0]["exit_code"] == 2
    assert "--docling-input-pdf is required" in payload["gates"][0]["stderr_tail"]


def test_release_gate_runner_supports_docling_installed_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="Wrote docling_benchmark_report.json", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    input_pdf = tmp_path / "NVM-Command-Set.pdf"
    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-docling",
            gates=["docling"],
            docling_input_pdf=input_pdf,
            docling_pages="1-2",
            docling_document_label="latest-nvme-smoke",
            docling_figure_semantics_mode="visual",
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["gates"][0]["gate"] == "docling"
    assert payload["gates"][0]["report_path"].endswith("docling_benchmark_report.json")
    command = calls[0]
    assert any(str(part).endswith("run_latest_nvme_command_set_eval.py") for part in command)
    assert str(input_pdf) in command
    assert "--require-docling" in command
    assert "--fail-on-error" in command
    assert "--fail-on-current-tool-failure" in command
    assert "--figure-semantics-mode" in command
    assert "visual" in command
    assert "--layout-comparison-mode" in command
    assert "summary" in command
    assert "--pages" in command


def test_release_gate_runner_requires_figure_description_eval_output_dir(tmp_path: Path) -> None:
    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-figure-description-missing-output",
            gates=["figure-description-eval"],
        )
    )

    assert payload["passed_release_gate"] is False
    assert payload["gates"][0]["gate"] == "figure-description-eval"
    assert payload["gates"][0]["exit_code"] == 2
    assert "--figure-description-eval-output-dir is required" in payload["gates"][0]["stderr_tail"]


def test_release_gate_runner_supports_figure_description_eval_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="Wrote figure_description_eval_report.json", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    output_dir = tmp_path / "converted-spec"
    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-figure-description-eval",
            gates=["figure-description-eval"],
            figure_description_eval_output_dir=output_dir,
            figure_description_eval_min_confidence=0.7,
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["gates"][0]["gate"] == "figure-description-eval"
    assert payload["gates"][0]["report_path"].endswith("figure_description_eval_report.json")
    command = calls[0]
    assert any(str(part).endswith("evaluate_figure_descriptions.py") for part in command)
    assert "--output-dir" in command
    assert str(output_dir) in command
    assert "--report-file" in command
    assert "--min-confidence" in command
    assert "0.7" in command
    assert "--fail-on-error" in command


def test_release_gate_runner_supports_optional_gui_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        stdout = '{"kind": "gui_runtime_doctor", "passed": true}' if "--doctor" in command else "ok"
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-gui",
            gates=["gui"],
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["summary"]["total_gate_commands"] == 4
    assert [record["gate"] for record in payload["gates"]] == [
        "gui:module-help",
        "gui:doctor",
        "gui:smoke-evidence",
        "gui:support-bundle",
    ]
    assert (tmp_path / "release-gui" / "gui" / "gui_help_report.json").exists()
    assert (tmp_path / "release-gui" / "gui" / "gui_doctor_report.json").exists()
    assert any(command[1:] == ["-m", "pdf2md.gui", "--help"] for command in calls)
    assert any("--doctor-format" in command and "json" in command for command in calls)
    smoke_command = next(command for command in calls if any(str(part).endswith("run_gui_smoke_evidence.py") for part in command))
    support_command = next(command for command in calls if any(str(part).endswith("create_gui_support_bundle.py") for part in command))
    assert "--state-path" in smoke_command
    assert str(tmp_path / "release-gui" / "gui" / "smoke") in smoke_command
    assert "--smoke-evidence" in support_command
    assert str(tmp_path / "release-gui" / "gui" / "smoke" / "gui_smoke_evidence.json") in support_command
    assert payload["gates"][2]["report_path"].endswith("gui_smoke_evidence.json")
    assert payload["gates"][3]["report_path"].endswith("gui_support_bundle.json")


def test_release_gate_runner_fails_gui_gate_on_redaction_failure(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    def fake_run(command, **kwargs):  # noqa: ANN001
        if any(str(part).endswith("run_gui_smoke_evidence.py") for part in command):
            return SimpleNamespace(returncode=1, stdout="", stderr="redaction failed")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-gui-redaction-fail",
            gates=["gui"],
        )
    )

    assert payload["passed_release_gate"] is False
    assert payload["summary"]["failed_count"] == 1
    failed = [record for record in payload["gates"] if record["status"] == "failed"]
    assert failed[0]["gate"] == "gui:smoke-evidence"
    assert "redaction failed" in failed[0]["stderr_tail"]


def test_gui_cli_parity_report_detects_hash_mismatch(tmp_path: Path) -> None:
    cli_output = tmp_path / "cli"
    gui_output = tmp_path / "gui"
    cli_output.mkdir()
    gui_output.mkdir()
    (cli_output / "document.md").write_text("cli\n", encoding="utf-8")
    (gui_output / "document.md").write_text("gui\n", encoding="utf-8")

    payload = run_gui_cli_parity.compare_artifacts(cli_output, gui_output, artifact_names=("document.md",))

    assert payload["passed"] is False
    assert payload["summary"]["mismatched_count"] == 1
    assert payload["artifacts"][0]["artifact"] == "document.md"
    assert payload["artifacts"][0]["status"] == "mismatched"


def test_release_gate_runner_supports_optional_gui_parity_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="Wrote gui_cli_parity_report.json", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-gui-parity",
            gates=["gui-parity"],
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["summary"]["total_gate_commands"] == 1
    assert payload["gates"][0]["gate"] == "gui-parity"
    command = calls[0]
    assert any(str(part).endswith("run_gui_cli_parity.py") for part in command)
    assert "--output-dir" in command
    assert payload["gates"][0]["report_path"].endswith("gui_cli_parity_report.json")


def test_gui_cli_benchmark_policy_is_advisory_by_default() -> None:
    payload = benchmark_gui_cli_parity.apply_benchmark_policy(
        cli_elapsed_ms=100,
        gui_elapsed_ms=150,
        max_gui_duration_ratio=1.2,
        fail_on_regression=False,
    )

    assert payload["passed"] is True
    assert payload["threshold_status"] == "advisory"
    assert payload["gui_duration_ratio"] == 1.5
    assert payload["regressions"][0]["severity"] == "advisory"


def test_gui_cli_benchmark_policy_can_fail_on_threshold() -> None:
    payload = benchmark_gui_cli_parity.apply_benchmark_policy(
        cli_elapsed_ms=100,
        gui_elapsed_ms=150,
        max_gui_duration_ratio=1.2,
        fail_on_regression=True,
    )

    assert payload["passed"] is False
    assert payload["threshold_status"] == "failed"
    assert payload["regressions"][0]["severity"] == "failed"


def test_release_gate_runner_supports_optional_gui_benchmark_gate(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="Wrote gui_cli_benchmark_report.json", stderr="")

    monkeypatch.setattr(run_release_gates.subprocess, "run", fake_run)

    payload = run_release_gates.run_release_gates(
        run_release_gates.ReleaseGateConfig(
            output_dir=tmp_path / "release-gui-benchmark",
            gates=["gui-benchmark"],
        )
    )

    assert payload["passed_release_gate"] is True
    assert payload["summary"]["total_gate_commands"] == 1
    assert payload["gates"][0]["gate"] == "gui-benchmark"
    command = calls[0]
    assert any(str(part).endswith("benchmark_gui_cli_parity.py") for part in command)
    assert "--output-dir" in command
    assert payload["gates"][0]["report_path"].endswith("gui_cli_benchmark_report.json")


def test_wheel_contract_inspector_accepts_gui_resource_and_entry_points(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    wheel_path = dist_dir / "pdf2md-0.1.0-py3-none-any.whl"
    _write_wheel(
        wheel_path,
        {
            *inspect_wheel_contract.REQUIRED_WHEEL_MEMBERS,
            "pdf2md-0.1.0.dist-info/entry_points.txt",
        },
        entry_points="\n".join(
                [
                    "[console_scripts]",
                    "pdf2md = pdf2md.cli:main",
                    "pdf2md-gui = pdf2md.gui:main",
                    "pdf2md-mcp = pdf2md.mcp_server:main",
                    "",
                ]
            ),
        )

    payload = inspect_wheel_contract.inspect_wheel_contract(dist_dir)

    assert payload["status"] == "passed"
    assert payload["summary"]["failed_count"] == 0
    assert any(check["name"] == "wheel_member:pdf2md/py.typed" for check in payload["checks"])
    assert any(
        check["name"] == "wheel_member:pdf2md/extractors/ocr_backends/registry.py"
        for check in payload["checks"]
    )
    assert any(check["name"] == "wheel_member:pdf2md/resources/GUI_USER_GUIDE.md" for check in payload["checks"])
    assert any(check["name"] == "console_script:pdf2md-gui" for check in payload["checks"])


def test_wheel_contract_inspector_fails_without_gui_help_resource(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    wheel_path = dist_dir / "pdf2md-0.1.0-py3-none-any.whl"
    members = set(inspect_wheel_contract.REQUIRED_WHEEL_MEMBERS)
    members.remove("pdf2md/resources/GUI_USER_GUIDE.md")
    members.add("pdf2md-0.1.0.dist-info/entry_points.txt")
    _write_wheel(
        wheel_path,
        members,
        entry_points="\n".join(
                [
                    "[console_scripts]",
                    "pdf2md = pdf2md.cli:main",
                    "pdf2md-gui = pdf2md.gui:main",
                    "pdf2md-mcp = pdf2md.mcp_server:main",
                    "",
                ]
            ),
        )

    payload = inspect_wheel_contract.inspect_wheel_contract(dist_dir)

    assert payload["status"] == "failed"
    failed = [check for check in payload["checks"] if check["status"] == "failed"]
    assert failed == [
        {
            "name": "wheel_member:pdf2md/resources/GUI_USER_GUIDE.md",
            "status": "failed",
            "message": "missing",
        }
    ]


def test_wheel_contract_inspector_fails_without_ocr_backend_package(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    wheel_path = dist_dir / "pdf2md-0.1.0-py3-none-any.whl"
    members = set(inspect_wheel_contract.REQUIRED_WHEEL_MEMBERS)
    members.remove("pdf2md/extractors/ocr_backends/registry.py")
    members.add("pdf2md-0.1.0.dist-info/entry_points.txt")
    _write_wheel(
        wheel_path,
        members,
        entry_points="\n".join(
            [
                "[console_scripts]",
                "pdf2md = pdf2md.cli:main",
                "pdf2md-gui = pdf2md.gui:main",
                "",
            ]
        ),
    )

    payload = inspect_wheel_contract.inspect_wheel_contract(dist_dir)

    assert payload["status"] == "failed"
    assert {
        "name": "wheel_member:pdf2md/extractors/ocr_backends/registry.py",
        "status": "failed",
        "message": "missing",
    } in payload["checks"]


def _write_wheel(wheel_path: Path, members: set[str], *, entry_points: str) -> None:
    with zipfile.ZipFile(wheel_path, "w") as wheel:
        for member in sorted(members):
            wheel.writestr(member, entry_points if member.endswith("entry_points.txt") else "")
