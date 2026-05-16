from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject

from pdf2md.gui_i18n import SUPPORTED_GUI_LANGUAGES
from pdf2md.gui_presets import (
    SUPPORTED_GUI_OPTION_PRESETS,
    apply_preset_to_options,
    preset_display_name,
    preset_editable_fields,
)
from pdf2md.gui_runner import (
    GuiConversionOptions,
    GuiConversionRequest,
    GuiConversionSummary,
    check_gui_runtime,
    run_gui_conversion,
)
from pdf2md.gui_state import (
    GUI_STATE_SCHEMA_VERSION,
    GuiRecentState,
    GuiStateStore,
    remember_gui_path,
    remember_gui_preferences,
)


EVIDENCE_FILENAME = "gui_smoke_evidence.json"
EXIT_SMOKE_FAILED = 1
SINGLE_FIXTURE_TEXT = "Q62 single smoke fixture text must not appear in evidence."
BATCH_FIXTURE_TEXTS = (
    "Q62 batch alpha fixture text must not appear in evidence.",
    "Q62 batch beta fixture text must not appear in evidence.",
)
FORBIDDEN_EVIDENCE_STRINGS = (SINGLE_FIXTURE_TEXT, *BATCH_FIXTURE_TEXTS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create local-only GUI smoke evidence without launching a Tk window. "
            "The evidence records diagnostics, sanitized command results, GUI runner smoke status, "
            "and manual checklist state."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("gui_smoke_output"),
        help="Directory for local smoke fixtures, conversion outputs, and gui_smoke_evidence.json.",
    )
    parser.add_argument(
        "--state-path",
        type=Path,
        default=None,
        help="Isolated GUI state path used only for this smoke run.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only the sanitized evidence JSON to stdout.",
    )
    return parser


def redact_text(text: object, roots: Iterable[Path] | None = None) -> str:
    """Redact known local absolute roots from arbitrary evidence text."""
    redacted = str(text)
    replacements = _redaction_roots(roots)
    for raw_path, placeholder in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        if raw_path:
            redacted = redacted.replace(raw_path, placeholder)
    return redacted


def redact_path_label(path: Path | None, *, output_dir: Path | None = None) -> str | None:
    """Return a relative or redacted label for evidence instead of an absolute path."""
    if path is None:
        return None
    expanded = path.expanduser()
    resolved = expanded.resolve(strict=False)
    if output_dir is not None:
        output_resolved = output_dir.expanduser().resolve(strict=False)
        try:
            relative = resolved.relative_to(output_resolved)
        except ValueError:
            pass
        else:
            return "<output>" if str(relative) == "." else f"<output>/{relative.as_posix()}"
    cwd = Path.cwd().resolve(strict=False)
    try:
        relative = resolved.relative_to(cwd)
    except ValueError:
        pass
    else:
        return "<workspace>" if str(relative) == "." else f"<workspace>/{relative.as_posix()}"
    home = Path.home().resolve(strict=False)
    try:
        relative = resolved.relative_to(home)
    except ValueError:
        return f"<path:{resolved.name}>"
    return "<home>" if str(relative) == "." else f"<home>/{relative.as_posix()}"


def run_smoke(output_dir: Path, state_path: Path) -> dict[str, Any]:
    """Run the headless GUI smoke workflow and return sanitized evidence."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fixtures = _prepare_fixtures(output_dir)
    redaction_roots = (output_dir, state_path.parent, Path.cwd(), Path.home())
    runtime_report = check_gui_runtime()
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "generated_by": "scripts/run_gui_smoke_evidence.py",
        "environment": _environment_evidence(),
        "evidence_file": f"<output>/{EVIDENCE_FILENAME}",
        "runtime": _runtime_evidence(runtime_report, output_dir=output_dir, roots=redaction_roots),
        "commands": [_help_command_evidence(output_dir=output_dir, roots=redaction_roots)],
        "presets": _preset_evidence(),
        "state": _state_evidence(state_path, output_dir, fixtures["single_pdf"]),
        "runner_smoke": _runner_smoke_evidence(output_dir, fixtures),
        "manual_checklist": _manual_checklist_evidence(),
        "redaction_policy": {
            "stores_raw_pdf_text": False,
            "stores_table_content": False,
            "stores_image_content": False,
            "stores_conversion_warning_messages": False,
            "path_policy": "absolute paths are replaced by <output>, <workspace>, <home>, or basename labels",
        },
    }
    return finalize_evidence(evidence)


def finalize_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Attach deterministic pass/fail summary and redaction findings to evidence."""
    failed_checks = _failed_checks(evidence)
    serialized = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    redaction_findings = [
        {"code": "forbidden_fixture_text", "value": "fixture_text_detected"}
        for forbidden in FORBIDDEN_EVIDENCE_STRINGS
        if forbidden in serialized
    ]
    if _contains_absolute_path(serialized):
        redaction_findings.append(
            {
                "code": "absolute_path_detected",
                "value": "evidence text still appears to contain an absolute path",
            }
        )
    failed_checks.extend(
        {
            "code": finding["code"],
            "section": "redaction",
            "next_action": "Inspect evidence construction and store only labels/counts/codes.",
        }
        for finding in redaction_findings
    )
    evidence["summary"] = {
        "status": "failed" if failed_checks else "passed",
        "passed": not failed_checks,
        "failed_check_count": len(failed_checks),
        "failed_checks": failed_checks,
        "redaction_findings": redaction_findings,
    }
    evidence["status"] = evidence["summary"]["status"]
    return evidence


