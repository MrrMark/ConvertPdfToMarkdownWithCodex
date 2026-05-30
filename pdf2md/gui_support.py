from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any, Iterable, Mapping

from pdf2md.gui_runner import GuiConversionSummary, GuiDiagnosticReport


GUI_SUPPORT_BUNDLE_SCHEMA_VERSION = "1.0"
GUI_SUPPORT_BUNDLE_JSON = "gui_support_bundle.json"
GUI_SUPPORT_BUNDLE_MARKDOWN = "gui_support_bundle.md"


def sanitize_support_path_label(path: Path | None, *, roots: Iterable[Path] | None = None) -> str | None:
    """Return a non-absolute label for a local path used in support artifacts."""
    if path is None:
        return None
    resolved = path.expanduser().resolve(strict=False)
    for index, root in enumerate(roots or (), start=1):
        root_resolved = root.expanduser().resolve(strict=False)
        try:
            relative = resolved.relative_to(root_resolved)
        except ValueError:
            continue
        return f"<root-{index}>" if str(relative) == "." else f"<root-{index}>/{relative.as_posix()}"
    for root, label in ((Path.cwd(), "<workspace>"), (Path.home(), "<home>")):
        root_resolved = root.expanduser().resolve(strict=False)
        try:
            relative = resolved.relative_to(root_resolved)
        except ValueError:
            continue
        return label if str(relative) == "." else f"{label}/{relative.as_posix()}"
    return f"<path:{resolved.name}>"


def build_gui_support_bundle(
    *,
    summary: GuiConversionSummary | None = None,
    runtime_report: GuiDiagnosticReport | None = None,
    smoke_evidence: Mapping[str, Any] | None = None,
    roots: Iterable[Path] | None = None,
) -> dict[str, Any]:
    """Build a sanitized local-only support bundle from GUI-safe summaries and evidence."""
    root_list = tuple(roots or ())
    bundle: dict[str, Any] = {
        "schema_version": GUI_SUPPORT_BUNDLE_SCHEMA_VERSION,
        "kind": "gui_support_bundle",
        "local_only": True,
        "environment": {
            "platform": platform.system() or "unknown",
            "python_version": platform.python_version(),
        },
        "redaction_policy": {
            "stores_raw_pdf_text": False,
            "stores_table_content": False,
            "stores_image_content": False,
            "stores_conversion_warning_messages": False,
            "stores_absolute_paths": False,
            "path_policy": "paths are stored only as root-relative or basename labels",
        },
    }
    if summary is not None:
        bundle["conversion_summary"] = _summary_payload(summary, roots=(summary.output_root, *root_list))
    if runtime_report is not None:
        bundle["runtime"] = _runtime_payload(runtime_report)
    if smoke_evidence is not None:
        bundle["smoke_evidence"] = _smoke_payload(smoke_evidence)
    return bundle


def support_bundle_redaction_findings(
    bundle: Mapping[str, Any],
    *,
    forbidden_values: Iterable[str] = (),
    roots: Iterable[Path] = (),
) -> list[dict[str, str]]:
    """Return deterministic redaction findings for values that must not be shared."""
    serialized = json.dumps(bundle, ensure_ascii=False, sort_keys=True)
    findings: list[dict[str, str]] = []
    for value in forbidden_values:
        if value and value in serialized:
            findings.append({"code": "forbidden_value_detected", "value": "<redacted>"})
    if _contains_absolute_path(serialized, roots=roots):
        findings.append({"code": "absolute_path_detected", "value": "absolute_path"})
    return findings


