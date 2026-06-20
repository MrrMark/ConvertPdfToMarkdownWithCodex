from __future__ import annotations

import json
from pathlib import Path

from pdf2md import mcp_server
from pdf2md.preflight import PreflightOptions, plan_large_spec_conversion
from scripts.plan_large_spec_conversion import main as plan_large_spec_main
from tests.fixtures.pdf_builder import PageSpec, PositionedText, write_pdf


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