def exit_code_for_evidence(evidence: dict[str, Any]) -> int:
    """Return the process exit code for a finalized evidence object."""
    return 0 if evidence.get("status") == "passed" else EXIT_SMOKE_FAILED


def write_evidence(evidence: dict[str, Any], output_dir: Path) -> Path:
    """Write sanitized evidence JSON with stable ordering."""
    evidence_path = output_dir / EVIDENCE_FILENAME
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return evidence_path


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir.expanduser().resolve(strict=False)
    state_path = (args.state_path or output_dir / "gui_state_smoke.json").expanduser().resolve(strict=False)
    evidence = run_smoke(output_dir, state_path)
    evidence_path = write_evidence(evidence, output_dir)
    if args.json_only:
        print(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(evidence, evidence_path, output_dir)
    return exit_code_for_evidence(evidence)


def _redaction_roots(roots: Iterable[Path] | None) -> list[tuple[str, str]]:
    root_labels: list[tuple[Path, str]] = []
    if roots:
        for index, root in enumerate(roots, start=1):
            root_labels.append((root, f"<redacted-{index}>"))
    root_labels.extend(
        [
            (Path.cwd(), "<workspace>"),
            (Path.home(), "<home>"),
        ]
    )
    replacements: list[tuple[str, str]] = []
    seen: set[str] = set()
    for root, placeholder in root_labels:
        resolved = root.expanduser().resolve(strict=False)
        variants = {str(resolved), str(root.expanduser())}
        if os.sep == "/":
            variants.update(value.replace("/", "\\") for value in list(variants))
        else:
            variants.update(value.replace("\\", "/") for value in list(variants))
        for variant in variants:
            if variant and variant not in seen:
                seen.add(variant)
                replacements.append((variant, placeholder))
    return replacements


def _environment_evidence() -> dict[str, str]:
    return {
        "python_version": platform.python_version(),
        "platform": platform.system() or "unknown",
    }


def _runtime_evidence(report, *, output_dir: Path, roots: Iterable[Path]) -> dict[str, Any]:  # noqa: ANN001
    diagnostics = []
    for diagnostic in report.diagnostics:
        item = {
            "code": diagnostic.code,
            "severity": diagnostic.severity,
            "message": redact_text(diagnostic.message, roots),
        }
        if diagnostic.path is not None:
            item["path"] = redact_path_label(diagnostic.path, output_dir=output_dir)
        diagnostics.append(item)
    return {
        "passed": not report.has_errors,
        "error_count": len(report.errors),
        "warning_count": len(report.warnings),
        "diagnostics": diagnostics,
    }


def _help_command_evidence(*, output_dir: Path, roots: Iterable[Path]) -> dict[str, Any]:
    command = [sys.executable, "-m", "pdf2md.gui", "--help"]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "name": "gui_module_help",
            "args": [Path(sys.executable).name, "-m", "pdf2md.gui", "--help"],
            "passed": False,
            "return_code": None,
            "stdout_excerpt": "",
            "stderr_excerpt": redact_text(exc, roots),
            "expected": "python -m pdf2md.gui --help exits 0 without launching a window",
        }
    stdout = redact_text(_truncate(completed.stdout), roots)
    stderr = redact_text(_truncate(completed.stderr), roots)
    return {
        "name": "gui_module_help",
        "args": [Path(sys.executable).name, "-m", "pdf2md.gui", "--help"],
        "passed": completed.returncode == 0 and "desktop GUI wrapper" in completed.stdout,
        "return_code": completed.returncode,
        "stdout_excerpt": stdout,
        "stderr_excerpt": stderr,
        "expected": "python -m pdf2md.gui --help exits 0 without launching a window",
        "output_label": redact_path_label(output_dir, output_dir=output_dir),
    }


