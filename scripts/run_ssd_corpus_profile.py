from __future__ import annotations

import argparse
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
    args = parser.parse_args(argv)

    report = run_profile(args.profile, dry_run=args.dry_run)
    report_path = args.report_path or Path(REPORT_FILENAME)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "SSD corpus profile: "
        f"passed={report['passed']} documents={report['summary']['document_count']} "
        f"failed={report['summary']['failed_count']} report={report_path}"
    )
    if args.fail_on_error and not report["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
