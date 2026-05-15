from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.validate_ssd_rag_contract import DOMAIN_ADAPTER_TO_SPEC_TYPE, validate_ssd_rag_contract
    from scripts.run_rag_eval import (
        _load_eval_set,
        _profile_thresholds,
        _read_jsonl,
        apply_calibration_gate,
        collect_output_diagnostics,
        evaluate_queries,
    )
except ModuleNotFoundError:  # pragma: no cover - allows `python scripts/run_ssd_corpus_profile.py`
    from validate_ssd_rag_contract import DOMAIN_ADAPTER_TO_SPEC_TYPE, validate_ssd_rag_contract
    from run_rag_eval import (
        _load_eval_set,
        _profile_thresholds,
        _read_jsonl,
        apply_calibration_gate,
        collect_output_diagnostics,
        evaluate_queries,
    )


REPORT_FILENAME = "ssd_corpus_profile_report.json"
EVIDENCE_PACK_FILENAME = "local_corpus_evidence_pack.json"
EVIDENCE_SCHEMA_VERSION = "1.0"
EVIDENCE_PURPOSE = "local_technical_corpus_evidence_pack"
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _short_hash(payload: Any) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()[:16]


def _load_profile(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Profile must be a JSON object.")
    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("Profile must contain a non-empty documents list.")
    return payload


def _document_name(item: dict[str, Any], index: int) -> str:
    return str(item.get("name") or item.get("doc_id") or f"document-{index:03d}")


def _command_for_document(item: dict[str, Any]) -> list[str]:
    input_pdf = str(item["input_pdf"])
    output_dir = str(item["output_dir"])
    domain_adapter = str(item["domain_adapter"])
    command = [
        sys.executable,
        "-m",
        "pdf2md",
        input_pdf,
        "-o",
        output_dir,
        "--domain-adapter",
        domain_adapter,
        "--rag-table-output",
        "jsonl",
        "--remove-header-footer",
        "--confidential-safe-mode",
    ]
    if item.get("pages"):
        command.extend(["--pages", str(item["pages"])])
    if item.get("password"):
        command.extend(["--password", str(item["password"])])
    extra_args = item.get("extra_args") or []
    if not isinstance(extra_args, list):
        raise ValueError("extra_args must be a list when provided.")
    command.extend(str(arg) for arg in extra_args)
    return command


def _expected_spec_type(item: dict[str, Any]) -> str:
    explicit = item.get("ssd_agent_spec_type")
    if explicit:
        return str(explicit)
    adapter = str(item["domain_adapter"])
    try:
        return DOMAIN_ADAPTER_TO_SPEC_TYPE[adapter]
    except KeyError as exc:
        raise ValueError(f"Unknown domain_adapter: {adapter}") from exc


def _budget_failures(item: dict[str, Any], contract_report: dict[str, Any]) -> list[dict[str, Any]]:
    budgets = item.get("budgets") or {}
    if not isinstance(budgets, dict):
        raise ValueError("budgets must be an object when provided.")
    summary = contract_report.get("summary") or {}
    failures: list[dict[str, Any]] = []
    for metric, key in (
        ("min_chunks", "chunk_count"),
        ("min_technical_tables", "technical_table_row_count"),
        ("min_domain_units", "domain_unit_count"),
        ("min_tables", "table_row_count"),
    ):
        if metric not in budgets:
            continue
        current = int(summary.get(key) or 0)
        limit = int(budgets[metric])
        if current < limit:
            failures.append({"metric": metric, "current": current, "limit": limit, "direction": "min"})
    for metric, key in (("max_contract_warnings", "warning_count"),):
        if metric not in budgets:
            continue
        current = int(summary.get(key) or 0)
        limit = int(budgets[metric])
        if current > limit:
            failures.append({"metric": metric, "current": current, "limit": limit, "direction": "max"})
    return failures


def _numeric_metrics(report: dict[str, Any] | None) -> dict[str, float]:
    if report is None:
        return {}
    metrics = report.get("metrics")
    if not isinstance(metrics, dict):
        return {}
    return {str(key): float(value) for key, value in metrics.items() if isinstance(value, (int, float))}


def _contract_findings(contract_report: dict[str, Any] | None) -> list[dict[str, Any]]:
    if contract_report is None:
        return []
    findings: list[dict[str, Any]] = []
    for severity, key in (("error", "errors"), ("warning", "warnings")):
        raw_findings = contract_report.get(key)
        if not isinstance(raw_findings, list):
            continue
        for finding in raw_findings:
            if not isinstance(finding, dict):
                continue
            findings.append(
                {
                    "severity": severity,
                    "code": str(finding.get("code") or "unknown_contract_issue"),
                    "path": str(finding.get("path") or ""),
                }
            )
    return findings


def _rag_thresholds(item: dict[str, Any]) -> tuple[str | None, dict[str, float]]:
    profile_path = item.get("calibration_profile")
    profile_name, thresholds = _profile_thresholds(Path(profile_path) if profile_path else None)
    inline_thresholds = item.get("rag_thresholds") or item.get("thresholds") or {}
    if inline_thresholds and not isinstance(inline_thresholds, dict):
        raise ValueError("rag_thresholds/thresholds must be an object when provided.")
    thresholds.update(
        {str(key): float(value) for key, value in inline_thresholds.items() if isinstance(value, (int, float))}
    )
    return str(item.get("profile_name") or profile_name) if item.get("profile_name") or profile_name else None, thresholds


def _run_rag_eval_for_document(item: dict[str, Any]) -> dict[str, Any] | None:
    eval_set = item.get("eval_set")
    if not eval_set:
        return None
    output_dir = Path(item["output_dir"])
    chunks = _read_jsonl(output_dir / "retrieval_chunks_rag.jsonl")
    queries = _load_eval_set(Path(eval_set))
    report = evaluate_queries(chunks=chunks, queries=queries, top_k=int(item.get("top_k") or 5))
    report["metrics"].update(collect_output_diagnostics(output_dir))
    calibration_profile, thresholds = _rag_thresholds(item)
    if thresholds:
        report = apply_calibration_gate(
            report,
            calibration_profile=calibration_profile,
            thresholds=thresholds,
        )
    report_path = output_dir / "rag_eval_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _aggregate_metric_groups(results: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, list[float] | int]] = {}
    for item in results:
        metrics = _numeric_metrics(item.get("rag_eval_report"))
        if not metrics:
            continue
        group_key = str(item.get(field) or "unknown")
        group = groups.setdefault(group_key, {"document_count": 0})
        group["document_count"] = int(group["document_count"]) + 1
        for metric, value in metrics.items():
            values = group.setdefault(metric, [])
            if isinstance(values, list):
                values.append(value)

    aggregate: dict[str, dict[str, Any]] = {}
    for group_key, raw_group in sorted(groups.items()):
        group_payload: dict[str, Any] = {"document_count": int(raw_group.get("document_count") or 0)}
        for metric, values in sorted(raw_group.items()):
            if metric == "document_count" or not isinstance(values, list) or not values:
                continue
            group_payload[metric] = {
                "average": round(sum(values) / len(values), 4),
                "min": round(min(values), 4),
                "max": round(max(values), 4),
            }
        aggregate[group_key] = group_payload
    return aggregate


def _evidence_doc_label(index: int) -> str:
    return f"document-{index:06d}"


def _signature_candidates(document: dict[str, Any]) -> list[dict[str, Any]]:
    domain_adapter = str(document.get("domain_adapter") or "unknown")
    ssd_agent_domain = str(document.get("ssd_agent_domain") or "unknown")
    ssd_agent_spec_type = str(document.get("ssd_agent_spec_type") or "unknown")
    common = {
        "domain_adapter": domain_adapter,
        "ssd_agent_domain": ssd_agent_domain,
        "ssd_agent_spec_type": ssd_agent_spec_type,
    }
    candidates: list[dict[str, Any]] = []

    exit_code = document.get("conversion_exit_code")
    if isinstance(exit_code, int) and exit_code not in {0, 2}:
        candidates.append(
            {
                **common,
                "severity": "error",
                "category": "conversion_exit_code",
                "code": "conversion_failed",
                "metric": "conversion_exit_code",
                "current": exit_code,
            }
        )

    contract_findings = document.get("contract_findings")
    if isinstance(contract_findings, list) and contract_findings:
        for finding in contract_findings:
            if not isinstance(finding, dict):
                continue
            severity = str(finding.get("severity") or "error")
            candidates.append(
                {
                    **common,
                    "severity": severity,
                    "category": "contract_warning" if severity == "warning" else "contract_error",
                    "code": str(finding.get("code") or "unknown_contract_issue"),
                    "path": str(finding.get("path") or ""),
                }
            )
    elif document.get("contract_passed") is False:
        contract_summary = document.get("contract_summary") if isinstance(document.get("contract_summary"), dict) else {}
        error_count = int(contract_summary.get("error_count") or 0)
        warning_count = int(contract_summary.get("warning_count") or 0)
        if error_count:
            candidates.append(
                {
                    **common,
                    "severity": "error",
                    "category": "contract_error",
                    "code": "contract_error_count",
                    "metric": "error_count",
                    "current": error_count,
                }
            )
        if warning_count:
            candidates.append(
                {
                    **common,
                    "severity": "warning",
                    "category": "contract_warning",
                    "code": "contract_warning_count",
                    "metric": "warning_count",
                    "current": warning_count,
                }
            )

    rag_eval_report = document.get("rag_eval_report")
    gate_failures = rag_eval_report.get("gate_failures") if isinstance(rag_eval_report, dict) else []
    if isinstance(gate_failures, list):
        for failure in gate_failures:
            if not isinstance(failure, dict):
                continue
            candidates.append(
                {
                    **common,
                    "severity": "error",
                    "category": "rag_threshold",
                    "code": str(failure.get("type") or "rag_threshold_failure"),
                    "metric": str(failure.get("metric") or ""),
                    "direction": str(failure.get("direction") or ""),
                    "current": failure.get("current"),
                    "limit": failure.get("limit"),
                }
            )
    elif document.get("rag_eval_passed") is False:
        candidates.append(
            {
                **common,
                "severity": "error",
                "category": "rag_threshold",
                "code": "rag_eval_failed",
            }
        )

    budget_failures = document.get("budget_failures")
    if isinstance(budget_failures, list):
        for failure in budget_failures:
            if not isinstance(failure, dict):
                continue
            candidates.append(
                {
                    **common,
                    "severity": "error",
                    "category": "budget_failure",
                    "code": "budget_failure",
                    "metric": str(failure.get("metric") or ""),
                    "direction": str(failure.get("direction") or ""),
                    "current": failure.get("current"),
                    "limit": failure.get("limit"),
                }
            )
    return candidates


def _signature_key(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "category": candidate.get("category"),
        "severity": candidate.get("severity"),
        "domain_adapter": candidate.get("domain_adapter"),
        "ssd_agent_domain": candidate.get("ssd_agent_domain"),
        "ssd_agent_spec_type": candidate.get("ssd_agent_spec_type"),
        "code": candidate.get("code"),
        "path": candidate.get("path"),
        "metric": candidate.get("metric"),
        "direction": candidate.get("direction"),
    }


def _append_unique(target: list[Any], value: Any) -> None:
    if value not in target:
        target.append(value)


def build_evidence_pack(profile_report: dict[str, Any], *, profile_label: str = "redacted-profile") -> dict[str, Any]:
    """Build a redacted, deterministic evidence pack from a local SSD corpus profile report."""
    documents = profile_report.get("documents")
    if not isinstance(documents, list):
        documents = []

    signature_map: dict[str, dict[str, Any]] = {}
    evidence_documents: list[dict[str, Any]] = []
    domain_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    total_contract_errors = 0
    total_contract_warnings = 0
    total_rag_threshold_failures = 0
    total_budget_failures = 0
    total_conversion_failures = 0

    for index, document in enumerate(documents, start=1):
        if not isinstance(document, dict):
            continue
        document_label = _evidence_doc_label(index)
        domain_adapter = str(document.get("domain_adapter") or "unknown")
        ssd_agent_domain = str(document.get("ssd_agent_domain") or "unknown")
        ssd_agent_spec_type = str(document.get("ssd_agent_spec_type") or "unknown")
        domain_key = (domain_adapter, ssd_agent_domain, ssd_agent_spec_type)
        domain_entry = domain_map.setdefault(
            domain_key,
            {
                "domain_adapter": domain_adapter,
                "ssd_agent_domain": ssd_agent_domain,
                "ssd_agent_spec_type": ssd_agent_spec_type,
                "document_count": 0,
                "failed_document_count": 0,
                "signature_ids": [],
            },
        )
        domain_entry["document_count"] += 1

        candidates = _signature_candidates(document)
        signature_ids: list[str] = []
        for candidate in candidates:
            signature_id = f"sig-{_short_hash(_signature_key(candidate))}"
            signature_ids.append(signature_id)
            signature = signature_map.setdefault(
                signature_id,
                {
                    "signature_id": signature_id,
                    "severity": str(candidate.get("severity") or "error"),
                    "category": str(candidate.get("category") or "unknown"),
                    "domain_adapter": domain_adapter,
                    "ssd_agent_domain": ssd_agent_domain,
                    "ssd_agent_spec_type": ssd_agent_spec_type,
                    "code": candidate.get("code"),
                    "path": candidate.get("path"),
                    "metric": candidate.get("metric"),
                    "direction": candidate.get("direction"),
                    "document_count": 0,
                    "document_labels": [],
                    "observed_values": [],
                    "limits": [],
                },
            )
            _append_unique(signature["document_labels"], document_label)
            signature["document_count"] = len(signature["document_labels"])
            if "current" in candidate:
                _append_unique(signature["observed_values"], candidate.get("current"))
            if "limit" in candidate:
                _append_unique(signature["limits"], candidate.get("limit"))
            _append_unique(domain_entry["signature_ids"], signature_id)

        if signature_ids:
            domain_entry["failed_document_count"] += 1
        total_conversion_failures += sum(1 for item in candidates if item.get("category") == "conversion_exit_code")
        total_contract_errors += sum(1 for item in candidates if item.get("category") == "contract_error")
        total_contract_warnings += sum(1 for item in candidates if item.get("category") == "contract_warning")
        total_rag_threshold_failures += sum(1 for item in candidates if item.get("category") == "rag_threshold")
        total_budget_failures += sum(1 for item in candidates if item.get("category") == "budget_failure")

        evidence_documents.append(
            {
                "document_label": document_label,
                "domain_adapter": domain_adapter,
                "ssd_agent_domain": ssd_agent_domain,
                "ssd_agent_spec_type": ssd_agent_spec_type,
                "conversion_exit_code": document.get("conversion_exit_code"),
                "contract_passed": document.get("contract_passed"),
                "rag_eval_passed": document.get("rag_eval_passed"),
                "rag_eval_metrics": document.get("rag_eval_metrics") or {},
                "signature_ids": sorted(dict.fromkeys(signature_ids)),
            }
        )

    failure_signatures = sorted(
        signature_map.values(),
        key=lambda item: (
            SEVERITY_ORDER.get(str(item.get("severity")), 9),
            str(item.get("category") or ""),
            str(item.get("domain_adapter") or ""),
            str(item.get("ssd_agent_spec_type") or ""),
            str(item.get("code") or ""),
            str(item.get("metric") or ""),
            str(item.get("signature_id") or ""),
        ),
    )
    for signature in failure_signatures:
        signature["document_labels"] = sorted(signature["document_labels"])
        signature["observed_values"] = sorted(signature["observed_values"], key=lambda value: str(value))
        signature["limits"] = sorted(signature["limits"], key=lambda value: str(value))

    domains = sorted(
        domain_map.values(),
        key=lambda item: (
            str(item.get("domain_adapter") or ""),
            str(item.get("ssd_agent_domain") or ""),
            str(item.get("ssd_agent_spec_type") or ""),
        ),
    )
    for domain in domains:
        domain["signature_ids"] = sorted(domain["signature_ids"])

    failed_document_count = sum(1 for item in evidence_documents if item["signature_ids"])
    summary = {
        "document_count": len(evidence_documents),
        "failed_document_count": failed_document_count,
        "failure_signature_count": len(failure_signatures),
        "conversion_failure_count": total_conversion_failures,
        "contract_error_count": total_contract_errors,
        "contract_warning_count": total_contract_warnings,
        "rag_threshold_failure_count": total_rag_threshold_failures,
        "budget_failure_count": total_budget_failures,
    }
    redaction_policy = {
        "raw_paths_included": False,
        "commands_included": False,
        "document_names_included": False,
        "query_text_included": False,
        "source_filenames_included": False,
        "document_label_policy": "order_preserving_redacted_labels",
    }
    fingerprint_payload = {
        "profile_label": profile_label,
        "summary": summary,
        "domains": domains,
        "documents": evidence_documents,
        "failure_signatures": failure_signatures,
        "redaction_policy": redaction_policy,
    }
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "purpose": EVIDENCE_PURPOSE,
        "profile_label": profile_label,
        "profile_fingerprint": _short_hash(fingerprint_payload),
        "redaction_policy": redaction_policy,
        "summary": summary,
        "domains": domains,
        "documents": evidence_documents,
        "failure_signatures": failure_signatures,
    }