def _preset_evidence() -> list[dict[str, Any]]:
    base = GuiConversionOptions(pages="1", password="secret-smoke", ocr_lang="kor+eng", force_ocr=True)
    records = []
    for preset in SUPPORTED_GUI_OPTION_PRESETS:
        applied = apply_preset_to_options(preset, base)
        records.append(
            {
                "preset": preset,
                "display_names": {
                    language: preset_display_name(language, preset)
                    for language in SUPPORTED_GUI_LANGUAGES
                },
                "editable_fields": preset_editable_fields(preset),
                "document_inputs_preserved": {
                    "pages": applied.pages == base.pages,
                    "password": applied.password == base.password,
                    "ocr_lang": applied.ocr_lang == base.ocr_lang,
                },
            }
        )
    return records


def _state_evidence(state_path: Path, output_dir: Path, input_pdf: Path) -> dict[str, Any]:
    store = GuiStateStore(state_path)
    state = remember_gui_preferences(
        GuiRecentState(),
        language="en",
        option_preset="rag_optimized",
    )
    state = remember_gui_path(state, "input_file", input_pdf)
    state = remember_gui_path(state, "output_dir", output_dir / "state-output")
    store.save(state)
    loaded = store.load()
    passed = (
        loaded.language == "en"
        and loaded.option_preset == "rag_optimized"
        and len(loaded.recent_input_files) == 1
        and len(loaded.recent_output_dirs) == 1
    )
    existed_after_save = state_path.exists()
    store.clear()
    return {
        "passed": passed and existed_after_save and not state_path.exists(),
        "schema_version": GUI_STATE_SCHEMA_VERSION,
        "state_path_label": redact_path_label(state_path, output_dir=output_dir),
        "language": loaded.language,
        "option_preset": loaded.option_preset,
        "recent_input_file_count": len(loaded.recent_input_files),
        "recent_output_dir_count": len(loaded.recent_output_dirs),
        "cleared_after_smoke": not state_path.exists(),
        "stores_raw_content": False,
    }


def _runner_smoke_evidence(output_dir: Path, fixtures: dict[str, Path]) -> list[dict[str, Any]]:
    smoke_cases = [
        (
            "single_preserve",
            "preserve",
            GuiConversionRequest(
                input_mode="file",
                input_path=fixtures["single_pdf"],
                output_dir=output_dir / "single-preserve-output",
                options=apply_preset_to_options("preserve", GuiConversionOptions(pages="1")),
            ),
        ),
        (
            "single_custom",
            "custom",
            GuiConversionRequest(
                input_mode="file",
                input_path=fixtures["single_pdf"],
                output_dir=output_dir / "single-custom-output",
                options=apply_preset_to_options(
                    "custom",
                    GuiConversionOptions(pages="1", keep_page_markers=True),
                ),
            ),
        ),
        (
            "batch_rag_optimized",
            "rag_optimized",
            GuiConversionRequest(
                input_mode="folder",
                input_path=fixtures["batch_dir"],
                output_dir=output_dir / "batch-rag-output",
                options=apply_preset_to_options("rag_optimized", GuiConversionOptions(pages="1")),
            ),
        ),
    ]
    records = []
    for name, preset, request in smoke_cases:
        try:
            summary = run_gui_conversion(request)
        except Exception as exc:  # noqa: BLE001
            records.append(
                {
                    "name": name,
                    "preset": preset,
                    "passed": False,
                    "input_mode": request.input_mode,
                    "error": redact_text(exc, (output_dir, Path.cwd(), Path.home())),
                    "documents": [],
                }
            )
            continue
        records.append(_summary_evidence(name, preset, summary, output_dir))
    return records


def _summary_evidence(name: str, preset: str, summary: GuiConversionSummary, output_dir: Path) -> dict[str, Any]:
    return {
        "name": name,
        "preset": preset,
        "passed": summary.exit_code == 0,
        "input_mode": summary.input_mode,
        "output_root_label": redact_path_label(summary.output_root, output_dir=output_dir),
        "exit_code": summary.exit_code,
        "status_counts": {
            "success": summary.success_count,
            "partial_success": summary.partial_success_count,
            "failed": summary.failed_count,
            "skipped": summary.skipped_count,
            "cancelled": summary.cancelled_count,
        },
        "documents": [
            {
                "input_label": document.input_pdf.name,
                "output_label": redact_path_label(document.output_dir, output_dir=output_dir),
                "status": document.status,
                "exit_code": document.exit_code,
                "warning_count": document.warning_count,
                "warning_codes": list(document.warning_codes),
                "retry_candidate": document.retry_candidate,
                "artifacts": {
                    "markdown": _artifact_evidence(document.markdown_path, output_dir),
                    "manifest": _artifact_evidence(document.manifest_path, output_dir),
                    "report": _artifact_evidence(document.report_path, output_dir),
                    "assets_dir": _artifact_evidence(document.assets_dir, output_dir),
                },
            }
            for document in summary.documents
        ],
    }


def _artifact_evidence(path: Path | None, output_dir: Path) -> dict[str, Any]:
    return {
        "exists": bool(path and path.exists()),
        "label": redact_path_label(path, output_dir=output_dir),
    }


