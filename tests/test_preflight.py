from __future__ import annotations

import json
from pathlib import Path

from pdf2md import mcp_server
from pdf2md.preflight import (
    PLAN_APPLY_CONFIG_OPTIONS,
    PreflightOptions,
    apply_large_spec_plan_options,
    plan_large_spec_conversion,
    recommend_domain_adapter_for_pdf,
)
from scripts.plan_large_spec_conversion import main as plan_large_spec_main
from tests.fixtures.pdf_builder import PageSpec, PositionedText, TableSpec, write_pdf


def test_large_spec_preflight_recommends_windowed_technical_ingest(tmp_path: Path) -> None:
    input_pdf = tmp_path / "large-spec.pdf"
    write_pdf(
        input_pdf,
        [
            PageSpec(texts=[PositionedText(f"Page {page} technical content", 72, 760)])
            for page in range(1, 206)
        ],
    )

    plan = mcp_server.plan_large_spec_conversion(
        input_pdf=str(input_pdf),
        sample_page_count=3,
        domain_adapter="nvme",
        roots=[tmp_path],
    )

    assert plan["purpose"] == "large_spec_preflight_plan"
    assert plan["selected_page_count"] == 205
    assert plan["sampled_pages"] == [1, 103, 205]
    assert plan["recommendation"]["use_page_windowing"] is True
    assert plan["recommendation"]["preferred_mcp_tool"] == "pdf2md_convert_pdf_windowed"
    assert plan["recommendation"]["recommended_options"]["rag_profile"] == "technical_spec_rag"
    assert plan["recommendation"]["recommended_options"]["domain_adapter"] == "nvme"
    assert plan["recommendation"]["recommended_options"]["image_mode"] == "none"
    assert plan["recommendation"]["recommended_options"]["window_size"] == 100
    assert "large_selected_page_count" in plan["recommendation"]["reasons"]["windowing"]
    assert len(plan["source_sha256"]) == 64


def test_large_spec_preflight_prefers_visual_sidecars_when_requested(tmp_path: Path) -> None:
    input_pdf = tmp_path / "visual-spec.pdf"
    write_pdf(input_pdf, [PageSpec(texts=[PositionedText("Visual spec", 72, 760)], repeated_image=True)])

    plan = plan_large_spec_conversion(
        input_pdf,
        PreflightOptions(sample_page_count=1, domain_adapter="nvme", prefer_visual=True),
    )

    options = plan["recommendation"]["recommended_options"]
    assert plan["recommendation"]["use_page_windowing"] is False
    assert options["rag_profile"] == "technical_spec_rag_visual"
    assert options["domain_adapter"] == "nvme"
    assert options["image_mode"] == "referenced"
    assert plan["recommendation"]["preferred_mcp_tool"] == "pdf2md_convert_pdf"


def test_large_spec_preflight_recommends_security_domain_adapter_without_raw_text(tmp_path: Path) -> None:
    input_pdf = tmp_path / "DMTF-SPDM-Synthetic.pdf"
    write_pdf(
        input_pdf,
        [
            PageSpec(
                texts=[
                    PositionedText("Security Protocol and Data Model (SPDM) Specification", 72, 760),
                    PositionedText("GET_MEASUREMENTS and CHALLENGE_AUTH message flow", 72, 740),
                ]
            )
        ],
    )

    recommendation = recommend_domain_adapter_for_pdf(input_pdf, PreflightOptions(sample_page_count=1))
    plan = plan_large_spec_conversion(input_pdf, PreflightOptions(sample_page_count=1))

    assert recommendation["recommended_domain_adapter"] == "spdm"
    assert recommendation["confidence"] == "high"
    assert recommendation["raw_content_included"] is False
    assert "sample_text" not in recommendation
    assert plan["recommendation"]["recommended_options"]["domain_adapter"] == "spdm"
    assert plan["recommendation"]["domain_adapter_recommendation"]["recommended_domain_adapter"] == "spdm"


def test_large_spec_preflight_recommends_storage_domain_adapters_without_raw_text(tmp_path: Path) -> None:
    cases = [
        (
            "NVMe-Base-Synthetic.pdf",
            "NVM Express Base Specification Admin Command Submission Queue Completion Queue Command Dword CDW",
            "nvme",
        ),
        (
            "PCIe-Base-Synthetic.pdf",
            "PCI Express Base Specification configuration space extended capability link status TLP lane margining",
            "pcie",
        ),
        (
            "OCP-Datacenter-NVMe-SSD-Synthetic.pdf",
            "Open Compute Project Datacenter NVMe SSD requirement ID telemetry profile latency monitor",
            "ocp",
        ),
    ]
    for filename, text, expected_adapter in cases:
        input_pdf = tmp_path / filename
        write_pdf(input_pdf, [PageSpec(texts=[PositionedText(text, 72, 760)])])

        recommendation = recommend_domain_adapter_for_pdf(input_pdf, PreflightOptions(sample_page_count=1))
        plan = plan_large_spec_conversion(input_pdf, PreflightOptions(sample_page_count=1))

        assert recommendation["recommended_domain_adapter"] == expected_adapter
        assert recommendation["confidence"] == "high"
        assert recommendation["raw_content_included"] is False
        assert "sample_text" not in recommendation
        assert plan["recommendation"]["recommended_options"]["domain_adapter"] == expected_adapter