def run_profile(profile_path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Run local SSD corpus conversion and contract validation from a JSON profile."""
    profile = _load_profile(profile_path)
    results: list[dict[str, Any]] = []
    for index, raw_item in enumerate(profile["documents"], start=1):
        if not isinstance(raw_item, dict):
            raise ValueError(f"documents[{index}] must be an object.")
        item = dict(raw_item)
        for field in ("input_pdf", "output_dir", "domain_adapter"):
            if not item.get(field):
                raise ValueError(f"documents[{index}] missing required field: {field}")
        name = _document_name(item, index)
        command = _command_for_document(item)
        ssd_agent_domain = str(item.get("ssd_agent_domain") or "HIL")
        ssd_agent_spec_type = _expected_spec_type(item)
        conversion_exit_code: int | None = None
        contract_report: dict[str, Any] | None = None
        contract_findings: list[dict[str, Any]] = []
        rag_eval_report: dict[str, Any] | None = None
        budget_failures: list[dict[str, Any]] = []
        if not dry_run:
            completed = subprocess.run(command, check=False)
            conversion_exit_code = completed.returncode
            if completed.returncode in {0, 2}:
                contract_report = validate_ssd_rag_contract(
                    output_dir=Path(item["output_dir"]),
                    ssd_agent_domain=ssd_agent_domain,
                    ssd_agent_spec_type=ssd_agent_spec_type,
                    domain_adapter=str(item["domain_adapter"]),
                    document_id=str(item.get("document_id") or name),
                    require_tables=True,
                    require_domain_units=True,
                )
                contract_report_path = Path(item["output_dir"]) / "ssd_rag_contract_report.json"
                contract_report_path.write_text(
                    json.dumps(contract_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                contract_findings = _contract_findings(contract_report)
                budget_failures = _budget_failures(item, contract_report)
                rag_eval_report = _run_rag_eval_for_document(item)
        results.append(
            {
                "name": name,
                "input_pdf": str(item["input_pdf"]),
                "output_dir": str(item["output_dir"]),
                "domain_adapter": str(item["domain_adapter"]),
                "ssd_agent_domain": ssd_agent_domain,
                "ssd_agent_spec_type": ssd_agent_spec_type,
                "command": command,
                "dry_run": dry_run,
                "conversion_exit_code": conversion_exit_code,
                "contract_passed": None if contract_report is None else bool(contract_report.get("passed")),
                "contract_summary": None if contract_report is None else contract_report.get("summary"),
                "contract_findings": contract_findings,
                "rag_eval_passed": None
                if rag_eval_report is None
                else bool(rag_eval_report.get("passed_calibration_gate", True)),
                "rag_eval_metrics": _numeric_metrics(rag_eval_report),
                "rag_eval_report": rag_eval_report,
                "budget_failures": budget_failures,
            }
        )
    failed = [
        item
        for item in results
        if (item["conversion_exit_code"] not in {None, 0, 2})
        or item["contract_passed"] is False
        or item["rag_eval_passed"] is False
        or item["budget_failures"]
    ]
    rag_evaluated = [item for item in results if item.get("rag_eval_report") is not None]
    return {
        "schema_version": "1.0",
        "purpose": "ssd_local_corpus_profile",
        "profile": str(profile_path),
        "profile_name": profile.get("profile_name") or profile_path.stem,
        "dry_run": dry_run,
        "passed": not failed,
        "summary": {
            "document_count": len(results),
            "failed_count": len(failed),
            "rag_eval_document_count": len(rag_evaluated),
            "rag_eval_failed_count": sum(1 for item in rag_evaluated if item.get("rag_eval_passed") is False),
        },
        "rag_metrics_by_domain": _aggregate_metric_groups(results, "domain_adapter"),
        "rag_metrics_by_spec_type": _aggregate_metric_groups(results, "ssd_agent_spec_type"),
        "documents": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a local SSD spec corpus profile through pdf2md and contract checks.")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--report-path", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-on-error", action="store_true")
    parser.add_argument("--evidence-pack", action="store_true", help="Write a redacted local corpus evidence pack.")
    parser.add_argument("--evidence-pack-path", type=Path, default=None)
    parser.add_argument("--evidence-profile-label", default="redacted-profile")
    args = parser.parse_args(argv)

    report = run_profile(args.profile, dry_run=args.dry_run)
    report_path = args.report_path or Path(REPORT_FILENAME)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_pack_path = args.evidence_pack_path
    if evidence_pack_path is None and args.evidence_pack:
        evidence_pack_path = report_path.with_name(EVIDENCE_PACK_FILENAME)
    if evidence_pack_path is not None:
        evidence_pack = build_evidence_pack(report, profile_label=args.evidence_profile_label)
        evidence_pack_path.write_text(
            json.dumps(evidence_pack, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        "SSD corpus profile: "
        f"passed={report['passed']} documents={report['summary']['document_count']} "
        f"failed={report['summary']['failed_count']} report={report_path}"
    )
    if evidence_pack_path is not None:
        print(f"Local corpus evidence pack: report={evidence_pack_path}")
    if args.fail_on_error and not report["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