def _manual_checklist_evidence() -> list[dict[str, str]]:
    return [
        {
            "id": "launch_default_korean",
            "status": "manual_required",
            "check": "Launch the Tk window locally and confirm Korean is the default UI language.",
        },
        {
            "id": "english_switch",
            "status": "manual_required",
            "check": "Switch to English and confirm visible labels, buttons, headings, and status text update.",
        },
        {
            "id": "preset_lock_unlock",
            "status": "manual_required",
            "check": "Confirm preserve/RAG presets lock detailed options and custom unlocks them.",
        },
        {
            "id": "progress_percent",
            "status": "manual_required",
            "check": "Confirm single conversion ends at 100% and batch conversion shows current/total percent.",
        },
        {
            "id": "state_clear",
            "status": "manual_required",
            "check": "Restart the GUI, confirm local-only preference restore, then Clear recent removes paths.",
        },
    ]


def _prepare_fixtures(output_dir: Path) -> dict[str, Path]:
    fixture_dir = output_dir / "fixtures"
    batch_dir = fixture_dir / "batch"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    batch_dir.mkdir(parents=True, exist_ok=True)
    single_pdf = fixture_dir / "single-smoke.pdf"
    alpha_pdf = batch_dir / "alpha-smoke.pdf"
    beta_pdf = batch_dir / "beta-smoke.pdf"
    _write_text_pdf(single_pdf, SINGLE_FIXTURE_TEXT)
    _write_text_pdf(alpha_pdf, BATCH_FIXTURE_TEXTS[0])
    _write_text_pdf(beta_pdf, BATCH_FIXTURE_TEXTS[1])
    return {
        "single_pdf": single_pdf,
        "batch_dir": batch_dir,
        "alpha_pdf": alpha_pdf,
        "beta_pdf": beta_pdf,
    }


def _write_text_pdf(path: Path, text: str) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)  # noqa: SLF001
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref}),
        }
    )
    content = StreamObject()
    content._data = f"BT /F1 12 Tf 72 770 Td ({_escape_pdf_text(text)}) Tj ET".encode("utf-8")  # noqa: SLF001
    page[NameObject("/Contents")] = writer._add_object(content)  # noqa: SLF001
    with path.open("wb") as fp:
        writer.write(fp)


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _failed_checks(evidence: dict[str, Any]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    if not evidence["runtime"]["passed"]:
        failures.append(
            {
                "code": "gui_runtime_failed",
                "section": "runtime",
                "next_action": "Install Python 3.11+ with Tkinter/Tcl-Tk support and rerun the smoke script.",
            }
        )
    for command in evidence["commands"]:
        if not command["passed"]:
            failures.append(
                {
                    "code": f"{command['name']}_failed",
                    "section": "commands",
                    "next_action": "Run python -m pdf2md.gui --help in the same environment and inspect stderr.",
                }
            )
    if not evidence["state"]["passed"]:
        failures.append(
            {
                "code": "gui_state_isolation_failed",
                "section": "state",
                "next_action": "Check --state-path permissions and GUI state schema v2 round-trip behavior.",
            }
        )
    for smoke in evidence["runner_smoke"]:
        if not smoke["passed"]:
            failures.append(
                {
                    "code": f"{smoke['name']}_failed",
                    "section": "runner_smoke",
                    "next_action": "Inspect sanitized smoke output labels and rerun the GUI runner path locally.",
                }
            )
            continue
        for document in smoke["documents"]:
            missing = [
                name
                for name, artifact in document["artifacts"].items()
                if name != "assets_dir" and not artifact["exists"]
            ]
            if missing:
                failures.append(
                    {
                        "code": f"{smoke['name']}_missing_artifacts",
                        "section": "runner_smoke",
                        "next_action": f"Expected artifacts are missing: {', '.join(sorted(missing))}.",
                    }
                )
    return failures


def _contains_absolute_path(text: str) -> bool:
    if str(Path.cwd().resolve(strict=False)) in text or str(Path.home().resolve(strict=False)) in text:
        return True
    if os.name == "nt":
        return ":\\" in text or ":/" in text
    return "/Users/" in text or "/home/" in text or "/private/" in text


def _truncate(text: str, *, limit: int = 1200) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"


def _print_summary(evidence: dict[str, Any], evidence_path: Path, output_dir: Path) -> None:
    print(f"GUI smoke evidence: {evidence['status']}")
    print(f"Evidence file: {redact_path_label(evidence_path, output_dir=output_dir)}")
    if evidence["summary"]["failed_checks"]:
        print("Failed checks:")
        for failure in evidence["summary"]["failed_checks"]:
            print(f"- {failure['code']}: {failure['next_action']}")
    else:
        print("All headless smoke checks passed. Manual GUI checklist remains local-only.")


if __name__ == "__main__":
    raise SystemExit(main())