def test_large_spec_preflight_records_recommendation_basis_without_raw_text(tmp_path: Path) -> None:
    input_pdf = tmp_path / "NVMe-Base-Synthetic.pdf"
    write_pdf(
        input_pdf,
        [
            PageSpec(
                texts=[
                    PositionedText(
                        "NVM Express Base Specification Admin Command Submission Queue Completion Queue CDW",
                        72,
                        760,
                    )
                ]
            )
        ],
    )

    recommendation = recommend_domain_adapter_for_pdf(input_pdf, PreflightOptions(sample_page_count=1))
    basis = recommendation["recommendation_basis"]

    assert basis["top_adapter"] == "nvme"
    assert basis["top_score"] > basis["runner_up_score"]
    assert basis["score_margin"] >= 2
    assert basis["matched_candidate_count"] >= 1
    assert basis["ambiguous"] is False
    assert basis["raw_content_included"] is False
    assert "sample_text" not in recommendation


def test_large_spec_preflight_does_not_promote_ambiguous_domain_adapter(tmp_path: Path) -> None:
    input_pdf = tmp_path / "ambiguous-nvme-pcie.pdf"
    write_pdf(input_pdf, [PageSpec(texts=[PositionedText("NVMe PCIe", 72, 760)])])

    recommendation = recommend_domain_adapter_for_pdf(input_pdf, PreflightOptions(sample_page_count=1))
    plan = plan_large_spec_conversion(input_pdf, PreflightOptions(sample_page_count=1))

    assert recommendation["confidence"] == "low"
    assert recommendation["recommendation_basis"]["ambiguous"] is True
    assert recommendation["recommendation_basis"]["score_margin"] == 0
    assert "domain_adapter" not in plan["recommendation"]["recommended_options"]


def test_large_spec_preflight_recommends_customer_requirements_without_raw_text(tmp_path: Path) -> None:
    input_pdf = tmp_path / "customer-requirements-specification.pdf"
    write_pdf(
        input_pdf,
        [
            PageSpec(
                texts=[
                    PositionedText("Customer Requirements Specification", 72, 760),
                    PositionedText("Supplier shall comply with the acceptance criteria and compliance matrix.", 72, 740),
                ]
            )
        ],
    )

    recommendation = recommend_domain_adapter_for_pdf(input_pdf, PreflightOptions(sample_page_count=1))
    plan = plan_large_spec_conversion(input_pdf, PreflightOptions(sample_page_count=1))

    assert recommendation["recommended_domain_adapter"] == "customer-requirements"
    assert recommendation["confidence"] == "high"
    assert recommendation["raw_content_included"] is False
    assert recommendation["recommendation_basis"]["top_adapter"] == "customer-requirements"
    assert "sample_text" not in recommendation
    assert plan["recommendation"]["recommended_options"]["domain_adapter"] == "customer-requirements"


def test_large_spec_preflight_keeps_ocp_ahead_of_customer_requirements(tmp_path: Path) -> None:
    input_pdf = tmp_path / "OCP-Datacenter-NVMe-SSD-requirements.pdf"
    write_pdf(
        input_pdf,
        [
            PageSpec(
                texts=[
                    PositionedText("Open Compute Project Datacenter NVMe SSD", 72, 760),
                    PositionedText("Requirement ID, telemetry profile, latency monitor, and cloud SSD behavior.", 72, 740),
                ]
            )
        ],
    )

    recommendation = recommend_domain_adapter_for_pdf(input_pdf, PreflightOptions(sample_page_count=1))

    assert recommendation["recommended_domain_adapter"] == "ocp"
    assert recommendation["confidence"] == "high"
    assert recommendation["recommendation_basis"]["top_adapter"] == "ocp"


def test_large_spec_preflight_recommends_performance_profile_from_sample_metrics(tmp_path: Path) -> None:
    input_pdf = tmp_path / "table-dense-large-spec.pdf"
    table = TableSpec(
        rows=[["Field", "Bits", "Description"], ["CAP.MQES", "15:0", "Synthetic register field"]],
        x=72,
        y=720,
        column_widths=[120, 80, 220],
    )
    write_pdf(
        input_pdf,
        [
            PageSpec(
                texts=[PositionedText(f"Table dense page {page}", 72, 760)],
                tables=[table],
            )
            for page in range(1, 81)
        ],
    )

    plan = plan_large_spec_conversion(input_pdf, PreflightOptions(sample_page_count=3))
    recommendation = plan["recommendation"]

    assert recommendation["performance_profile"]["name"] == "table_dense_parallel"
    assert recommendation["performance_profile"]["recommended_page_workers"] == 2
    assert recommendation["recommended_options"]["page_workers"] == 2
    assert "large_or_table_dense_document" in recommendation["reasons"]["page_workers"]
    assert recommendation["performance_profile"]["raw_content_included"] is False


