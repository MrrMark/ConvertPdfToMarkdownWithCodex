#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPORT_FILENAME = "corpus_evidence_trend_report.json"
SCHEMA_VERSION = "1.0"
PURPOSE = "corpus_evidence_trend_comparison"
STATUS_ORDER = {"added": 0, "persisting": 1, "resolved": 2}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def _signature_map(pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for signature in pack.get("failure_signatures", []):
        if not isinstance(signature, dict):
            continue
        signature_id = signature.get("signature_id")
        if signature_id:
            result[str(signature_id)] = signature
    return result


def _document_count(signature: dict[str, Any] | None) -> int:
    if not signature:
        return 0
    value = signature.get("document_count")
    if isinstance(value, int):
        return value
    labels = signature.get("document_labels")
    return len(labels) if isinstance(labels, list) else 0


def _signature_record(
    signature_id: str,
    *,
    status: str,
    baseline_signature: dict[str, Any] | None,
    current_signature: dict[str, Any] | None,
) -> dict[str, Any]:
    source = current_signature or baseline_signature or {}
    return {
        "signature_id": signature_id,
        "status": status,
        "severity": str(source.get("severity") or "error"),
        "category": str(source.get("category") or "unknown"),
        "domain_adapter": str(source.get("domain_adapter") or "unknown"),
        "ssd_agent_domain": str(source.get("ssd_agent_domain") or "unknown"),
        "ssd_agent_spec_type": str(source.get("ssd_agent_spec_type") or "unknown"),
        "code": source.get("code"),
        "metric": source.get("metric"),
        "baseline_document_count": _document_count(baseline_signature),
        "current_document_count": _document_count(current_signature),
    }


def build_trend_report(
    *,
    baseline_pack: dict[str, Any],
    current_pack: dict[str, Any],
    fail_on_new_signature: bool = False,
) -> dict[str, Any]:
    """Compare two redacted evidence packs by deterministic signature id."""
    baseline = _signature_map(baseline_pack)
    current = _signature_map(current_pack)
    baseline_ids = set(baseline)
    current_ids = set(current)
    added = current_ids - baseline_ids
    resolved = baseline_ids - current_ids
    persisting = baseline_ids & current_ids
    records: list[dict[str, Any]] = []
    for signature_id in sorted(added):
        records.append(
            _signature_record(
                signature_id,
                status="added",
                baseline_signature=None,
                current_signature=current[signature_id],
            )
        )
    for signature_id in sorted(persisting):
        records.append(
            _signature_record(
                signature_id,
                status="persisting",
                baseline_signature=baseline[signature_id],
                current_signature=current[signature_id],
            )
        )
    for signature_id in sorted(resolved):
        records.append(
            _signature_record(
                signature_id,
                status="resolved",
                baseline_signature=baseline[signature_id],
                current_signature=None,
            )
        )
    records.sort(
        key=lambda item: (
            STATUS_ORDER.get(str(item.get("status")), 9),
            SEVERITY_ORDER.get(str(item.get("severity")), 9),
            str(item.get("category") or ""),
            str(item.get("domain_adapter") or ""),
            str(item.get("signature_id") or ""),
        )
    )
    added_error_count = sum(1 for item in records if item["status"] == "added" and item["severity"] == "error")
    return {
        "schema_version": SCHEMA_VERSION,
        "purpose": PURPOSE,
        "baseline_profile_fingerprint": str(baseline_pack.get("profile_fingerprint") or ""),
        "current_profile_fingerprint": str(current_pack.get("profile_fingerprint") or ""),
        "passed_trend_gate": not (fail_on_new_signature and added_error_count > 0),
        "summary": {
            "baseline_signature_count": len(baseline_ids),
            "current_signature_count": len(current_ids),
            "added_signature_count": len(added),
            "resolved_signature_count": len(resolved),
            "persisting_signature_count": len(persisting),
            "added_error_signature_count": added_error_count,
        },
        "signatures": records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare redacted local corpus evidence packs.")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--report-path", type=Path, default=Path(REPORT_FILENAME))
    parser.add_argument("--fail-on-new-signature", action="store_true")
    args = parser.parse_args(argv)

    report = build_trend_report(
        baseline_pack=_load_json(args.baseline),
        current_pack=_load_json(args.current),
        fail_on_new_signature=args.fail_on_new_signature,
    )
    args.report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.report_path}")
    if args.fail_on_new_signature and not report["passed_trend_gate"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
