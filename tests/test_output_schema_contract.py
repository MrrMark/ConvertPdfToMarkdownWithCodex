from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from pdf2md.config import Config
from pdf2md.models import CorpusManifest, Manifest, Report
from pdf2md.pipeline import run_conversion
from helpers.normalize_outputs import normalize_manifest, normalize_report
from scripts import export_output_schema


def test_generated_manifest_and_report_match_current_models(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "schema-contract"
    result = run_conversion(Config(input_pdf=sample_pdf, output_dir=output_dir, pages="1", keep_page_markers=True))

    assert result.exit_code == 0
    manifest_payload = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report_payload = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))

    manifest = Manifest.model_validate(manifest_payload)
    report = Report.model_validate(report_payload)

    assert manifest.schema_version == "1.0"
    assert report.schema_version == "1.0"
    assert report.summary.text_line_extract_count >= 1


def test_additive_optional_fields_do_not_change_normalized_contract(sample_pdf: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "schema-additive"
    result = run_conversion(Config(input_pdf=sample_pdf, output_dir=output_dir, pages="1", keep_page_markers=True))
    assert result.exit_code == 0

    manifest_payload = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report_payload = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    manifest_with_extra = deepcopy(manifest_payload)
    report_with_extra = deepcopy(report_payload)
    manifest_with_extra["future_optional_field"] = {"ignored": True}
    report_with_extra["future_optional_field"] = {"ignored": True}
    report_with_extra["summary"]["future_optional_metric"] = 1

    Manifest.model_validate(manifest_with_extra)
    Report.model_validate(report_with_extra)

    assert normalize_manifest(manifest_payload) == normalize_manifest(manifest_with_extra)
    assert normalize_report(report_payload) == normalize_report(report_with_extra)


def test_output_schema_export_is_deterministic(tmp_path: Path) -> None:
    output_dir = tmp_path / "schema"

    written = export_output_schema.write_schema_files(output_dir)

    assert [path.name for path in written] == [
        "manifest.schema.json",
        "report.schema.json",
        "conversion_state.schema.json",
        "interrupted_conversion_report.schema.json",
        "batch_report.schema.json",
        "corpus_manifest.schema.json",
        "corpus_diff_report.schema.json",
        "requirement_change_impact_report.schema.json",
        "index_contract_report.schema.json",
        "provenance_integrity_report.schema.json",
        "artifact_integrity_report.schema.json",
        "page_window_merge_report.schema.json",
        "plan_apply_report.schema.json",
        "visual_sidecar_contract_report.schema.json",
        "docling_benchmark_report.schema.json",
        "docling_artifact_comparison.schema.json",
        "latest_nvme_spec_benchmark_report.schema.json",
        "latest_ocp_datacenter_nvme_ssd_benchmark_report.schema.json",
        "latest_ssd_security_spec_benchmark_report.schema.json",
        "ocr_backend_probe_report.schema.json",
        "figure_description_eval_report.schema.json",
        "local_corpus_evidence_pack.schema.json",
        "corpus_evidence_analysis_report.schema.json",
        "corpus_evidence_trend_report.schema.json",
    ]
    assert export_output_schema.check_schema_files(output_dir) == []
    manifest_schema = json.loads((output_dir / "manifest.schema.json").read_text(encoding="utf-8"))
    corpus_schema = json.loads((output_dir / "corpus_manifest.schema.json").read_text(encoding="utf-8"))
    assert manifest_schema["properties"]["schema_version"]["default"] == "1.0"
    conversion_state_schema = json.loads((output_dir / "conversion_state.schema.json").read_text(encoding="utf-8"))
    assert conversion_state_schema["properties"]["purpose"]["default"] == "conversion_state"
    interrupted_schema = json.loads(
        (output_dir / "interrupted_conversion_report.schema.json").read_text(encoding="utf-8")
    )
    assert interrupted_schema["properties"]["purpose"]["default"] == "interrupted_conversion"
    assert corpus_schema["properties"]["purpose"]["default"] == "rag_corpus_ingest"
    diff_schema = json.loads((output_dir / "corpus_diff_report.schema.json").read_text(encoding="utf-8"))
    assert diff_schema["properties"]["purpose"]["default"] == "rag_corpus_incremental_diff"
    impact_schema = json.loads(
        (output_dir / "requirement_change_impact_report.schema.json").read_text(encoding="utf-8")
    )
    assert impact_schema["properties"]["purpose"]["default"] == "rag_requirement_change_impact"
    index_contract_schema = json.loads((output_dir / "index_contract_report.schema.json").read_text(encoding="utf-8"))
    assert index_contract_schema["properties"]["purpose"]["default"] == "rag_index_contract_validation"
    provenance_schema = json.loads((output_dir / "provenance_integrity_report.schema.json").read_text(encoding="utf-8"))
    assert provenance_schema["properties"]["purpose"]["default"] == "rag_provenance_integrity_validation"
    artifact_schema = json.loads((output_dir / "artifact_integrity_report.schema.json").read_text(encoding="utf-8"))
    assert artifact_schema["properties"]["purpose"]["default"] == "output_artifact_integrity_validation"
    page_window_schema = json.loads((output_dir / "page_window_merge_report.schema.json").read_text(encoding="utf-8"))
    assert page_window_schema["properties"]["purpose"]["default"] == "page_window_merge"
    assert "sidecar_inventory" in page_window_schema["properties"]
    assert "merge_memory_guard" in page_window_schema["properties"]
    plan_apply_schema = json.loads((output_dir / "plan_apply_report.schema.json").read_text(encoding="utf-8"))
    assert plan_apply_schema["properties"]["purpose"]["default"] == "large_spec_plan_apply_audit"
    assert "option_matrix" in plan_apply_schema["properties"]
    assert "skipped_options" in plan_apply_schema["properties"]
    visual_contract_schema = json.loads(
        (output_dir / "visual_sidecar_contract_report.schema.json").read_text(encoding="utf-8")
    )
    assert visual_contract_schema["properties"]["purpose"]["default"] == "visual_sidecar_contract_validation"
    assert (
        "figure_description_record_count"
        in visual_contract_schema["$defs"]["VisualSidecarContractSummary"]["properties"]
    )
    docling_benchmark_schema = json.loads(
        (output_dir / "docling_benchmark_report.schema.json").read_text(encoding="utf-8")
    )
    assert docling_benchmark_schema["properties"]["purpose"]["default"] == "docling_benchmark_comparison"
    assert "layout_comparison_mode" in docling_benchmark_schema["$defs"]["DoclingBenchmarkSummary"]["properties"]
    docling_comparison_schema = json.loads(
        (output_dir / "docling_artifact_comparison.schema.json").read_text(encoding="utf-8")
    )
    assert docling_comparison_schema["properties"]["purpose"]["default"] == "docling_sanitized_artifact_comparison"
    assert "layout_comparable" in docling_comparison_schema["$defs"]["DoclingArtifactSummary"]["properties"]
    latest_nvme_schema = json.loads(
        (output_dir / "latest_nvme_spec_benchmark_report.schema.json").read_text(encoding="utf-8")
    )
    assert latest_nvme_schema["properties"]["purpose"]["default"] == "latest_nvme_spec_benchmark"
    assert "spec_document_type" in latest_nvme_schema["properties"]
    assert "command_set_eval" in latest_nvme_schema["properties"]
    assert "sidecar_file_sizes" in latest_nvme_schema["$defs"]["LatestNvmeSpecBenchmarkSummary"]["properties"]
    assert (
        "command_set_eval_expected_source_coverage"
        in latest_nvme_schema["$defs"]["LatestNvmeSpecBenchmarkSummary"]["properties"]
    )
    latest_ocp_schema = json.loads(
        (output_dir / "latest_ocp_datacenter_nvme_ssd_benchmark_report.schema.json").read_text(encoding="utf-8")
    )
    assert latest_ocp_schema["properties"]["purpose"]["default"] == "latest_ocp_datacenter_nvme_ssd_benchmark"
    assert latest_ocp_schema["properties"]["expected_version"]["default"] == "2.7"
    assert "ocp_eval" in latest_ocp_schema["properties"]
    assert "ocp_requirement_unit_count" in latest_ocp_schema["$defs"][
        "LatestOcpDatacenterNvmeSsdBenchmarkSummary"
    ]["properties"]
    assert "ocp_eval_expected_source_coverage" in latest_ocp_schema["$defs"][
        "LatestOcpDatacenterNvmeSsdBenchmarkSummary"
    ]["properties"]
    latest_ssd_security_schema = json.loads(
        (output_dir / "latest_ssd_security_spec_benchmark_report.schema.json").read_text(encoding="utf-8")
    )
    assert latest_ssd_security_schema["properties"]["purpose"]["default"] == "latest_ssd_security_spec_benchmark"
    assert "security_domain_unit_counts" in latest_ssd_security_schema["$defs"][
        "LatestSsdSecuritySpecBenchmarkSummary"
    ]["properties"]
    assert "contract_validation" in latest_ssd_security_schema["properties"]
    ocr_probe_schema = json.loads((output_dir / "ocr_backend_probe_report.schema.json").read_text(encoding="utf-8"))
    assert ocr_probe_schema["properties"]["purpose"]["default"] == "multi_ocr_backend_probe"
    figure_eval_schema = json.loads(
        (output_dir / "figure_description_eval_report.schema.json").read_text(encoding="utf-8")
    )
    assert figure_eval_schema["properties"]["purpose"]["default"] == "local_figure_description_eval"
    evidence_schema = json.loads((output_dir / "local_corpus_evidence_pack.schema.json").read_text(encoding="utf-8"))
    assert evidence_schema["properties"]["purpose"]["default"] == "local_technical_corpus_evidence_pack"
    assert "coverage_failure_count" in evidence_schema["$defs"]["LocalCorpusEvidenceSummary"]["properties"]
    assert "raw_content_included" in evidence_schema["$defs"]["LocalCorpusEvidenceRedactionPolicy"]["properties"]
    assert "coverage_summary" in evidence_schema["$defs"]["LocalCorpusEvidenceDocument"]["properties"]
    assert "coverage_summary" in evidence_schema["$defs"]["LocalCorpusEvidenceDomain"]["properties"]
    analysis_schema = json.loads(
        (output_dir / "corpus_evidence_analysis_report.schema.json").read_text(encoding="utf-8")
    )
    assert analysis_schema["properties"]["purpose"]["default"] == "corpus_evidence_signature_analysis"
    trend_schema = json.loads((output_dir / "corpus_evidence_trend_report.schema.json").read_text(encoding="utf-8"))
    assert trend_schema["properties"]["purpose"]["default"] == "corpus_evidence_trend_comparison"


def test_output_schema_doc_lists_every_public_schema() -> None:
    output_schema_doc = Path("docs/OUTPUT_SCHEMA.md").read_text(encoding="utf-8")

    for schema_filename in export_output_schema.SCHEMA_FILES:
        assert f"docs/schema/{schema_filename}" in output_schema_doc


def test_corpus_manifest_model_accepts_rag_file_map() -> None:
    corpus = CorpusManifest.model_validate(
        {
            "schema_version": "1.0",
            "purpose": "rag_corpus_ingest",
            "input_dir": "/tmp/input",
            "output_dir": "/tmp/input/output",
            "documents": [
                {
                    "doc_id": "spec",
                    "input_pdf": "/tmp/input/spec.pdf",
                    "source_sha256": "0" * 64,
                    "output_dir": "/tmp/input/output/spec",
                    "status": "success",
                    "selected_pages": [1, 2],
                    "skipped": False,
                    "files": {
                        "markdown": "/tmp/input/output/spec/spec.md",
                        "manifest": "/tmp/input/output/spec/spec_manifest.json",
                        "report": "/tmp/input/output/spec/spec_report.json",
                        "retrieval_chunks_rag": "/tmp/input/output/spec/retrieval_chunks_rag.jsonl",
                        "requirement_traceability_rag": "/tmp/input/output/spec/requirement_traceability_rag.jsonl",
                        "technical_tables_rag": "/tmp/input/output/spec/technical_tables_rag.jsonl",
                    },
                }
            ],
        }
    )

    assert corpus.documents[0].files.retrieval_chunks_rag.endswith("retrieval_chunks_rag.jsonl")
    assert corpus.documents[0].files.technical_tables_rag.endswith("technical_tables_rag.jsonl")


def test_committed_output_schemas_match_current_models() -> None:
    schema_dir = Path("docs/schema")

    assert export_output_schema.check_schema_files(schema_dir) == []
