from __future__ import annotations

import json
from pathlib import Path

from pdf2md.models import CorpusEvidenceAnalysisReport, CorpusEvidenceTrendReport
from scripts.analyze_corpus_evidence_pack import build_analysis_report, main as analyze_main
from scripts.compare_corpus_evidence_packs import build_trend_report, main as compare_main


def _signature(
    signature_id: str,
    *,
    category: str,
    severity: str = "error",
    code: str | None = None,
    path: str | None = None,
    metric: str | None = None,
    domain_adapter: str = "customer-requirements",
    spec_type: str = "CustomerRequirement",
) -> dict:
    return {
        "signature_id": signature_id,
        "severity": severity,
        "category": category,
        "domain_adapter": domain_adapter,
        "ssd_agent_domain": "HIL",
        "ssd_agent_spec_type": spec_type,
        "code": code,
        "path": path,
        "metric": metric,
        "document_count": 2,
        "document_labels": ["document-000001", "document-000002"],
        "observed_values": [],
        "limits": [],
    }


def _pack(*signatures: dict, fingerprint: str = "fp-current") -> dict:
    return {
        "schema_version": "1.0",
        "purpose": "local_technical_corpus_evidence_pack",
        "profile_label": "redacted-profile",
        "profile_fingerprint": fingerprint,
        "summary": {
            "document_count": 2,
            "failed_document_count": 1,
            "failure_signature_count": len(signatures),
        },
        "failure_signatures": list(signatures),
    }


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_analyze_corpus_evidence_pack_builds_hotspots_and_followup_hints(tmp_path: Path) -> None:
    pack = _pack(
        _signature(
            "sig-appendix",
            category="contract_error",
            code="missing_requirement_heading_path",
            path="requirement_traceability_rag.jsonl",
        ),
        _signature(
            "sig-table",
            category="budget_failure",
            metric="min_domain_units",
            path="domain_units_rag.jsonl",
        ),
        _signature(
            "sig-diagram",
            category="contract_warning",
            severity="warning",
            code="ocr_caption_low_confidence",
            path="figures_rag.jsonl",
        ),
    )

    report = build_analysis_report(pack)
    CorpusEvidenceAnalysisReport.model_validate(report)

    assert report["purpose"] == "corpus_evidence_signature_analysis"
    assert report["summary"]["failure_signature_count"] == 3
    assert report["category_hotspots"][0]["key"] == "budget_failure"
    assert {hint["hint_id"] for hint in report["followup_hints"]} == {
        "appendix_clause_requirement_fixture",
        "captionless_diagram_diagnostics",
        "vendor_requirement_table_fixture",
    }

    input_path = tmp_path / "local_corpus_evidence_pack.json"
    output_path = tmp_path / "corpus_evidence_analysis_report.json"
    _write_json(input_path, pack)
    assert analyze_main(["--evidence-pack", str(input_path), "--report-path", str(output_path)]) == 0
    CorpusEvidenceAnalysisReport.model_validate(json.loads(output_path.read_text(encoding="utf-8")))


def test_compare_corpus_evidence_packs_reports_signature_trends(tmp_path: Path) -> None:
    baseline = _pack(
        _signature("sig-persisting", category="contract_error"),
        _signature("sig-resolved", category="contract_warning", severity="warning"),
        fingerprint="fp-baseline",
    )
    current = _pack(
        _signature("sig-persisting", category="contract_error"),
        _signature("sig-added", category="budget_failure", metric="min_domain_units"),
        fingerprint="fp-current",
    )

    report = build_trend_report(
        baseline_pack=baseline,
        current_pack=current,
        fail_on_new_signature=True,
    )
    CorpusEvidenceTrendReport.model_validate(report)

    assert report["purpose"] == "corpus_evidence_trend_comparison"
    assert report["passed_trend_gate"] is False
    assert report["summary"] == {
        "baseline_signature_count": 2,
        "current_signature_count": 2,
        "added_signature_count": 1,
        "resolved_signature_count": 1,
        "persisting_signature_count": 1,
        "added_error_signature_count": 1,
    }
    assert [record["status"] for record in report["signatures"]] == ["added", "persisting", "resolved"]

    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    output_path = tmp_path / "trend.json"
    _write_json(baseline_path, baseline)
    _write_json(current_path, current)

    assert (
        compare_main(
            [
                "--baseline",
                str(baseline_path),
                "--current",
                str(current_path),
                "--report-path",
                str(output_path),
                "--fail-on-new-signature",
            ]
        )
        == 1
    )
    CorpusEvidenceTrendReport.model_validate(json.loads(output_path.read_text(encoding="utf-8")))
    assert (
        compare_main(
            [
                "--baseline",
                str(baseline_path),
                "--current",
                str(current_path),
                "--report-path",
                str(tmp_path / "trend_without_gate.json"),
            ]
        )
        == 0
    )