def test_large_spec_plan_apply_maps_safe_recommendations_without_raw_content() -> None:
    plan = {
        "schema_version": "1.0",
        "purpose": "large_spec_preflight_plan",
        "input_pdf": "/tmp/security.pdf",
        "source_sha256": "0" * 64,
        "total_pages": 300,
        "selected_page_count": 300,
        "sampled_pages": [1, 150, 300],
        "recommendation": {
            "preferred_mcp_tool": "pdf2md_convert_pdf",
            "recommended_options": {
                "rag_profile": "technical_spec_rag",
                "domain_adapter": "spdm",
                "image_mode": "none",
                "rag_sidecar_scope": "minimal",
                "page_workers": 2,
                "image_extraction_page_timeout_seconds": None,
                "image_extraction_stage_timeout_seconds": 120,
                "figure_semantics_stage_timeout_seconds": 60,
            },
            "recommended_option_sources": {
                "domain_adapter": "domain_adapter_recommendation",
            },
            "domain_adapter_recommendation": {
                "recommended_domain_adapter": "spdm",
                "confidence": "high",
                "recommendation_basis": {"ambiguous": False},
            },
        },
    }

    applied_options, audit = apply_large_spec_plan_options(
        plan,
        current_options={
            "rag_profile": "preserve",
            "domain_adapter": None,
            "image_mode": None,
            "rag_sidecar_scope": None,
            "page_workers": 1,
            "image_extraction_page_timeout_seconds": None,
            "image_extraction_stage_timeout_seconds": None,
            "figure_semantics_stage_timeout_seconds": None,
        },
        explicit_options=set(),
        allowed_options=PLAN_APPLY_CONFIG_OPTIONS,
    )

    assert applied_options["rag_profile"] == "technical_spec_rag"
    assert applied_options["domain_adapter"] == "spdm"
    assert applied_options["image_mode"] == "none"
    assert applied_options["rag_sidecar_scope"] == "minimal"
    assert applied_options["page_workers"] == 2
    assert "image_extraction_page_timeout_seconds" not in applied_options
    assert audit["purpose"] == "large_spec_plan_apply_audit"
    assert audit["raw_content_included"] is False
    assert audit["policy"]["conflict_resolution"] == "explicit_option_precedence"
    assert audit["option_matrix"]["before"]["rag_profile"] == "preserve"
    assert audit["option_matrix"]["after"]["rag_profile"] == "technical_spec_rag"
    assert audit["skipped_options"] == [
        {
            "option": "image_extraction_page_timeout_seconds",
            "reason": "null_recommendation",
            "value": None,
        }
    ]
    assert "sample_text" not in json.dumps(audit, ensure_ascii=False, sort_keys=True)


def test_large_spec_plan_apply_rejects_low_ambiguous_domain_adapter() -> None:
    plan = {
        "schema_version": "1.0",
        "purpose": "large_spec_preflight_plan",
        "recommendation": {
            "recommended_options": {
                "rag_profile": "technical_spec_rag",
                "domain_adapter": "spdm",
            },
            "recommended_option_sources": {
                "domain_adapter": "domain_adapter_recommendation",
            },
            "domain_adapter_recommendation": {
                "recommended_domain_adapter": "spdm",
                "confidence": "low",
                "recommendation_basis": {"ambiguous": True},
            },
        },
    }

    applied_options, audit = apply_large_spec_plan_options(
        plan,
        current_options={
            "rag_profile": "preserve",
            "domain_adapter": None,
            "image_mode": None,
            "rag_sidecar_scope": None,
            "page_workers": 1,
            "image_extraction_page_timeout_seconds": None,
            "image_extraction_stage_timeout_seconds": None,
            "figure_semantics_stage_timeout_seconds": None,
        },
        explicit_options=set(),
    )

    assert applied_options == {"rag_profile": "technical_spec_rag"}
    assert audit["option_matrix"]["after"]["domain_adapter"] is None
    assert {
        "option": "domain_adapter",
        "reason": "low_or_ambiguous_domain_adapter_recommendation",
        "value": "spdm",
    } in audit["skipped_options"]


def test_plan_large_spec_conversion_script_writes_report(tmp_path: Path) -> None:
    input_pdf = tmp_path / "small-spec.pdf"
    report_path = tmp_path / "preflight.json"
    write_pdf(input_pdf, [PageSpec(texts=[PositionedText("Small spec", 72, 760)])])

    exit_code = plan_large_spec_main(
        [
            str(input_pdf),
            "--sample-page-count",
            "1",
            "--domain-adapter",
            "nvme",
            "--report-path",
            str(report_path),
        ]
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["purpose"] == "large_spec_preflight_plan"
    assert payload["recommendation"]["recommended_options"]["domain_adapter"] == "nvme"