def render_support_bundle_markdown(bundle: Mapping[str, Any]) -> str:
    """Render a compact Markdown support bundle without raw document content."""
    lines = [
        "# GUI Support Bundle",
        "",
        f"- Status: {_bundle_status(bundle)}",
        f"- Schema version: {bundle.get('schema_version', 'unknown')}",
        f"- Platform: {bundle.get('environment', {}).get('platform', 'unknown')}",
        f"- Python: {bundle.get('environment', {}).get('python_version', 'unknown')}",
    ]
    runtime = bundle.get("runtime")
    if isinstance(runtime, Mapping):
        lines.extend(
            [
                "",
                "## Runtime",
                f"- Errors: {runtime.get('error_count', 0)}",
                f"- Warnings: {runtime.get('warning_count', 0)}",
                f"- Advisories: {runtime.get('advisory_count', 0)}",
                "- Codes: " + ", ".join(_diagnostic_codes(runtime.get("diagnostics", []))),
            ]
        )
    summary = bundle.get("conversion_summary")
    if isinstance(summary, Mapping):
        lines.extend(["", "## Conversion Summary"])
        counts = summary.get("status_counts", {})
        if isinstance(counts, Mapping):
            lines.append("- Status counts: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
        lines.append(f"- Total warnings: {summary.get('warning_count', 0)}")
        for document in summary.get("documents", []):
            if not isinstance(document, Mapping):
                continue
            lines.append(
                "- "
                + str(document.get("input_label", "<document>"))
                + f": status={document.get('status', 'unknown')}, warnings={document.get('warning_count', 0)}"
            )
    smoke = bundle.get("smoke_evidence")
    if isinstance(smoke, Mapping):
        lines.extend(
            [
                "",
                "## Smoke Evidence",
                f"- Status: {smoke.get('status', 'unknown')}",
                f"- Failed checks: {smoke.get('failed_check_count', 0)}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def write_gui_support_bundle(bundle: Mapping[str, Any], output_dir: Path) -> tuple[Path, Path]:
    """Write sanitized support bundle JSON and Markdown files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / GUI_SUPPORT_BUNDLE_JSON
    markdown_path = output_dir / GUI_SUPPORT_BUNDLE_MARKDOWN
    json_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_support_bundle_markdown(bundle), encoding="utf-8")
    return json_path, markdown_path


def _summary_payload(summary: GuiConversionSummary, *, roots: Iterable[Path]) -> dict[str, Any]:
    documents = []
    for document in summary.documents:
        documents.append(
            {
                "input_label": document.input_pdf.name,
                "output_label": sanitize_support_path_label(document.output_dir, roots=roots),
                "status": document.status,
                "exit_code": document.exit_code,
                "warning_count": document.warning_count,
                "actionable_warning_count": document.actionable_warning_count,
                "advisory_warning_count": document.advisory_warning_count,
                "warning_codes": list(document.warning_codes),
                "retry_candidate": document.retry_candidate,
                "skipped": document.skipped,
                "artifacts": {
                    "markdown": _artifact_payload(document.markdown_path, roots=roots),
                    "manifest": _artifact_payload(document.manifest_path, roots=roots),
                    "report": _artifact_payload(document.report_path, roots=roots),
                    "assets_dir": _artifact_payload(document.assets_dir, roots=roots),
                },
            }
        )
    return {
        "input_mode": summary.input_mode,
        "input_label": sanitize_support_path_label(summary.input_path, roots=roots),
        "output_root_label": sanitize_support_path_label(summary.output_root, roots=roots),
        "exit_code": summary.exit_code,
        "status_counts": {
            "success": summary.success_count,
            "partial_success": summary.partial_success_count,
            "failed": summary.failed_count,
            "skipped": summary.skipped_count,
            "cancelled": summary.cancelled_count,
        },
        "warning_count": sum(document.warning_count for document in summary.documents),
        "actionable_warning_count": sum(document.actionable_warning_count for document in summary.documents),
        "advisory_warning_count": sum(document.advisory_warning_count for document in summary.documents),
        "warning_codes": sorted({code for document in summary.documents for code in document.warning_codes}),
        "documents": documents,
    }


def _runtime_payload(report: GuiDiagnosticReport) -> dict[str, Any]:
    return {
        "kind": "gui_runtime_doctor",
        "passed": not report.has_errors,
        "error_count": len(report.errors),
        "warning_count": len(report.warnings),
        "advisory_count": len(report.advisories),
        "diagnostics": [
            {
                "code": diagnostic.code,
                "severity": diagnostic.severity,
            }
            for diagnostic in report.diagnostics
        ],
    }


def _smoke_payload(smoke_evidence: Mapping[str, Any]) -> dict[str, Any]:
    raw_summary = smoke_evidence.get("summary", {})
    summary = raw_summary if isinstance(raw_summary, Mapping) else {}
    raw_runtime = smoke_evidence.get("runtime", {})
    runtime = raw_runtime if isinstance(raw_runtime, Mapping) else {}
    raw_runner_smoke = smoke_evidence.get("runner_smoke", [])
    runner_smoke = raw_runner_smoke if isinstance(raw_runner_smoke, list) else []
    return {
        "status": str(smoke_evidence.get("status", "unknown")),
        "failed_check_count": _mapping_int(summary, "failed_check_count"),
        "failed_check_codes": [
            str(item.get("code", "unknown"))
            for item in summary.get("failed_checks", [])
            if isinstance(item, Mapping)
        ],
        "runtime_codes": _diagnostic_codes(runtime.get("diagnostics", [])),
        "runner_smoke": [
            {
                "name": str(item.get("name", "unknown")),
                "passed": bool(item.get("passed", False)),
                "input_mode": str(item.get("input_mode", "unknown")),
                "status_counts": dict(item.get("status_counts", {})) if isinstance(item.get("status_counts"), Mapping) else {},
            }
            for item in runner_smoke
            if isinstance(item, Mapping)
        ],
    }


def _artifact_payload(path: Path | None, *, roots: Iterable[Path]) -> dict[str, Any]:
    return {
        "exists": bool(path and path.exists()),
        "label": sanitize_support_path_label(path, roots=roots),
    }


def _diagnostic_codes(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    return sorted(
        {
            str(item.get("code"))
            for item in items
            if isinstance(item, Mapping) and item.get("code")
        }
    )


def _mapping_int(mapping: object, key: str) -> int:
    if not isinstance(mapping, Mapping):
        return 0
    value = mapping.get(key, 0)
    return value if isinstance(value, int) else 0


def _bundle_status(bundle: Mapping[str, Any]) -> str:
    runtime = bundle.get("runtime")
    if isinstance(runtime, Mapping) and runtime.get("passed") is False:
        return "needs_runtime_attention"
    smoke = bundle.get("smoke_evidence")
    if isinstance(smoke, Mapping) and smoke.get("status") == "failed":
        return "needs_smoke_attention"
    summary = bundle.get("conversion_summary")
    if isinstance(summary, Mapping) and summary.get("exit_code", 0) != 0:
        return "conversion_attention"
    return "ready"


def _contains_absolute_path(text: str, *, roots: Iterable[Path]) -> bool:
    for root in roots:
        resolved = str(root.expanduser().resolve(strict=False))
        if resolved and resolved in text:
            return True
    if str(Path.cwd().resolve(strict=False)) in text or str(Path.home().resolve(strict=False)) in text:
        return True
    if os.name == "nt":
        return ":\\" in text or ":/" in text
    return "/Users/" in text or "/home/" in text or "/private/" in text
