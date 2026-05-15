#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPORT_FILENAME = "corpus_evidence_analysis_report.json"
SCHEMA_VERSION = "1.0"
PURPOSE = "corpus_evidence_signature_analysis"
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _signature_ids(signatures: list[dict[str, Any]]) -> list[str]:
    return sorted(str(signature.get("signature_id") or "") for signature in signatures if signature.get("signature_id"))


def _signature_document_count(signature: dict[str, Any]) -> int:
    value = signature.get("document_count")
    if isinstance(value, int):
        return value
    labels = signature.get("document_labels")
    return len(labels) if isinstance(labels, list) else 0


def _severity_counts(signatures: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for signature in signatures:
        severity = str(signature.get("severity") or "unknown")
        counts[severity] = counts.get(severity, 0) + 1
    return dict(sorted(counts.items()))


def _category_hotspots(signatures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for signature in signatures:
        groups.setdefault(str(signature.get("category") or "unknown"), []).append(signature)
    hotspots: list[dict[str, Any]] = []
    for category, grouped in groups.items():
        hotspots.append(
            {
                "key": category,
                "category": category,
                "signature_count": len(grouped),
                "document_count": sum(_signature_document_count(signature) for signature in grouped),
                "severity_counts": _severity_counts(grouped),
                "signature_ids": _signature_ids(grouped),
            }
        )
    return sorted(hotspots, key=lambda item: (-int(item["signature_count"]), str(item["key"])))


def _domain_hotspots(signatures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for signature in signatures:
        key = (
            str(signature.get("domain_adapter") or "unknown"),
            str(signature.get("ssd_agent_domain") or "unknown"),
            str(signature.get("ssd_agent_spec_type") or "unknown"),
        )
        groups.setdefault(key, []).append(signature)
    hotspots: list[dict[str, Any]] = []
    for (domain_adapter, ssd_agent_domain, ssd_agent_spec_type), grouped in groups.items():
        hotspots.append(
            {
                "key": f"{domain_adapter}/{ssd_agent_domain}/{ssd_agent_spec_type}",
                "domain_adapter": domain_adapter,
                "ssd_agent_domain": ssd_agent_domain,
                "ssd_agent_spec_type": ssd_agent_spec_type,
                "signature_count": len(grouped),
                "document_count": sum(_signature_document_count(signature) for signature in grouped),
                "severity_counts": _severity_counts(grouped),
                "signature_ids": _signature_ids(grouped),
            }
        )
    return sorted(hotspots, key=lambda item: (-int(item["signature_count"]), str(item["key"])))


def _text_for_signature(signature: dict[str, Any]) -> str:
    return " ".join(
        str(signature.get(field) or "")
        for field in ("category", "code", "path", "metric", "domain_adapter", "ssd_agent_spec_type")
    ).lower()


def _hint(
    *,
    hint_id: str,
    priority: str,
    reason: str,
    categories: set[str],
    signatures: list[dict[str, Any]],
) -> dict[str, Any] | None:
    ids = _signature_ids(signatures)
    if not ids:
        return None
    return {
        "hint_id": hint_id,
        "priority": priority,
        "reason": reason,
        "categories": sorted(categories),
        "matching_signature_ids": ids,
    }


def _followup_hints(signatures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    appendix_matches: list[dict[str, Any]] = []
    diagram_matches: list[dict[str, Any]] = []
    table_matches: list[dict[str, Any]] = []
    conversion_matches: list[dict[str, Any]] = []
    for signature in signatures:
        text = _text_for_signature(signature)
        category = str(signature.get("category") or "")
        if any(token in text for token in ("appendix", "clause", "heading", "requirement")):
            appendix_matches.append(signature)
        if any(token in text for token in ("figure", "diagram", "ocr", "caption", "image")):
            diagram_matches.append(signature)
        if any(token in text for token in ("table", "domain_units", "technical", "min_tables", "min_domain_units")):
            table_matches.append(signature)
        if category == "conversion_exit_code":
            conversion_matches.append(signature)

    hints = [
        _hint(
            hint_id="appendix_clause_requirement_fixture",
            priority="P1",
            reason="Requirement, heading, appendix, or clause signatures indicate fixture coverage should be expanded.",
            categories={str(item.get("category") or "") for item in appendix_matches},
            signatures=appendix_matches,
        ),
        _hint(
            hint_id="vendor_requirement_table_fixture",
            priority="P1",
            reason="Table/domain-unit signatures indicate vendor requirement table provenance needs focused coverage.",
            categories={str(item.get("category") or "") for item in table_matches},
            signatures=table_matches,
        ),
        _hint(
            hint_id="captionless_diagram_diagnostics",
            priority="P2",
            reason="Figure, diagram, OCR, image, or caption signatures indicate diagnostics-only hardening is appropriate.",
            categories={str(item.get("category") or "") for item in diagram_matches},
            signatures=diagram_matches,
        ),
        _hint(
            hint_id="conversion_failure_reproducer",
            priority="P1",
            reason="Conversion failures should be reduced to a local deterministic reproducer before adding heuristics.",
            categories={str(item.get("category") or "") for item in conversion_matches},
            signatures=conversion_matches,
        ),
    ]
    return [hint for hint in hints if hint is not None]


def build_analysis_report(evidence_pack: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic analysis from a redacted local corpus evidence pack."""
    signatures = [
        signature
        for signature in evidence_pack.get("failure_signatures", [])
        if isinstance(signature, dict)
    ]
    error_count = sum(1 for signature in signatures if signature.get("severity") == "error")
    warning_count = sum(1 for signature in signatures if signature.get("severity") == "warning")
    hints = _followup_hints(signatures)
    source_summary = evidence_pack.get("summary") if isinstance(evidence_pack.get("summary"), dict) else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "purpose": PURPOSE,
        "source_profile_label": str(evidence_pack.get("profile_label") or "redacted-profile"),
        "source_profile_fingerprint": str(evidence_pack.get("profile_fingerprint") or ""),
        "summary": {
            "document_count": int(source_summary.get("document_count") or 0),
            "failed_document_count": int(source_summary.get("failed_document_count") or 0),
            "failure_signature_count": len(signatures),
            "error_signature_count": error_count,
            "warning_signature_count": warning_count,
            "followup_hint_count": len(hints),
        },
        "category_hotspots": _category_hotspots(signatures),
        "domain_hotspots": _domain_hotspots(signatures),
        "followup_hints": sorted(
            hints,
            key=lambda item: (
                item["priority"],
                item["hint_id"],
                item["matching_signature_ids"],
            ),
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze a redacted local corpus evidence pack.")
    parser.add_argument("--evidence-pack", type=Path, required=True)
    parser.add_argument("--report-path", type=Path, default=Path(REPORT_FILENAME))
    args = parser.parse_args(argv)

    report = build_analysis_report(_load_json(args.evidence_pack))
    args.report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
