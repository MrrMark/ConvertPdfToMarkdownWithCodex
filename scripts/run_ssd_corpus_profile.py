from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.validate_ssd_rag_contract import DOMAIN_ADAPTER_TO_SPEC_TYPE, validate_ssd_rag_contract
except ModuleNotFoundError:  # pragma: no cover - allows `python scripts/run_ssd_corpus_profile.py`
    from validate_ssd_rag_contract import DOMAIN_ADAPTER_TO_SPEC_TYPE, validate_ssd_rag_contract


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
                "budget_failures": budget_failures,
            }
        )
    failed = [
        item
        for item in results
        if (item["conversion_exit_code"] not in {None, 0, 2})
        or item["contract_passed"] is False
        or item["budget_failures"]
    ]
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
        },
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
