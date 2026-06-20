from __future__ import annotations

import json
from pathlib import Path

from pdf2md import mcp_server
from pdf2md.preflight import PreflightOptions, plan_large_spec_conversion, recommend_domain_adapter_for_pdf
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
